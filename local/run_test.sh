#!/bin/bash

# This script automates the process of running a determinism test.
# It ensures the environment is set up, starts the led-toggle service,
# captures data with a Saleae Logic Analyzer, exports the results,
# and runs the Python analysis script.

# Exit immediately if a command exits with a non-zero status.
set -e

# --- AUTOMATIC PATH SETTING ---
# This ensures the script always runs inside the folder where it lives
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

# --- Setup and python .venv activation ----
# Run the setup script to ensure all dependencies are met and the venv is active.
# Use 'source' so that environment changes (like venv activation) persist.
source "${SCRIPT_DIR}/setup.sh"

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

# --- Argument Parsing (Highest Precedence) ---
# This section will parse command-line arguments and override any values
# set by the initial defaults or the .env file.

# Use getopt for robust argument parsing. The empty string '' after -o means no short options.
# The long options are defined after --long.
# The -- "$@" ensures that getopt correctly handles arguments that might start with a hyphen.
PARSED_ARGS=$(getopt -o '' --long type:,duration: -- "$@")

# Check for parsing errors
if [ $? -ne 0 ]; then
    echo "Error: Failed to parse arguments." >&2
    exit 1
fi

# eval set -- "$PARSED_ARGS" assigns the parsed arguments back to the script's positional parameters.
eval set -- "$PARSED_ARGS"

while true; do
    case "$1" in
        --type)
            test_type_arg="$2"
            shift 2
            ;;
        --duration)
            CAPTURE_DURATION_S="$2"
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
        TEST_NAME="${TEST_NAME_RT}_${DATE}"
        OUTPUT_DIR="${SCRIPT_DIR}/test_results/${TEST_NAME}"
    elif [ $test_type_arg = "default" ]; then
        TEST_NAME="${TEST_NAME_DEFAULT}_${DATE}"
        OUTPUT_DIR="${SCRIPT_DIR}/test_results/${TEST_NAME}"
    else
        echo "ERROR: --type argument accepts only 'rt' or 'default'."
        exit 1
    fi
fi

# --- Display Final Configuration ---
echo "--- Final Configuration ---"
echo "TEST_NAME: ${TEST_NAME}"
echo "CAPTURE_DURATION_S: ${CAPTURE_DURATION_S}"
echo "OUTPUT_DIR: ${OUTPUT_DIR}"
echo "---------------------------"

# ---- Functions ----
# -------------------
# idle/load testing
testing() {
    if [ "$1" = "idle" ]; then
        local TEST_TYPE="idle"
        local TEST_ID="2"
        echo "[Step ${TEST_ID}.2/5] Idle testing..."
    elif [ "$1" = "load" ]; then
        local TEST_TYPE="load"
        local TEST_ID="3"
        echo "[Step ${TEST_ID}.2/5] Load testing..."
        #TODO: enter load testing activities here before starting script measurment
    else
        exit 1
    fi

    echo "[Step ${TEST_ID}.3/5]Starting led-toggle service on remote RPI..."
    sshpass -f .sshpass ssh -t "${RPI_USER}@${RPI_HOST}" "echo '$(cat .sshpass)' | sudo -S systemctl start led-toggle.service"

    # Give the service a moment to initialize
    sleep 1

    echo "[Step ${TEST_ID}.4/5]Starting capture with Python script..."
    # Run the python script to perform the capture.
    # It will connect to the already running Logic 2 instance.
    python3 "$PYTHON_MEASUREMENT_SCRIPT" \
        --port "$SALEAE_AUTOMATION_PORT" \
        --device "$SALEAE_DEVICE_ID" \
        --duration "$CAPTURE_DURATION_S" \
        --output-dir "$OUTPUT_DIR/$TEST_TYPE" \
        --channels "$SALEAE_CH_SOFT_PIN" "$SALEAE_CH_HARD_PIN"

    echo "[Step ${TEST_ID}.5/5]Stop led-toggle service on remote RPI..."
    sshpass -f .sshpass ssh -t "${RPI_USER}@${RPI_HOST}" "echo '$(cat .sshpass)' | sudo -S systemctl stop led-toggle.service"

    echo "  Retrieving log files from remote RPI..."
    sshpass -f .sshpass scp "${RPI_USER}@${RPI_HOST}:/var/log/led-toggle.log" "${OUTPUT_DIR}/${TEST_NAME}.log"
    echo "  Log file saved."
    echo "  Test finished."
}

# Processing of obtained results
processing() {
    # Run the python script to perform the capture.
    # It will connect to the already running Logic 2 instance.
    python3 "$PYTHON_PROCESSING_SCRIPT" \
        --duration "$CAPTURE_DURATION_S" \
        --input-dir "$OUTPUT_DIR" \
        --channels "$SALEAE_CH_SOFT_PIN" "$SALEAE_CH_HARD_PIN"
}


# ---- Main logic ----
# -------------------
# Prompt for password if not set
if [ ! -f "$SCRIPT_DIR/.sshpass" ]; then
    echo "ERROR: File $SCRIPT_DIR/.sshpass doesn't exist. Create it and save the password to it."
    exit 1
fi

if ! sshpass -f .sshpass ssh -o StrictHostKeyChecking=no -q "${RPI_USER}@${RPI_HOST}" exit; then
    echo "ERROR: Could not connect to RPI at '${RPI_USER}@${RPI_HOST}' via SSH with the provided password."
    exit 1
fi

echo "--- Starting Test: ${TEST_NAME} ---"
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
sleep 10

# Idle testing
testing "idle"

# Load testing
testing "load"

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

echo "--- Test Complete: ${TEST_NAME} ---"
echo "Summary of results can be found in:"
echo "${OUTPUT_DIR}"
echo "----------------------------------------"

echo "--- Test result processing ---"
processing
echo "----------------------------------------"

exit 0