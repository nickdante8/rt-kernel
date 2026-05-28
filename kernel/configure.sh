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
        echo "Please ensure config.env exists in the same directory as this script."
        exit 1
    fi

    echo "=============================================================================="
    # Check configuration variables
    if [ -z "${BUILD_DIR_PATH}" ] || [ -z "${ARCH}" ] || [ -z "${CROSS_COMPILE}" ] || [ -z "${DEFCONFIG}" ] || [ -z "${KERNEL_NAME}" ]; then
        echo "ERROR: Required variables (BUILD_DIR_PATH, ARCH, CROSS_COMPILE, DEFCONFIG, KERNEL_NAME) are not set in config.env."
        exit 1
    fi

    # Export KERNEL variable as required by Raspberry Pi build process
    export KERNEL="${KERNEL_NAME}"

    if [ ! -d "${BUILD_DIR_PATH}" ]; then
        echo "ERROR: Kernel source directory not found at ${BUILD_DIR_PATH}"
        echo "Please run ./setup.sh first to prepare the kernel source tree."
        exit 1
    fi
}

# For custom configuration arguments to reconfigure some behaviour
argument_parse() {
    # Ensure scripts/config is executable
    CONFIG_CMD="${BUILD_DIR_PATH}/scripts/config"
    if [ ! -f "${CONFIG_CMD}" ]; then
        echo "ERROR: scripts/config utility not found in kernel source tree."
        exit 1
    fi
    chmod +x "${CONFIG_CMD}"

    # Parse command line options
    INTERACTIVE=true
    for arg in "$@"; do
        case $arg in
            --non-interactive|-n)
                INTERACTIVE=false
                shift
                ;;
            *)
                ;;
        esac
    done
}

# Platform configuration
config_platform() {
    echo "-> Hardening platform for RPi 3B+ (BCM2837 / Cortex-A53)..."

    # =====================================================================
    # 1. CRITICAL: CPU & Memory sizing
    # =====================================================================
    # Pi 3B+ has exactly 4 cores
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-val NR_CPUS 4

    # Cortex-A53 supports 48-bit VA / 48-bit PA maximum
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-val ARM64_VA_BITS 48
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-val ARM64_PA_BITS 48

    # =====================================================================
    # 2. RECOMMENDED: Strip non-BCM architectures
    # =====================================================================
    # Keep ONLY Broadcom / BCM2835 platform support
    for arch in ACTIONS AIROHA SUNXI ALPINE APPLE ARTPEC AXIADO BERLIN \
                BLAIZE CIX EXYNOS K3 LG1K HISI KEEMBAY MEDIATEK MESON \
                MICROCHIP SPARX5 MVEBU NXP LAYERSCAPE MXC S32 MA35 NPCM \
                QCOM REALTEK RENESAS ROCKCHIP SEATTLE INTEL_SOCFPGA SOPHGO \
                STM32 SYNQUACER TEGRA TESLA_FSD SPRD THUNDER THUNDER2 \
                UNIPHIER VEXPRESS VISCONTI XGENE ZYNQMP; do
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable "ARCH_${arch}"
    done

    # Also disable non-Pi Broadcom platforms
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable ARCH_BCM_IPROC
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable ARCH_BCMBCA
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable ARCH_BRCMSTB

    # =====================================================================
    # 3. Ensure critical Pi 3B+ drivers are built-in
    # =====================================================================
    # Ethernet - built-in for faster boot (no initramfs dependency)
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable USB_LAN78XX
    
    # Enable FTRACE for latency analysis (cyclictest --breaktrace)
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable FTRACE
    
    # Ensure VC4 GPU driver is available (for HDMI output)
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable DRM_VC4

    # =====================================================================
    # 4. Strip Pi 4/5 specific configs
    # =====================================================================
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable BCM2711_THERMAL
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PINCTRL_BCM2712
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable BCM2712_MIP
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable CLK_BCM2711_DVP

    # Strip enterprise Broadcom clock drivers
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable CLK_BCM_63XX
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable CLK_BCM_NS2
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable CLK_BCM_SR
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable COMMON_CLK_IPROC

    # (Note: DEBUG_INFO is explicitly retained)

    echo "✓ Platform hardened for RPi 3B+."
}

