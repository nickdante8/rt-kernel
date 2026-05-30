#!/bin/bash

# ==============================================================================
# 1. SETTINGS & GLOBALS
# ==============================================================================
# Exit immediately if a command exits with a non-zero status
set -e

# Determine the directory where this script resides
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
CONFIG_FILE="${SCRIPT_DIR}/config.env"


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
# Load configuration file of the script
environment_var() {
    if [ -f "${CONFIG_FILE}" ]; then
        echo "Sourcing configuration from ${CONFIG_FILE}..."
        # shellcheck source=config.env
        source "${CONFIG_FILE}"
    else
        echo "ERROR: Configuration file not found at ${CONFIG_FILE}"
        exit 1
    fi

    # Adjust to user's updated dist directory structure
    DIST_DIR="${SCRIPT_DIR}/dist/${BUILD_DIR_NAME}"

    if [ ! -d "${DIST_DIR}" ]; then
        echo "ERROR: Distribution directory not found at ${DIST_DIR}."
        echo "Please run ./make.sh first to build and package the kernel."
        exit 1
    fi

    if [ -z "${SSH_USER}" ] || [ -z "${SSH_HOST}" ] || [ -z "${REMOTE_BOOT_DIR}" ]; then
        echo "ERROR: SSH connection details (SSH_USER, SSH_HOST, REMOTE_BOOT_DIR) are missing in config.env."
        exit 1
    fi

    # Set helper variables
    PIN_USB_IRQ_NAME="pin-usb-irq"
    PIN_USB_IRQ_REMOTE_PATH="/usr/local/bin/${PIN_USB_IRQ_NAME}.sh"
    SWITCH_KERNEL_NAME="switch-kernel"
    SWITCH_KERNEL_REMOTE_PATH="/usr/local/bin/${SWITCH_KERNEL_NAME}.sh"

    # Determine OS_PREFIX directory name
    if [ "${ENABLE_RT}" = "true" ]; then
        OS_PREFIX="${KERNEL_VERSION_MAJOR_MINOR}.${KERNEL_VERSION_PATCH}-rt"
    else
        OS_PREFIX="${KERNEL_VERSION_MAJOR_MINOR}.${KERNEL_VERSION_PATCH}-baseline"
    fi

    # Ensure .sshpass file exists
    if [ ! -f "${SCRIPT_DIR}/.sshpass" ]; then
        echo "ERROR: File ${SCRIPT_DIR}/.sshpass doesn't exist. Create it and save your SSH password to it."
        exit 1
    fi

    # Set up SSH and SCP commands globally using sshpass
    SSH_CMD="sshpass -f ${SCRIPT_DIR}/.sshpass ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no"
    SCP_CMD="sshpass -f ${SCRIPT_DIR}/.sshpass scp -P ${SSH_PORT} -o StrictHostKeyChecking=no"
}

