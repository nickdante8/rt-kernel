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
}

# Deploy kernel to remote device
deploy_kernel() {
    echo "=============================================================================="
    echo "Deploying Kernel to ${SSH_USER}@${SSH_HOST}"
    echo "=============================================================================="

    # Set up SSH and SCP commands with the specified port
    SSH_CMD="ssh -p ${SSH_PORT}"
    SCP_CMD="scp -P ${SSH_PORT}"
    
    echo "-> 1. Preparing remote temporary staging area: ${REMOTE_TEMP_DIR}"
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "rm -rf ${REMOTE_TEMP_DIR} && mkdir -p ${REMOTE_TEMP_DIR}"

    echo "-> 2. Transferring kernel image, device trees, and overlays..."
    ${SCP_CMD} -r "${DIST_DIR}/boot" "${SSH_USER}@${SSH_HOST}:${REMOTE_TEMP_DIR}/"
    
    echo "-> 3. Transferring loadable kernel modules..."
    ${SCP_CMD} -r "${DIST_DIR}/modules" "${SSH_USER}@${SSH_HOST}:${REMOTE_TEMP_DIR}/"

    echo "-> 4. Installing files on the Raspberry Pi (Requires sudo privileges on remote)..."
    
    # Install modules to /lib/modules
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "sudo cp -r ${REMOTE_TEMP_DIR}/modules/lib/modules/* /lib/modules/"
    
    # Backup existing custom kernel image just in case (we don't backup the default kernel8.img)
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "
        if [ -f ${REMOTE_BOOT_DIR}/${KERNEL_IMG_NAME} ]; then 
            sudo cp ${REMOTE_BOOT_DIR}/${KERNEL_IMG_NAME} ${REMOTE_BOOT_DIR}/${KERNEL_IMG_NAME}.bak
            echo '   (Backed up existing ${KERNEL_IMG_NAME} to ${KERNEL_IMG_NAME}.bak)'
        fi
    "

    # Install boot files (image, dtbs, overlays) to the boot firmware directory
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "sudo cp -r ${REMOTE_TEMP_DIR}/boot/* ${REMOTE_BOOT_DIR}/"

    # Ensure config.txt points to our new kernel
    echo "-> 5. Verifying config.txt boot entry..."
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "
        if ! grep -q '^kernel=${KERNEL_IMG_NAME}' ${REMOTE_BOOT_DIR}/config.txt; then
            echo '   (Adding kernel=${KERNEL_IMG_NAME} to config.txt)'
            echo -e '\n[all]\nkernel=${KERNEL_IMG_NAME}' | sudo tee -a ${REMOTE_BOOT_DIR}/config.txt > /dev/null
        else
            echo '   (kernel=${KERNEL_IMG_NAME} already exists in config.txt)'
        fi
    "

    echo "-> 6. Cleaning up remote temporary files..."
    ${SSH_CMD} "${SSH_USER}@${SSH_HOST}" "rm -rf ${REMOTE_TEMP_DIR}"

    echo "=============================================================================="
    echo "Deployment Successful!"
    echo "Your new kernel has been installed."
    echo "Reboot the Raspberry Pi (sudo reboot) and run 'uname -r' to verify."
    echo "=============================================================================="
}

# ==============================================================================
# 3. MAIN LOGIC
# ==============================================================================
main() {
    environment_var
    deploy_kernel
}

main "$@"