# Kernel configuration
config_kernel() {
    echo "Starting configuration for kernel source at: ${BUILD_DIR_PATH}"
    echo "=============================================================================="

    # Apply Defconfig for default configuration and build the sources and Device Tree files
    echo "Applying base configuration: ${DEFCONFIG}..."
    make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" "${DEFCONFIG}"
    echo "✓ Base configuration applied."

    # Apply Programmatic Tweaks
    echo "Applying RT and stripping options to .config..."

    # Enable EXPERT mode (often required to enable PREEMPT_RT or disable core features)
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable EXPERT

    # Enable High Resolution Timers (critical for precision in both, but essential for RT)
    "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable HIGH_RES_TIMERS

    # Harden the config for the specific target platform
    config_platform

    # PREEMPT_RT and specific Baseline settings
    if [ "${ENABLE_RT}" = "true" ]; then
        echo "-> Configuring for RT (Real-Time)..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable PREEMPT_RT
        
        # Disable standard/conflicting preempt models
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT_NONE
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT_VOLUNTARY
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT
        
        # Timer frequency 1000 Hz for RT
        echo "-> Setting timer frequency to 1000 Hz..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable HZ_1000
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_100
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_250
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_300
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-val HZ 1000
        
        # RCU no-callbacks configuration (often used for isolating cores in RT)
        echo "-> Enabling RCU no-callback support (RCU_NOCB_CPU)..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable RCU_NOCB_CPU
    else
        echo "-> Configuring for Baseline (Non-RT)..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT_RT
        
        # Enable standard preempt (Typical default for Raspberry Pi desktop/baseline)
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable PREEMPT
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT_NONE
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable PREEMPT_VOLUNTARY
        
        # Timer frequency 250 Hz for baseline (Standard trade-off for performance/power)
        echo "-> Setting timer frequency to 250 Hz..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable HZ_250
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_100
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_300
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable HZ_1000
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-val HZ 250
        
        # Disable RCU no-callbacks for standard baseline behavior
        echo "-> Disabling RCU no-callback support..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable RCU_NOCB_CPU
    fi

    # Localversion Suffix
    if [ -n "${LOCALVERSION}" ]; then
        echo "-> Setting LOCALVERSION suffix to: ${LOCALVERSION}"
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-str LOCALVERSION "${LOCALVERSION}"
    fi

    # Subsystem/Driver Stripping
    if [ "${STRIP_WIFI}" = "true" ]; then
        echo "-> Stripping Wi-Fi drivers and stack..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable CFG80211
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable MAC80211
    fi

    if [ "${STRIP_BLUETOOTH}" = "true" ]; then
        echo "-> Stripping Bluetooth drivers and stack..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable BT
    fi

    if [ "${STRIP_SOUND_VIDEO}" = "true" ]; then
        echo "-> Stripping Sound support..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable SOUND
        echo "-> Stripping DRM/Video drivers..."
        "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --disable DRM
    fi

    echo "=============================================================================="
    echo "Resolving configuration dependencies (make olddefconfig)..."
    make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" olddefconfig
    echo "✓ Configuration dependencies resolved."
    echo "=============================================================================="

    # Interactive Configuration (menuconfig)
    if [ "${INTERACTIVE}" = "true" ]; then
        echo "Launching interactive menuconfig..."
        echo "You can make custom tweaks, compare settings, and then save & exit."
        echo "Press Enter to start..."
        read -r
        
        # Launch menuconfig
        make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" menuconfig
    else
        echo "Non-interactive mode requested. Skipping menuconfig."
    fi
}

# Validate the configuration
config_validation() {
    # Validation Step
    echo "=============================================================================="
    echo "Validating configuration..."
    if [ "${ENABLE_RT}" = "true" ]; then
        if ! grep -q "CONFIG_PREEMPT_RT=y" "${BUILD_DIR_PATH}/.config"; then
            echo "WARNING: CONFIG_PREEMPT_RT=y is NOT enabled in .config!"
            echo "This kernel will NOT be compiled with real-time support."
            echo
            read -p "Would you like to force-enable PREEMPT_RT and resolve configs again? (Y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
                "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --enable PREEMPT_RT
                make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" olddefconfig
                echo "✓ Force-enabled PREEMPT_RT and resolved dependencies."
            fi
        else
            echo "✓ PREEMPT_RT is verified as ENABLED."
        fi
    fi

    # Validate LOCALVERSION
    CURRENT_LV=$("${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --state LOCALVERSION || true)
    # The output of --state for strings includes quotes, so strip them
    CURRENT_LV="${CURRENT_LV%\"}"
    CURRENT_LV="${CURRENT_LV#\"}"
    
    if [ "${CURRENT_LV}" != "${LOCALVERSION}" ]; then
        echo "WARNING: LOCALVERSION is set to '${CURRENT_LV}', expected '${LOCALVERSION}'."
        read -p "Would you like to correct this? (Y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]] || [ -z "$REPLY" ]; then
            "${CONFIG_CMD}" --file "${BUILD_DIR_PATH}/.config" --set-str LOCALVERSION "${LOCALVERSION}"
            make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" olddefconfig
        fi
    else
        echo "✓ LOCALVERSION suffix is verified ('${LOCALVERSION}')."
    fi
}

# Back up the configuration
config_backup() {
    # Save Backup
    BACKUP_DIR="${SCRIPT_DIR}/configs"
    mkdir -p "${BACKUP_DIR}"
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    BACKUP_FILE="${BACKUP_DIR}/config-${TIMESTAMP}${LOCALVERSION}"
    cp "${BUILD_DIR_PATH}/.config" "${BACKUP_FILE}"
    ln -sf "config-${TIMESTAMP}" "${BACKUP_DIR}/last_config"
}

# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    environment_var
    argument_parse "$@"
    config_kernel
    config_validation
    config_backup

    echo "=============================================================================="
    echo "Configuration complete!"
    echo "A backup of your configuration has been saved to:"
    echo "  ${BACKUP_FILE}"
    echo "Symlinked to: ${BACKUP_DIR}/last_config"
    echo
    echo "You can now build the kernel by running:"
    echo "  ./make.sh build"
    echo "=============================================================================="
}

# Invoke main
main "$@"