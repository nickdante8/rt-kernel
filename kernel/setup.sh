#!/bin/bash

# ==============================================================================
# 1. SETTINGS & GLOBALS
# ==============================================================================
# Exit immediately if a command exits with a non-zero status
set -e

# --- AUTOMATIC PATH SETTING ---
# Determine the directory where this script resides
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"
CONFIG_FILE="${SCRIPT_DIR}/config.env"

# Check host dependencies
echo "Checking required host dependencies..."
REQUIRED_PKGS=(
    "git"
    "bc"
    "bison"
    "flex"
    "libssl-dev"
    "make"
    "gcc-aarch64-linux-gnu"
    "g++-aarch64-linux-gnu"
    "libncurses-dev"
    "libelf-dev"
    "rsync"
    "tar"
)

MISSING_PKGS=()


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
# Load environment variable of the script
environment_var() {
    # Load config.env
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
    if [ -z "${BUILD_DIR}" ] || [ -z "${KERNEL_REPO}" ] || [ -z "${KERNEL_BRANCH}" ]; then
        echo "ERROR: Required variables (BUILD_DIR, KERNEL_REPO, KERNEL_BRANCH) are not set in config.env."
        exit 1
    fi

    echo "Setting up build environment for board: ${TARGET_BOARD:-rpi3bplus}"
    echo "Kernel branch: ${KERNEL_BRANCH}"
    echo "Target Architecture: ${ARCH}"
    echo "Cross-compiler prefix: ${CROSS_COMPILE}"
    echo "=============================================================================="
}

check_dependencies() {
    # Software dependencies
    local -n required_pkg=$1
    local -n missing_pkg=$2

    for pkg in "${required_pkg[@]}"; do
        if ! dpkg -l | grep -q "ii  $pkg " &>/dev/null && ! which "$pkg" &>/dev/null; then
            # Double check with dpkg-query to be more accurate on Debian/Ubuntu/Mint
            if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "ok installed"; then
                missing_pkg+=("$pkg")
            fi
        fi
    done

    if [ ${#missing_pkg[@]} -ne 0 ]; then
        echo "The following host dependencies are missing: ${missing_pkg[*]}"
        echo "You can install them by running:"
        echo "  sudo apt-get update && sudo apt-get install -y ${missing_pkg[*]}"
        echo
        read -p "Would you like to run this installation command now? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            sudo apt-get update && sudo apt-get install -y "${missing_pkg[@]}"
        else
            echo "Aborting. Please install missing packages manually before running setup again."
            exit 1
        fi
    else
        echo "✓ All host dependencies are installed."
    fi
}

kenel_dependencies() {
    echo "=============================================================================="

    # 3. Clone or Update the Kernel Source
    if [ ! -d "${BUILD_DIR}" ]; then
        echo "Kernel source directory not found at: ${BUILD_DIR}"
        echo "Cloning repository: ${KERNEL_REPO}"
        echo "Branch: ${KERNEL_BRANCH} (Depth: ${KERNEL_DEPTH})"
        
        # We run git clone. Depth 1 saves a lot of space and time.
        git clone --branch "${KERNEL_BRANCH}" --depth "${KERNEL_DEPTH}" "${KERNEL_REPO}" "${BUILD_DIR}"
        echo "✓ Cloned successfully."
    else
        echo "Kernel source directory already exists at: ${BUILD_DIR}"
        
        # Verify it is a valid git repository
        if ! git -C "${BUILD_DIR}" rev-parse --is-inside-work-tree &>/dev/null; then
            echo "ERROR: Directory ${BUILD_DIR} exists but is not a valid Git repository."
            echo "Please delete or move it and re-run this script."
            exit 1
        fi

        # Check current branch
        CURRENT_BRANCH=$(git -C "${BUILD_DIR}" branch --show-current 2>/dev/null || git -C "${BUILD_DIR}" rev-parse --abbrev-ref HEAD)
        
        if [ "${CURRENT_BRANCH}" = "${KERNEL_BRANCH}" ]; then
            echo "✓ Git repository is on the correct branch: ${KERNEL_BRANCH}"
            read -p "Would you like to pull the latest updates for this branch? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "Pulling latest changes..."
                git -C "${BUILD_DIR}" pull
            fi
        else
            echo "WARNING: Repository is currently on branch '${CURRENT_BRANCH}', but config.env specifies '${KERNEL_BRANCH}'."
            read -p "Would you like to switch to '${KERNEL_BRANCH}'? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                echo "Fetching branch '${KERNEL_BRANCH}'..."
                # Try to fetch branch in case it doesn't exist locally
                git -C "${BUILD_DIR}" fetch origin "${KERNEL_BRANCH}":"${KERNEL_BRANCH}" --depth "${KERNEL_DEPTH}" || true
                echo "Checking out '${KERNEL_BRANCH}'..."
                git -C "${BUILD_DIR}" checkout "${KERNEL_BRANCH}"
            else
                echo "Remaining on current branch. Note that compilation might not target the configured version."
            fi
        fi
    fi

    echo "=============================================================================="
    echo "Setup complete! You can now configure the kernel by running:"
    echo "  ./configure.sh"
    echo "=============================================================================="
}

# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v 

    environment_var
    check_dependencies REQUIRED_PKGS MISSING_PKGS
    exit 1
    kernel_dependencies
}

# Invoke main
main "$@"