#!/bin/bash

# --- AUTOMATIC PATH SETTING ---
# This ensures the script always runs inside the folder where it lives
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

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

echo "--- Starting Environment Setup & Pre-flight Checks ---"



# --- Pre-flight Checks ---
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

# --- Python venv and dependencies ---
# Check if python3 exists
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed. Please install it (e.g., 'sudo apt install python3')."
    exit 1
fi

# Check if pip3 exists
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed. Please install it (e.g., 'sudo apt install python3-pip')."
    exit 1
fi

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
source "$PYTHON_VENV_DIR/bin/activate"
echo "Activating python virtual environment..."

# Check installed libraries
if [ ! -f "$PYTHON_REQS_FILE" ]; then
    echo "Error: Python requirements file not found at '$PYTHON_REQS_FILE'."
    exit 1
else
    echo "Found requirements.txt, installing python modules..."
    if ! pip3 install -r "$PYTHON_REQS_FILE"; then
        echo "Error: Failed to install python modules from $PYTHON_REQS_FILE."
        exit 1
    fi
    echo "Python modules installed successfully."
fi

# Check sshpass dependency is satisfied
if ! command -v sshpass &> /dev/null; then
    echo "Error: sshpass is not installed. Please install it (e.g., 'sudo apt install sshpass')."
    exit 1
fi

echo "[✔] Setup complete. All dependencies are satisfied."
