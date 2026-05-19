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
}

# Setup running environment with setup.sh
setup_environment() {
    # --- Setup and python .venv activation ----
    # Run the setup script to ensure all dependencies are met and the venv is active.
    # Use 'source' so that environment changes (like venv activation) persist.
    source "${SCRIPT_DIR}/setup.sh"
}

# This section will parse command-line arguments and override any values
# set by the initial defaults or the .env file.
argument_parse() {
    # Use getopt for robust argument parsing. The empty string '' after -o means no short options.
    # The long options are defined after --long.
    # The -- "$@" ensures that getopt correctly handles arguments that might start with a hyphen.
    PARSED_ARGS=$(getopt -o '' --long setup,test-type:,load-type:,date-init:,duration-s:,nominal-period-us:,relative-toggle-time -- "$@")

    # Check for parsing errors
    if [ $? -ne 0 ]; then
        echo "Error: Failed to parse arguments." >&2
        exit 1
    fi

    # eval set -- "$PARSED_ARGS" assigns the parsed arguments back to the script's positional parameters.
    eval set -- "$PARSED_ARGS"

    local test_type_arg=""
    local load_type_arg=""
    local date_init_arg=""
    local led_relative_toggle_time=""

    while true; do
        case "$1" in
            --setup)
                SETUP_CHECK_ENABLE=TRUE
                shift 1
                ;;
            --test-type)
                test_type_arg="$2"
                shift 2
                ;;
            --load-type)
                load_type_arg="$2"
                shift 2
                ;;
            --date-init)
                date_init_arg="$2"
                shift 2
                ;;
            --nominal-period-us)
                NOMINAL_PERIOD_US="$2"
                shift 2
                ;;
            --duration-s)
                CAPTURE_DURATION_S="$2"
                shift 2
                ;;
            --relative-toggle-time)
                led_relative_toggle_time="-r"
                shift 1
                ;;
            --)
                shift
                break
                ;;
            *)
                echo "Internal error during argument parsing: $1"
                exit 1
                break
                ;;
        esac
    done

    # --- Date init ---
    if [ -n "$date_init_arg" ]; then
        if [ $date_init_arg = "" ]; then
            echo "No --date-init argument. Using current date of ${DATE}"
        else
            DATE="$date_init_arg"
        fi
    fi

    # --- Test type and name ---
    if [ -n "$test_type_arg" ]; then
        if [ $test_type_arg = "rt" ]; then
            TEST_TYPE="${TEST_TYPE_RT}"
            TEST_TYPE_FOLDER_NAME="${TEST_TYPE_RT}_${DATE}"
            OUTPUT_DIR="${SCRIPT_DIR}/test_results/${TEST_TYPE_FOLDER_NAME}"
        elif [ $test_type_arg = "default" ]; then
            TEST_TYPE="${TEST_TYPE_DEFAULT}"
            TEST_TYPE_FOLDER_NAME="${TEST_TYPE_DEFAULT}_${DATE}"
            OUTPUT_DIR="${SCRIPT_DIR}/test_results/${TEST_TYPE_FOLDER_NAME}"
        else
            echo "ERROR: --test-type argument accepts only ${TEST_TYPE_RT} or ${TEST_TYPE_DEFAULT}."
            exit 1
        fi
    fi

    # --- Load type ---
    if [ -n "$load_type_arg" ]; then
        if [[ " ${LOAD_TYPE_ALL_LIST[*]} " =~ " ${load_type_arg} " ]]; then
            LOAD_TYPE="${load_type_arg}"
        else
            echo "ERROR: --load-type argument accepts only ${LOAD_TYPE_ALL_LIST[@]}."
            exit 1
        fi
    fi

    LED_TOGGLE_OPTIONAL_PARAMS="${led_relative_toggle_time}"
    
    # --- Display Current Configuration ---
    echo "==== Current Configuration ===="
    echo "TEST_TYPE: ${TEST_TYPE}"
    echo "DATE: ${DATE}"
    echo "TEST_TYPE_FOLDER_NAME: ${TEST_TYPE_FOLDER_NAME}"
    echo "LOAD_TYPE: ${LOAD_TYPE[*]}"
    echo "CAPTURE_DURATION_S: ${CAPTURE_DURATION_S}"
    echo "NOMINAL_PERIOS_US: ${NOMINAL_PERIOD_US}"
    echo "LED_TOGGLE_OPTIONAL_PARAMS: ${LED_TOGGLE_OPTIONAL_PARAMS}"
    echo "OUTPUT_DIR: ${OUTPUT_DIR}"
    echo "***************************"
}

system_service_environment_variables() {
    # Check if environment file for the system service exist
    echo "Status: Creating environment file for the system service..."
    tee "$SYSTEM_SERVICE_ENV_VAR_FILE_PATH" > /dev/null <<EOF
# Environment variables used for the test
TEST_TYPE="${TEST_TYPE}"
LOAD_TYPE="${LOAD_TYPE}"
DATE="${DATE}"
NOMINAL_PERIOD_US="${NOMINAL_PERIOD_US}"
CAPTURE_DURATION_S="${CAPTURE_DURATION_S}"
TEST_TYPE_FOLDER_NAME="${TEST_TYPE_FOLDER_NAME}"
OUTPUT_DIR="${OUTPUT_DIR}"
LED_TOGGLE_OPTIONAL_PARAMS=${LED_TOGGLE_OPTIONAL_PARAMS}
EOF
}

# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v

    # Set global variables, dependencies and parge arguments
    environment_var
    argument_parse "$@"
    if [[ "${SETUP_CHECK_ENABLE}" == "TRUE" ]]; then
        echo "Running setup checks"
        setup_environment
    fi
    system_service_environment_variables

    # Actual testing
    echo "--- Starting Test: ${TEST_TYPE_FOLDER_NAME}, ${LOAD_TYPE} ---"

    # Create a directory for the test results
    mkdir -p "${OUTPUT_DIR}/${LOAD_TYPE}"
    cp ${SYSTEM_SERVICE_ENV_VAR_FILE_PATH} ${OUTPUT_DIR}/${LOAD_TYPE}
    echo "Results will be saved in: ${OUTPUT_DIR}/${LOAD_TYPE}"
    # Run healesly ${TEST_EXEC_SERVICE_FILE_NAME}
    sudo systemctl start ${TEST_EXEC_SERVICE_FILE_NAME} &
    # Run headlesly ${LED_SERVICE_FILE_NAME}
    sudo systemctl start ${LED_SERVICE_FILE_NAME} &
    echo "========================================"

    exit 0
}

# Invoke main
main "$@"
