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
REQUIRED_PKG=("python3" "pip3" "sshpass" "iperf3")


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

    # --- Variable Checks ---
    # Ensure essential variables from .env_setup are loaded
    if [ -z "$SALEAE_APP_PATH" ] || [ -z "$PYTHON_VENV_DIR" ] || [ -z "$PYTHON_REQS_FILE" ]; then
        echo "Error: One or more required environment variables (SALEAE_APP_PATH, PYTHON_VENV_DIR, PYTHON_REQS_FILE) are not set."
        echo "Please check your .env_setup file."
        exit 1
    fi
}

# Checks if a list of packages is installed and installs missing ones.
# Arguments: None
check_dependencies() {
    # Software dependencies
    local required_pkg=("$@")
    local missing_pkg=()

    # Check if saleae is properly setup
    if [ ! -f "$SALEAE_APP_PATH" ]; then
        echo "Saleae Logic 2 AppImage not found at '$SALEAE_APP_PATH'."
        echo "Downloading now from ${SALEAE_DOWNLOAD_URL}..."
        if ! wget -O "$SALEAE_APP_PATH" "$SALEAE_DOWNLOAD_URL"; then
            echo "Error: Failed to download Saleae Logic 2."
            rm -f "$SALEAE_APP_PATH" # Clean up partial download
            exit 1
        fi
        echo "Download complete. Making it executable..."
        chmod +x "$SALEAE_APP_PATH"
    elif [ ! -x "$SALEAE_APP_PATH" ]; then
        echo "Warning: Saleae AppImage found but is not executable. Making it executable..."
        chmod +x "$SALEAE_APP_PATH"
    fi

    # Check for missing packages
    for pkg in "${required_pkg[@]}";
    do
        if ! command -v "$pkg" &> /dev/null; then
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

# Set python environment
python_venv() {
    # Check for a valid .venv
    if [ ! -f "$PYTHON_VENV_DIR/bin/activate" ]; then
        echo "Creating python virtual environment..."
        if ! python3 -m venv "$PYTHON_VENV_DIR"; then
            echo "Error: Failed to create python virtual environment."
            exit 1
        fi
        echo "Python virtual environment created successfully."
    else
        echo "Python virtual environment already exists."
    fi

    # Activate .venv
    echo "Activating python virtual environment..."
    source "$PYTHON_VENV_DIR/bin/activate"

    # Check installed libraries
    local sentinel="$PYTHON_VENV_DIR/.last_install"
    if [ ! -f "$PYTHON_REQS_FILE" ]; then
        echo "Error: Python requirements file not found at '$PYTHON_REQS_FILE'."
        exit 1
    else
        echo "Found requirements.txt, installing python modules..."
        if [ ! -f "$sentinel" ] || [ "$PYTHON_REQS_FILE" -nt "$sentinel" ]; then
            echo "Installing/Updating python modules..."
            python3 -m pip install --upgrade pip
            
            if ! python3 -m pip install -r "$PYTHON_REQS_FILE"; then
                echo "Error: Failed to install python modules from $PYTHON_REQS_FILE."
                exit 1
            fi
            touch "$sentinel"
        else
            echo "[✔] Python modules are up to date."
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
    check_dependencies "${REQUIRED_PKG[@]}"
    python_venv

    echo -e "\n[✔] Setup complete. System ready."
}

# Invoke main
main "$@"
