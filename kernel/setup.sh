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
    "libc6-dev"
    "libncurses-dev"
    "crossbuild-essential-arm64"
    "libelf-dev"
    "rsync"
    "tar"
    "wget"
    "patch"
    "xz-utils"
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
    if [ -z "${BUILD_DIR_PATH}" ] || [ -z "${KERNEL_REPO}" ] || [ -z "${KERNEL_BRANCH}" ]; then
        echo "ERROR: Required variables (BUILD_DIR_PATH, KERNEL_REPO, KERNEL_BRANCH) are not set in config.env."
        exit 1
    fi

    echo "Setting up build environment for board: ${TARGET_BOARD:-rpi3bplus}"
    echo "Kernel branch: ${KERNEL_BRANCH}"
    echo "Target Architecture: ${ARCH}"
    echo "Cross-compiler prefix: ${CROSS_COMPILE}"
    echo "=============================================================================="
}

# Check package dependencies
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

# Get kernel dependencies is they are missing
kernel_dependencies() {
    echo "=============================================================================="

    # Get a specific kenel revision. It is important in case of a need
    # to apply a patch which is not available for the latest kernel version
    # Make sure to find for the specific kernel version in git commits.
    if [ -n "${KERNEL_REVISION}" ]; then
        echo "Using specific kernel revision: ${KERNEL_REVISION}"
        if [ ! -d "${BUILD_DIR_PATH}" ]; then
            echo "Kernel source directory not found at: ${BUILD_DIR_PATH}"
            echo "Initializing git repository and fetching revision..."
            mkdir -p "${BUILD_DIR_PATH}"
            git -C "${BUILD_DIR_PATH}" init
            git -C "${BUILD_DIR_PATH}" remote add origin "${KERNEL_REPO}"
            git -C "${BUILD_DIR_PATH}" fetch --depth 1 origin "${KERNEL_REVISION}"
            git -C "${BUILD_DIR_PATH}" checkout FETCH_HEAD
            echo "✓ Checked out revision successfully."
        else
            echo "Kernel source directory already exists at: ${BUILD_DIR_PATH}"
            # Verify it is a valid git repository
            if ! git -C "${BUILD_DIR_PATH}" rev-parse --is-inside-work-tree &>/dev/null; then
                echo "ERROR: Directory ${BUILD_DIR_PATH} exists but is not a valid Git repository."
                echo "Please delete or move it and re-run this script."
                exit 1
            fi
            
            # Check if current commit matches KERNEL_REVISION
            local current_commit
            current_commit=$(git -C "${BUILD_DIR_PATH}" rev-parse HEAD 2>/dev/null || true)
            if [ "${current_commit}" = "${KERNEL_REVISION}" ]; then
                echo "✓ Git repository is already at the correct revision: ${KERNEL_REVISION}"
            else
                echo "Repository is at commit '${current_commit}', but config.env specifies '${KERNEL_REVISION}'."
                read -p "Would you like to fetch and switch to '${KERNEL_REVISION}'? (y/N) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    git -C "${BUILD_DIR_PATH}" fetch --depth 1 origin "${KERNEL_REVISION}"
                    git -C "${BUILD_DIR_PATH}" checkout FETCH_HEAD
                    echo "✓ Switched to revision successfully."
                fi
            fi
        fi
    else
        # Clone or Update the Kernel Source based on KERNEL_BRANCH
        if [ ! -d "${BUILD_DIR_PATH}" ]; then
            echo "Kernel source directory not found at: ${BUILD_DIR_PATH}"
            echo "Cloning repository: ${KERNEL_REPO}"
            echo "Branch: ${KERNEL_BRANCH} (Depth: ${KERNEL_DEPTH})"
            echo "<4> WARNING: If kernel headers are required separately, install them by running 'sudo apt install linux-headers-rpi-v8'. \
                Check https://www.raspberrypi.com/documentation/computers/linux_kernel.html#kernel-headers for more info."
            
            # We run git clone. Depth 1 saves a lot of space and time.
            git clone --branch "${KERNEL_BRANCH}" --depth "${KERNEL_DEPTH}" "${KERNEL_REPO}" "${BUILD_DIR_PATH}"
            echo "✓ Cloned successfully."
        else
            echo "Kernel source directory already exists at: ${BUILD_DIR_PATH}"
            
            # Verify it is a valid git repository
            if ! git -C "${BUILD_DIR_PATH}" rev-parse --is-inside-work-tree &>/dev/null; then
                echo "ERROR: Directory ${BUILD_DIR_PATH} exists but is not a valid Git repository."
                echo "Please delete or move it and re-run this script."
                exit 1
            fi

            # Check current branch
            CURRENT_BRANCH=$(git -C "${BUILD_DIR_PATH}" branch --show-current 2>/dev/null || git -C "${BUILD_DIR_PATH}" rev-parse --abbrev-ref HEAD)
            
            if [ "${CURRENT_BRANCH}" = "${KERNEL_BRANCH}" ]; then
                echo "✓ Git repository is on the correct branch: ${KERNEL_BRANCH}"
                read -p "Would you like to pull the latest updates for this branch? (y/N) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    echo "Pulling latest changes..."
                    git -C "${BUILD_DIR_PATH}" pull
                fi
            else
                echo "WARNING: Repository is currently on branch '${CURRENT_BRANCH}', but config.env specifies '${KERNEL_BRANCH}'."
                read -p "Would you like to switch to '${KERNEL_BRANCH}'? (y/N) " -n 1 -r
                echo
                if [[ $REPLY =~ ^[Yy]$ ]]; then
                    echo "Fetching branch '${KERNEL_BRANCH}'..."
                    # Try to fetch branch in case it doesn't exist locally
                    git -C "${BUILD_DIR_PATH}" fetch origin "${KERNEL_BRANCH}":"${KERNEL_BRANCH}" --depth "${KERNEL_DEPTH}" || true
                    echo "Checking out '${KERNEL_BRANCH}'..."
                    git -C "${BUILD_DIR_PATH}" checkout "${KERNEL_BRANCH}"
                else
                    echo "Remaining on current branch. Note that compilation might not target the configured version."
                fi
            fi
        fi
    fi

    # Verify kernel version matches patch version if patching is enabled
    if [ "${DOWNLOAD_RT_PATCH}" = "true" ]; then
        if [ ! -f "${BUILD_DIR_PATH}/Makefile" ]; then
            echo "ERROR: Makefile not found in ${BUILD_DIR_PATH}. Source check-out seems incomplete."
            exit 1
        fi
        local k_ver
        local k_pat
        local k_sub
        k_ver=$(grep -E "^VERSION =" "${BUILD_DIR_PATH}/Makefile" | awk '{print $3}')
        k_pat=$(grep -E "^PATCHLEVEL =" "${BUILD_DIR_PATH}/Makefile" | awk '{print $3}')
        k_sub=$(grep -E "^SUBLEVEL =" "${BUILD_DIR_PATH}/Makefile" | awk '{print $3}')
        local checked_out_version="${k_ver}.${k_pat}.${k_sub}"
        
        # Extract version from RT_PATCH_FILE (e.g. patch-6.18.13-rt4.patch.xz)
        local patch_version
        patch_version=$(echo "${RT_PATCH_FILE}" | sed -E 's/patch-([0-9]+\.[0-9]+\.[0-9]+)-rt[0-9]+\.patch\.xz/\1/')
        
        echo "Verifying version matching..."
        echo "  Checked out kernel: ${checked_out_version}"
        echo "  RT patch version:   ${patch_version}"
        
        if [ "${checked_out_version}" != "${patch_version}" ]; then
            echo "ERROR: Kernel version (${checked_out_version}) does not match the RT patch version (${patch_version})."
            echo "Please check config.env settings (KERNEL_REVISION, KERNEL_BRANCH, and RT_PATCH_FILE)."
            exit 1
        else
            echo "✓ Kernel version matches RT patch version."
        fi

        # RT Patch download and application
        echo "=============================================================================="
        local patch_local_path="${SCRIPT_DIR}/${RT_PATCH_FILE}"
        if [ ! -f "${patch_local_path}" ]; then
            echo "Downloading RT patch from ${RT_PATCH_URL}..."
            wget -O "${patch_local_path}" "${RT_PATCH_URL}"
            echo "✓ RT patch downloaded successfully."
        else
            echo "✓ RT patch already downloaded at: ${patch_local_path}"
        fi
        
        if [ -d "${BUILD_DIR_PATH}" ]; then
            echo "Checking if RT patch needs to be applied..."
            # Configure git identity locally to avoid patch commit failure
            git -C "${BUILD_DIR_PATH}" config user.name "RT Build System"
            git -C "${BUILD_DIR_PATH}" config user.email "rt-build@localhost"

            # Check if patch is already applied (via git commit message)
            if git -C "${BUILD_DIR_PATH}" log -n 5 --format="%s" 2>/dev/null | grep -q "Apply PREEMPT_RT patch"; then
                echo "✓ RT patch is already applied to git history."
            else
                echo "Applying RT patch to the kernel source tree..."
                # Check if it applies cleanly via git apply
                if xzcat "${patch_local_path}" | git -C "${BUILD_DIR_PATH}" apply --check - &>/dev/null; then
                    xzcat "${patch_local_path}" | git -C "${BUILD_DIR_PATH}" apply -
                    git -C "${BUILD_DIR_PATH}" add .
                    git -C "${BUILD_DIR_PATH}" commit -m "Apply PREEMPT_RT patch: ${RT_PATCH_FILE}"
                    echo "✓ RT patch applied and committed successfully."
                else
                    echo "WARNING: Git apply check failed. Attempting with standard patch command..."
                    if xzcat "${patch_local_path}" | patch -p1 -d "${BUILD_DIR_PATH}" --dry-run &>/dev/null; then
                        xzcat "${patch_local_path}" | patch -p1 -d "${BUILD_DIR_PATH}"
                        git -C "${BUILD_DIR_PATH}" add .
                        git -C "${BUILD_DIR_PATH}" commit -m "Apply PREEMPT_RT patch: ${RT_PATCH_FILE} (using patch utility)"
                        echo "✓ RT patch applied and committed successfully using patch utility."
                    else
                        echo "ERROR: RT patch does not apply cleanly to the selected branch."
                        echo "This is expected if your branch version (${KERNEL_BRANCH}) differs from the patch version (${RT_PATCH_FILE})."
                        echo "Please manually resolve conflicts or turn off DOWNLOAD_RT_PATCH in config.env."
                        exit 1
                    fi
                fi
            fi
        fi
    fi
}

# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v 

    environment_var
    check_dependencies REQUIRED_PKGS MISSING_PKGS
    kernel_dependencies

    echo "=============================================================================="
    echo "Setup complete! You can now configure the kernel by running:"
    echo "  ./configure.sh"
    echo "=============================================================================="
}

# Invoke main
main "$@"
