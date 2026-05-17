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
    # This safely loads the variables from .env without touching other files
    if [ -f "$SCRIPT_DIR/.env" ]; then
        set -a
        source "$SCRIPT_DIR/.env"
        set +a
        echo "[✔] Environment variables loaded."
    else
        echo "[!] No .env file found. Using defaults."
    fi
}

# Setup running environment with setup.sh
setup_environment() {
    # --- Setup and python .venv activation ----
    # Run the setup script to ensure all dependencies are met and the venv is active.
    # Use 'source' so that environment changes (like venv activation) persist.
    source "${SCRIPT_DIR}/setup.sh"

    # Prompt for password if not set
    if [ ! -f "$SCRIPT_DIR/.sshpass" ]; then
        echo "ERROR: File $SCRIPT_DIR/.sshpass doesn't exist. Create it and save the password to it."
        exit 1
    fi

    if ! sshpass -f .sshpass ssh -o StrictHostKeyChecking=no -q "${RPI_USER}@${RPI_HOST}" exit; then
        echo "ERROR: Could not connect to RPI at '${RPI_USER}@${RPI_HOST}' via SSH with the provided password."
        exit 1
    fi
}

# This section will parse command-line arguments and override any values
# set by the initial defaults or the .env file.
argument_parse() {
    # Use getopt for robust argument parsing. The empty string '' after -o means no short options.
    # The long options are defined after --long.
    # The -- "$@" ensures that getopt correctly handles arguments that might start with a hyphen.
    PARSED_ARGS=$(getopt -o '' --long test-type:,load-type:,load-type-all,duration-s:,nominal-period-us: -- "$@")

    # Check for parsing errors
    if [ $? -ne 0 ]; then
        echo "Error: Failed to parse arguments." >&2
        exit 1
    fi

    # eval set -- "$PARSED_ARGS" assigns the parsed arguments back to the script's positional parameters.
    eval set -- "$PARSED_ARGS"

    load_type_all_arg=FALSE
    load_type_arg=""
    test_type_arg=""

    while true; do
        case "$1" in
            --test-type)
                test_type_arg="$2"
                shift 2
                ;;
            --load-type)
                load_type_arg="$2"
                shift 2
                ;;
            --load-type-all)
                load_type_all_arg=TRUE
                shift 1
                ;;
            --nominal-period-us)
                NOMINAL_PERIOD_US="$2"
                shift 2
                ;;
            --duration-s)
                CAPTURE_DURATION_S="$2"
                SALEAE_CAPTURE_DURATION_S=$(($2 + 2))
                shift 2
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
            echo "ERROR: --type argument accepts only 'rt' or 'default'."
            exit 1
        fi
    fi

    # --- Load type ---
    if [[ "$load_type_all_arg" == "TRUE" ]]; then
        LOAD_TYPE=("${LOAD_TYPE_ALL_LIST[@]}")
    elif [[ -z "$load_type_arg" ]]; then
        LOAD_TYPE=("${LOAD_TYPE_ALL_LIST[@]}")
    else
        if [[ " ${LOAD_TYPE_ALL_LIST[*]} " =~ " ${load_type_arg} " ]]; then
            LOAD_TYPE="${load_type_arg}"
        else
            echo "ERROR: --load-type argument accepts only one of the following: ${LOAD_TYPE_ALL_LIST[@]}."
            exit 1
        fi
    fi

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

# Idle/load testing
testing() {
    # Use local variable to go through all test types
    local -n _load_type=$1

    echo " --- Testing --- "
    # Parse throught them
    for i in "${!_load_type[@]}"; do
        local current_load_type="${_load_type[$i]}"
        
        echo "Processing index $i with value ${current_load_type}"
        echo "[Step ${i}.1/5]Starting capture with Python script..."
        echo "[Step ${i}.2/5]Starting testing script on remote RPI..."
        sshpass -f .sshpass ssh -t "${RPI_USER}@${RPI_HOST}" \
            "echo '$(cat .sshpass)' | sudo -S bash \
            ${REMOTE_TEST_START_SCRIPT_NAME} \
            --test-type '${TEST_TYPE}' \
            --load-type '${current_load_type}' \
            --date-init '${DATE}' \
            --duration-s '${CAPTURE_DURATION_S}' \
            --nominal-period-us '${NOMINAL_PERIOD_US}'"

        # Run the python script to perform the capture.
        # It will connect to the already running Logic 2 instance.
        python3 "$PYTHON_MEASUREMENT_SCRIPT" \
            --port "$SALEAE_AUTOMATION_PORT" \
            --device "$SALEAE_DEVICE_ID" \
            --duration-s "$SALEAE_CAPTURE_DURATION_S" \
            --output-dir "$OUTPUT_DIR/$current_load_type" \
            --channels "$SALEAE_CH_SOFT_PIN" "$SALEAE_CH_HARD_PIN"

        # Add a small sleep to prevent spike during the test
        # After this, ideally, the tests on the remote must be finished
        sleep 1

        # Check test state result
    done
    echo " -------------- "

    echo "  Retrieving log files from remote ..."
    sshpass -f .sshpass scp -r \
        "${RPI_USER}@${RPI_HOST}:${REMOTE_OUTPUT_DIR}/${TEST_TYPE_FOLDER_NAME}/*" \
        "${OUTPUT_DIR}"

    echo "  Log file[s] saved."
    echo "  Tests[s] finished."
}

# Processing of obtained results
processing() {
    # Run the python script to perform the capture.
    # It will connect to the already running Logic 2 instance.
    python3 "$PYTHON_PROCESSING_SCRIPT" \
        --nominal-period-us "$NOMINAL_PERIOD_US" \
        --duration-s "$CAPTURE_DURATION_S" \
        --input-dir "$OUTPUT_DIR" \
        --channels "$SALEAE_CH_SOFT_PIN" "$SALEAE_CH_HARD_PIN"
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
    setup_environment

    # Actual testing
    echo "--- Starting Test: ${TEST_TYPE_FOLDER_NAME} ---"
    echo "Capture duration: ${CAPTURE_DURATION_S} seconds"

    # Create a directory for the test results
    mkdir -p "$OUTPUT_DIR"
    echo "Results will be saved in: ${OUTPUT_DIR}"

    # --- Test Execution ---
    echo "[Step 1/5] Starting Saleae Logic 2 application..."
    # Start the Logic 2 AppImage in the background. The '&' is key.
    # We redirect stdout and stderr to a log file to keep the console clean.
    nohup "$SALEAE_APP_PATH" --automation --automationPort $SALEAE_AUTOMATION_PORT > saleae.log 2>&1 &
    SALEAE_PID=$! # Get the Process ID of the background job

    # It's crucial to give the application time to launch before trying to connect.
    echo "Waiting for Saleae application to initialize (PID: $SALEAE_PID)..."
    sleep 5

    # Idle testing
    testing LOAD_TYPE

    echo "Shutting down Saleae application..."
    # Gracefully shut down the Saleae application by sending a SIGTERM signal
    kill $SALEAE_PID
    sleep 5 # Give it time to shut down
    # If it's still running, force kill it
    if ps -p $SALEAE_PID > /dev/null; then
    echo "Saleae did not shut down gracefully, forcing."
    kill -9 $SALEAE_PID
    fi
    echo "Saleae application closed."

    echo "--- Test Complete: ${TEST_TYPE_FOLDER_NAME} ---"
    echo "Summary of results can be found in:"
    echo "${OUTPUT_DIR}"
    echo "----------------------------------------"

    echo "--- Test result processing ---"
    # processing
    echo "----------------------------------------"

    exit 0
}

# Invoke main
main "$@"