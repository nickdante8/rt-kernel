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

    echo "=============================================================================="
    # Check configuration variables
    if [ -z "${BUILD_DIR_PATH}" ] || [ -z "${ARCH}" ] || [ -z "${CROSS_COMPILE}" ] || [ -z "${KERNEL_NAME}" ]; then
        echo "ERROR: Required variables missing in config.env."
        exit 1
    fi

    # Export KERNEL as required by the RPi build process
    export KERNEL="${KERNEL_NAME}"

    if [ ! -f "${BUILD_DIR_PATH}/.config" ]; then
        echo "ERROR: Kernel is not configured. .config file is missing."
        echo "Please run ./configure.sh first."
        exit 1
    fi
}

# Build the kernel
build_kernel() {
    echo "=============================================================================="
    echo "Starting Kernel Compilation"
    echo "Target Directory: ${BUILD_DIR_PATH}"
    echo "Parallel Jobs: ${BUILD_JOBS}"
    echo "=============================================================================="

    # The actual compilation command that triggers the C compiler
    make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" -j"${BUILD_JOBS}" Image modules dtbs

    echo "✓ Compilation finished successfully."
}

# Location where to save the results of the build
package_artifacts() {
    echo "=============================================================================="
    echo "Packaging build artifacts into local distribution folder..."
    
    DIST_DIR="${SCRIPT_DIR}/dist/${BUILD_DIR_NAME}"
    
    # Clean up previous distribution folder
    rm -rf "${DIST_DIR}"
    mkdir -p "${DIST_DIR}/boot/overlays"
    mkdir -p "${DIST_DIR}/modules"

    # 1. Copy the Kernel Image
    echo "-> Staging Kernel Image (${KERNEL_IMG_NAME})..."
    cp "${BUILD_DIR_PATH}/arch/arm64/boot/Image" "${DIST_DIR}/boot/${KERNEL_IMG_NAME}"

    # 2. Copy Device Tree Blobs (dtbs)
    echo "-> Staging dtbs and overlays..."
    # RPi dtbs are specifically in the broadcom/ folder for arm64
    cp "${BUILD_DIR_PATH}/arch/arm64/boot/dts/broadcom/"*.dtb "${DIST_DIR}/boot/" || true
    cp "${BUILD_DIR_PATH}/arch/arm64/boot/dts/overlays/"*.dtb* "${DIST_DIR}/boot/overlays/" || true
    cp "${BUILD_DIR_PATH}/arch/arm64/boot/dts/overlays/README" "${DIST_DIR}/boot/overlays/" || true

    # 3. Install Kernel Modules into the staging area
    echo "-> Staging loadable kernel modules..."
    make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" INSTALL_MOD_PATH="${DIST_DIR}/modules" modules_install

    echo "=============================================================================="
    echo "Artifacts successfully packaged!"
    echo "Distribution directory: ${DIST_DIR}"
    echo "The kernel is now ready to be deployed to the Raspberry Pi."
    echo "Next step: Review/Run ./install.sh"
    echo "=============================================================================="
}

# ==============================================================================
# 3. MAIN LOGIC
# ==============================================================================
main() {
    COMMAND="${1:-make}"

    environment_var

    case "${COMMAND}" in
        build|make)
            build_kernel
            package_artifacts
            ;;
        clean)
            echo "=============================================================================="
            echo "Cleaning Kernel Build..."
            echo "=============================================================================="
            make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" clean
            DIST_DIR="${SCRIPT_DIR}/dist/${BUILD_DIR_NAME}"
            rm -rf "${DIST_DIR}"
            echo "✓ Cleaned build directory and removed ${DIST_DIR}"
            ;;
        distclean)
            echo "=============================================================================="
            echo "Deep Cleaning Kernel Build (mrproper)..."
            echo "=============================================================================="
            make -C "${BUILD_DIR_PATH}" ARCH="${ARCH}" CROSS_COMPILE="${CROSS_COMPILE}" mrproper
            DIST_DIR="${SCRIPT_DIR}/dist/${BUILD_DIR_NAME}"
            rm -rf "${DIST_DIR}"
            echo "✓ Deep cleaned build directory (Note: This deletes .config!)"
            ;;
        *)
            echo "Usage: $0 [make|build|clean|distclean]"
            echo "  make|build - Compiles the kernel and packages it (Default)"
            echo "  clean      - Cleans the build environment but keeps .config"
            echo "  distclean  - Deep cleans the environment (Deletes .config!)"
            exit 1
            ;;
    esac
}

main "$@"
