#!/bin/bash

# ==============================================================================
# 1. SETTINGS & GLOBALS
# ==============================================================================
# Exit immediately if a command exits with a non-zero status.
set -e

# --- AUTOMATIC PATH SETTING ---
# This ensures the script always runs inside the folder where it lives
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# Required dependencies
# install pakages true name
INSTALL_PKG=("build-essential" "cmake" "sysstat" "iperf3")
# command name to check if they are available
REQUIRED_PKG=("gcc" "cmake" "pidstat" "iperf3")


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
# Load environment variable of the script
environment_var() {
    echo "--- Starting Environment Setup & Pre-flight Checks ---"
    # --- .env_setup LOADING ---
    # This safely loads the variables from .env_setup without touching other files
    if [ -f "$SCRIPT_DIR/.env_setup" ]; then
        set -a
        source "$SCRIPT_DIR/.env_setup"
        set +a
        echo "[✔] Environment variables loaded."
    else
        echo "[!] No .env_setup file found. Using defaults."
    fi
}

# Checks if a list of packages is installed and installs missing ones.
# Arguments: None
check_dependencies() {
    # Software dependencies
    local -n _required_ref=$1
    local -n _install_ref=$2
    local missing_pkg=()

    # Check for missing packages
    for i in "${!_required_ref[@]}"; do
        local cmd="${_required_ref[$i]}"
        local pkg="${_install_ref[$i]}"

        if ! command -v "$cmd" &> /dev/null; then
            echo "[!] Missing: $cmd (Requires: $pkg)"
            missing_pkg+=("$pkg")
        fi
    done

    # Install missing ones if any
    if [ ${#missing_pkg[@]} -gt 0 ]; then
        echo "The following packages are missing: ${missing_pkg[*]}"
        echo "Updating caches..."
        sudo apt update

        echo "Installing missing packages..."
        sudo apt install -y "${missing_pkg[@]}"
    else
        echo "All dependencies are satified."
    fi
}


# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v 
    
    environment_var
    check_dependencies REQUIRED_PKG INSTALL_PKG

    echo -e "\n[✔] Setup complete. System ready."
}

# Invoke main
main "$@"
