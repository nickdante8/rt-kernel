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


# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v

    # Set global variables, dependencies and parge arguments
    environment_var

    # Actual testing
    echo "=== Test state check ==="

    # Check test state result
    # Local variables for state check and timeout
    local result_code=0
    local timeout=3
    local count=0

    # Loop for service state check
    while [[ $result_code == 0 ]]; do
        result_code=$(systemctl is-active --quiet ${LED_SERVICE_FILE_NAME} ${TEST_EXEC_SERVICE_FILE_NAME} && echo "0" || echo "1")
    
        # Small delay before next try
        sleep 0.5
        count=$(($count + 1))

        # Safety timeout for script to not hang
        if [ "$count" -ge $((timeout * 2)) ]; then
            echo "Warning: Timeout reached. Services are running. Try force stopping them."
            result_code=$(sudo systemctl stop ${LED_SERVICE_FILE_NAME} ${TEST_EXEC_SERVICE_FILE_NAME} && echo "0" || echo "1")
            echo "Message result after stopping services: $result_code"
            break
        fi
    done

    echo "Services are done: result_code $result_code"
    echo "========================"
    
    exit 0
}

# Invoke main
main "$@"