# Deploy kernel to remote device
kernel_deploy() {
    echo "=============================================================================="
    echo "Deploying Kernel ${OS_PREFIX} to ${SSH_USER}@${SSH_HOST}"
    echo "=============================================================================="
    
    echo "-> 1. Preparing remote temporary staging area: ${REMOTE_TEMP_DIR}"
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "rm -rf ${REMOTE_TEMP_DIR} && mkdir -p ${REMOTE_TEMP_DIR}"

    echo "-> 2. Transferring kernel image, device trees, overlays and loadable kernel modules..."
    ${SCP_CMD} -r "${DIST_DIR}" "${SSH_USER}@${SSH_HOST}:${REMOTE_TEMP_DIR}/"
    
    echo "-> 3. Installing files on the Raspberry Pi (Requires sudo privileges on remote)..."
    
    # -------------------------------------------------------------------------
    # MODULE INSTALLATION (SSH vs SD Card):
    # In the official RPi docs (SD card method), this is where you would see:
    # "sudo env PATH=$PATH make INSTALL_MOD_PATH=mnt/root modules_install"
    #
    # Because we deploy over SSH, make.sh already safely extracted these 
    # modules into our local dist/ folder without needing sudo. 
    # Here, we simply move those pre-extracted modules into the Pi's live /lib/modules/
    # -------------------------------------------------------------------------
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "
        cd ${REMOTE_TEMP_DIR}/${BUILD_DIR_NAME}/modules/lib/modules/ && \
        for dir in *; do \
            if [ -d \"\$dir\" ]; then \
                echo '$(cat .sshpass)' | sudo -S rm -rf \"/lib/modules/\$dir\"; \
            fi; \
        done
    "
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S cp -r ${REMOTE_TEMP_DIR}/${BUILD_DIR_NAME}/modules/lib/modules/* /lib/modules/"
    
    # Remove any existing os_prefix directory and recreate it to ensure a clean slate
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S rm -rf ${REMOTE_BOOT_DIR}/${OS_PREFIX} && echo '$(cat .sshpass)' | sudo -S mkdir -p ${REMOTE_BOOT_DIR}/${OS_PREFIX}"

    # Install boot files (image, dtbs, overlays) to the isolated os_prefix directory
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S cp -r ${REMOTE_TEMP_DIR}/${BUILD_DIR_NAME}/boot/* ${REMOTE_BOOT_DIR}/${OS_PREFIX}"

    # If the overlays directory is missing (which happens when building pure mainline kernels),
    # borrow the factory overlays from the Raspberry Pi OS.
    ${SSH_CMD} -t "${SSH_USER}@${SSH_HOST}" "
        if [ ! -d ${REMOTE_BOOT_DIR}/${OS_PREFIX}/overlays ]; then
            echo '   Notice: overlays directory missing in build. Borrowing factory overlays from Pi OS...'
            echo '$(cat .sshpass)' | sudo -S cp -r ${REMOTE_BOOT_DIR}/overlays ${REMOTE_BOOT_DIR}/${OS_PREFIX}
        elif [ -z \"\$(ls -A ${REMOTE_BOOT_DIR}/${OS_PREFIX}/overlays 2>/dev/null)\" ]; then
            echo '   Notice: overlays directory exists but has no files. Borrowing factory overlays from Pi OS...'
            echo '$(cat .sshpass)' | sudo -S cp -r ${REMOTE_BOOT_DIR}/overlays/* ${REMOTE_BOOT_DIR}/${OS_PREFIX}/overlays/
        fi
    "
    
    echo "-> Cleaning up remote temporary files..."
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "rm -rf ${REMOTE_TEMP_DIR}"

    echo "=============================================================================="
    echo "Deployment Successful!"
    echo "Your new kernel has been installed."
    echo "Before reboot make sure that the dual-boot and the right kernel is selected."
    echo "After the Raspberry Pi (sudo reboot), run 'uname -r' to verify active kernel."
    echo "=============================================================================="
}

# Make sure to check config.env before running this utility as it will modify cmdline.txt of the kernel
kernel_boot_type_update() {
    # Ensure dual-boot config and boot parameters are set up
    echo "-> Configuring Boot parameters..."
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "
        # Extract base command line parameters safely
        BASE_CMDLINE=\$(cat ${REMOTE_BOOT_DIR}/cmdline.txt | sed -e 's/isolcpus=[^ ]*//g' -e 's/rcu_nocbs=[^ ]*//g' -e 's/nohz_full=[^ ]*//g' -e 's/irqaffinity=[^ ]*//g' -e 's/dwc_otg.fiq_enable=0//g' -e 's/dwc_otg.fiq_fsm_enable=0//g' | xargs)
        
        # Create the appropriate cmdline.txt inside the os_prefix folder
        BOOT_FLAGS=\"\"
        if [ \"${ENABLE_ISOLATION}\" = \"true\" ]; then
            BOOT_FLAGS=\"isolcpus=3 rcu_nocbs=3 nohz_full=3 irqaffinity=0,1,2\"
        fi
        
        # Append downstream-specific RT overrides if running RT on downstream
        if [ \"${ENABLE_RT}\" = \"true\" ]; then
            BOOT_FLAGS=\"\$BOOT_FLAGS dwc_otg.fiq_enable=0 dwc_otg.fiq_fsm_enable=0\"
        fi
        
        if [ -n \"\$BOOT_FLAGS\" ]; then
            echo \"\$BASE_CMDLINE \$BOOT_FLAGS\" > /tmp/cmdline.txt
        else
            echo \"\$BASE_CMDLINE\" > /tmp/cmdline.txt
        fi
        echo '$(cat .sshpass)' | sudo -S bash -c \"cat /tmp/cmdline.txt > ${REMOTE_BOOT_DIR}/${OS_PREFIX}/cmdline.txt && rm -f /tmp/cmdline.txt\"
    "
}

# Create remote helper files which will be copied to remote target
dual_boot_helpers_deploy() {
    local helper_remote_dir="${SCRIPT_DIR}/helper_remote"

    # Check if folder exist
    if [ ! -d "${helper_remote_dir}" ]; then
        echo "Folder ${helper_remote_dir} is missing. Creating it..."
        mkdir -p "${helper_remote_dir}"
    fi

    # Generate the IRQ Pinning script
    cat << 'EOF' > "${helper_remote_dir}/${PIN_USB_IRQ_NAME}.sh"
#!/bin/bash
# ==============================================================================
# IRQ Offloading & Network Steering Helper
# ==============================================================================

# 1. Configure Receive Packet Steering (RPS) to offload network stack processing to CPU1
RPS_PATH="/sys/class/net/eth0/queues/rx-0/rps_cpus"
if [ -f "$RPS_PATH" ]; then
    # 2 is the hex bitmask for CPU1 (0b0010)
    if echo 2 2>/dev/null > "$RPS_PATH"; then
        echo "Successfully configured RPS for eth0 to CPU1"
    else
        echo "WARNING: Failed to configure RPS for eth0"
    fi
else
    echo "Notice: eth0 RPS queue not found"
fi

# 2. Set USB/Ethernet hardware IRQ affinity to CPU0 only (mask 1)
IRQ=$(grep -E 'dwc2|dwc_otg' /proc/interrupts | awk '{print $1}' | tr -d ':')
if [ -n "$IRQ" ]; then
    # 1 is the hex bitmask for CPU0 (0b0001)
    if echo 1 2>/dev/null > /proc/irq/$IRQ/smp_affinity; then
        echo "Set USB/Eth IRQ $IRQ smp_affinity to CPU0 (mask 1)"
    else
        echo "WARNING: Failed to set smp_affinity for USB/Eth IRQ $IRQ (this is a hardware limitation on BCM2837/dwc2)"
    fi
else
    echo "Could not find dwc2/dwc_otg IRQ"
fi

# 3. Pin all threaded IRQ threads to CPU2 (CPU index 2)
# These threads exist on RT kernels (or baseline booted with threadirqs)
PINNED_COUNT=0
for pid in $(pgrep -f 'irq/[0-9]+-'); do
    if taskset -cp 2 "$pid" >/dev/null 2>&1; then
        PINNED_COUNT=$((PINNED_COUNT + 1))
    fi
done

if [ "$PINNED_COUNT" -gt 0 ]; then
    echo "Successfully pinned $PINNED_COUNT threaded IRQ workers to CPU2"
else
    echo "Notice: No threaded IRQ workers found to pin (running standard baseline kernel?)"
fi
EOF

    # Create the systemd service for IRQ Pinning
    # Note: Using unquoted EOF to expand local bash variables during file creation
    cat << EOF > "${helper_remote_dir}/${PIN_USB_IRQ_NAME}.service"
[Unit]
Description=IRQ Offloading & Network Steering Helper
After=network.target

[Service]
Type=oneshot
ExecStart=${PIN_USB_IRQ_REMOTE_PATH}
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

    # Generate the switch-kernel tool
    # Note: Escaping $1 so it passes through to the bash script, but letting 
    # ${REMOTE_BOOT_DIR} and ${PIN_USB_IRQ_NAME} expand automatically!
    cat << EOF > "${helper_remote_dir}/${SWITCH_KERNEL_NAME}.sh"
#!/bin/bash

if [ -z "\$1" ]; then
    echo "Usage: sudo switch-kernel [prefix_name|default]"
    echo "Example: sudo switch-kernel 6.18.13-rt"
    exit 1
fi

# Strip any existing os_prefix or custom kernel definitions to ensure a clean slate
sed -i '/^os_prefix=/d' ${REMOTE_BOOT_DIR}/config.txt
sed -i '/^kernel=/d' ${REMOTE_BOOT_DIR}/config.txt

if [ "\$1" == "default" ]; then
    systemctl disable ${PIN_USB_IRQ_NAME}.service
    echo "Switched to Factory Default kernel. Reboot to apply."
else
    PREFIX_DIR="${REMOTE_BOOT_DIR}/\$1"
    if [ ! -d "\$PREFIX_DIR" ]; then
        echo "ERROR: Kernel prefix directory '\$PREFIX_DIR' does not exist!"
        exit 1
    fi
    
    echo "os_prefix=\$1/" >> ${REMOTE_BOOT_DIR}/config.txt
    
    # Automatically enable IRQ offloading if the target kernel's cmdline.txt contains isolcpus or irqaffinity
    if grep -qE "isolcpus|irqaffinity" "\${PREFIX_DIR}/cmdline.txt" 2>/dev/null; then
        systemctl enable ${PIN_USB_IRQ_NAME}.service
        echo "Switched to kernel (\$1). Isolation detected -> IRQ Pinning & RPS ENABLED. Reboot to apply."
    else
        systemctl disable ${PIN_USB_IRQ_NAME}.service
        echo "Switched to kernel (\$1). No isolation -> IRQ Pinning & RPS DISABLED. Reboot to apply."
    fi
fi
EOF

    # Make sh files executable
    chmod +x "${helper_remote_dir}/${PIN_USB_IRQ_NAME}.sh"
    chmod +x "${helper_remote_dir}/${SWITCH_KERNEL_NAME}.sh"

    echo
    read -p "Would you like to force-update dual-boot helper files? (Y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
        # SCP runs as a normal user and cannot write directly to /usr/local/bin or /etc/
        # We must copy to a /tmp/ folder first, then use SSH with sudo to move them!
        ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "mkdir -p /tmp/helper_remote"
        ${SCP_CMD} -r "${helper_remote_dir}/"* "${SSH_USER}@${SSH_HOST}:/tmp/helper_remote/"
        
        ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "
            echo '$(cat .sshpass)' | sudo -S mv -f /tmp/helper_remote/${PIN_USB_IRQ_NAME}.sh ${PIN_USB_IRQ_REMOTE_PATH}
            echo '$(cat .sshpass)' | sudo -S mv -f /tmp/helper_remote/${PIN_USB_IRQ_NAME}.service /etc/systemd/system/
            echo '$(cat .sshpass)' | sudo -S mv -f /tmp/helper_remote/${SWITCH_KERNEL_NAME}.sh ${SWITCH_KERNEL_REMOTE_PATH}
            echo '$(cat .sshpass)' | sudo -S systemctl daemon-reload
            rm -rf /tmp/helper_remote
        "
        
        echo "✓ Helper files updated in paths:"
        echo "  ${PIN_USB_IRQ_REMOTE_PATH}"
        echo "  /etc/systemd/system/${PIN_USB_IRQ_NAME}.service"
        echo "  ${SWITCH_KERNEL_REMOTE_PATH}"

        echo "=============================================================================="
        echo "Dual-Boot configured Successful!"
        echo "Selec the new kernel with ${SWITCH_KERNEL_NAME} option."
        echo "   bash install.sh ${SWITCH_KERNEL_NAME}"
        echo "Reboot the Raspberry Pi (sudo reboot) and run 'uname -r' to verify."
        echo "=============================================================================="
    else
        echo "=============================================================================="
        echo "Dual-Boot left unchanged!"
        echo "=============================================================================="
    fi
}

# ==============================================================================
# 3. MAIN LOGIC
# ==============================================================================
main() {
    COMMAND="${1:-kernel-deploy}"

    environment_var

    case "${COMMAND}" in
        kernel-deploy)
            kernel_deploy
            kernel_boot_type_update
            ;;
        kernel-boot-update)
            kernel_boot_type_update
            ;;
        dual-boot-helpers)
            dual_boot_helpers_deploy
            ;;
        switch-kernel)
            echo
            read -p "To what kernel the switch is desired? (d/b/r) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[d]$ ]]; then
                echo "-> Activating default kernel..."
                ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S ${SWITCH_KERNEL_NAME}.sh default"
            elif [[ $REPLY =~ ^[b]$ ]]; then
                echo "-> Activating baseline kernel..."
                ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S ${SWITCH_KERNEL_NAME}.sh ${KERNEL_VERSION_MAJOR_MINOR}.${KERNEL_VERSION_PATCH}-baseline"
            elif [[ $REPLY =~ ^[r]$ ]]; then
                echo "-> Activating rt kernel..."
                ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "echo '$(cat .sshpass)' | sudo -S ${SWITCH_KERNEL_NAME}.sh ${KERNEL_VERSION_MAJOR_MINOR}.${KERNEL_VERSION_PATCH}-rt"
            else
                echo "Unknown command $REPLY."
                echo "Ending script..."
            fi
            ;;
        *)
            echo "Usage: $0 [kernel-deploy|kernel-boot-update|dual-boot-helpers|switch-kernel]"
            echo "  kernel-deploy      - Install/copy build kernel modules, dtb and img to remote target and update boot parameters."
            echo "  kernel-boot-update - Update boot parameters (cmdline.txt) on remote target based on configuration."
            echo "  dual-boot-helpers  - Checks if dual-boot is configured. If it is missing it will be set up."
            echo "  ${SWITCH_KERNEL_NAME}      - Switch to desired kernel. A pop up will appear requesting an input [d|b|r]."
            exit 1
            ;;
    esac
}

main "$@"
