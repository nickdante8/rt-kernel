#!/bin/bash

# This script automates the process of running a determinism test.
# It ensures the environment is set up, starts the led-toggle service,
# captures data with a Saleae Logic Analyzer, exports the results,
# and runs the Python analysis script.

# ==============================================================================
# 1. SETTINGS & GLOBALS
# ==============================================================================
# Exit immediately if a command exits with a non-zero status.
set -e

# --- AUTOMATIC PATH SETTING ---
# This ensures the script always runs inside the folder where it lives
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================
# Load environment variable of the script
environment_var() {
    # --- .env LOADING ---
    if [ -f "${SCRIPT_DIR}/.env" ]; then
        set -a
        source "${SCRIPT_DIR}/.env"
        set +a
        echo "[✔] Environment variables loaded from ${SCRIPT_DIR}/.env."
    else
        echo "[!] No .env file found. Using defaults."
    fi

    # --- current setup file ---
    if [ -f "${SETUP_FILE_CURRENT}" ]; then
        set -a
        source "${SETUP_FILE_CURRENT}"
        set +a
        echo "[✔] Setup variables loaded from ${SETUP_FILE_CURRENT}."
    else
        echo "[!] No ${SETUP_FILE_CURRENT} file found."
        exit 1
    fi

    # --- test execution configuration file ---
    if [ -f "${SYSTEM_SERVICE_ENV_VAR_FILE_PATH}" ]; then
        set -a
        source "${SYSTEM_SERVICE_ENV_VAR_FILE_PATH}"
        set +a
        echo "[✔] Test configuration variables loaded."
    else
        echo "[!] No ${SYSTEM_SERVICE_ENV_VAR_FILE_PATH} file found."
        exit 1
    fi
}

# This section will parse command-line arguments and override any values
# set by the initial defaults or the .env file.
current_configuration() {
    # --- Display Final Configuration ---
    echo "--- Final Configuration ---"
    echo "TEST_TYPE: ${TEST_TYPE}"
    echo "DATE: ${DATE}"
    echo "TEST_TYPE_FOLDER_NAME: ${TEST_TYPE_FOLDER_NAME}"
    echo "LOAD_TYPE: ${LOAD_TYPE}"
    echo "CAPTURE_DURATION_S: ${CAPTURE_DURATION_S}"
    echo "NOMINAL_PERIOS_US: ${NOMINAL_PERIOD_US}"
    echo "OUTPUT_DIR: ${OUTPUT_DIR}"
    echo "---------------------------"
}


# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v

    # Set global variables, dependencies and parge arguments
    environment_var
    current_configuration

    # Actual testing
    echo "--- Executing Test: ${TEST_TYPE_FOLDER_NAME}, ${LOAD_TYPE} ---"

    # Temporary
    cat <<EOF > "${OUTPUT_DIR}/${LOAD_TYPE}/log_file.log"
$(date +%Y-%m-%d-%H:%M:%S.%N)
EOF

    # Create a directory for the test results
    echo "Results will be saved in: ${OUTPUT_DIR}/${LOAD_TYPE}"
    # Test specific behavior based on requested load type
    if [[ "${LOAD_TYPE}" == "${LOAD_TYPE_IDLE}" ]]; then
        # Idle testing
        echo "idle"
    elif [[ "${LOAD_TYPE}" == "${LOAD_TYPE_NET}" ]]; then
        # Net load testing
        echo "load net"
    elif [[ "${LOAD_TYPE}" == "${LOAD_TYPE_USB}" ]]; then
        # USB load testing
        echo "load usb"
    elif [[ "${LOAD_TYPE}" == "${LOAD_TYPE_NET_USB}" ]]; then
        # Net and USB load testing
        echo "load net usb"
    else
        echo "ERROR: Load test type request isn't known: ${LOAD_TYPE}"
        exit 1
    fi

    # Temporary
    sleep $((CAPTURE_DURATION_S + 2))

    # Temporary
    cat <<EOF >> "${OUTPUT_DIR}/${LOAD_TYPE}/log_file.log"
$(date +%Y-%m-%d-%H:%M:%S.%N)
EOF

    echo "----------------------------------------"

    exit 0
}

# Invoke main
main "$@"
