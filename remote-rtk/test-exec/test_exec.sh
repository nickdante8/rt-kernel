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

# CPU, commands and interrupts measurement
timing_measurement() {
    # Background Logging
    if [[ "$1" == "start" ]]; then
        # Local variables to detect led-toggle start and record its pid
        local led_pid=""
        local timeout=1
        local count=0

        # Capture CPU per process
        while [[ "${led_pid}" == "" ]]; do
            if led_pid=$(pgrep led-toggle); then
                echo "${led_pid} break"
                break
            fi

            # Small delay before next try
            sleep 0.1
            count=$((count + 1))

            # Safety timeout for the script to not hang
            if [ "$count" -ge $((timeout * 10)) ]; then
                echo "ERROR: Timed out waiting for led-toggle service to start!"
                exit 1
            fi
        done

        echo "Found led-toggle PID: $Pled_pid}"
        pidstat -p "${led_pid}",$(pgrep iperf3) -u -w 1 ${CAPTURE_DURATION_S} > "${OUTPUT_DIR}/${LOAD_TYPE}/pidstat.log" &
        PID_STAT_PID=$!

        # Capture System-wide SoftIRQs and Interrupts
        mpstat -P ALL -n --dec=2 1 ${CAPTURE_DURATION_S} > "${OUTPUT_DIR}/${LOAD_TYPE}/mpstat_cpu_net.log" &
        MPSTAT_CPUNET_PID=$!
        mpstat -I SUM -P ALL --dec=2 1 ${CAPTURE_DURATION_S} > "${OUTPUT_DIR}/${LOAD_TYPE}/mpstat_interrupts.log" &
        MPSTAT_INT_PID=$!

        # Capture vmstat
        vmstat -twn 1 ${CAPTURE_DURATION_S} > "${OUTPUT_DIR}/${LOAD_TYPE}/vmstat.log" &
        VMSTAT_PID=$!

        # Capture Interrupt Counts (Start)
        cat /proc/interrupts > "${OUTPUT_DIR}/${LOAD_TYPE}/interrupts_start.txt"

        # Start cyclictest (Internal Latency)
        cyclictest -m -a 0 -N -t1 -p99 i400 -D ${CAPTURE_DURATION_S} --json="${OUTPUT_DIR}/${LOAD_TYPE}/cyclictest_interval.json" -h 5000 --histfile="${OUTPUT_DIR}/${LOAD_TYPE}/cyclictest_hist.log" &
        CYCLIC_PID=$!
    else
        # Cleanup and Finalize
        cat /proc/interrupts > "${OUTPUT_DIR}/${LOAD_TYPE}/interrupts_end.txt"
        sudo kill -SIGKILL $CYCLIC_PID $VMSTAT_PID $MPSTAT_INT_PID $MPSTAT_CPUNET_PID $PID_STAT_PID || true
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
    current_configuration

    # Actual testing
    echo "=== Executing Test: ${TEST_TYPE_FOLDER_NAME}, ${LOAD_TYPE} ==="

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

    timing_measurement "start"

    # Temporary
    sleep $((CAPTURE_DURATION_S + 2))

    timing_measurement "stop"

    # Temporary
    cat <<EOF >> "${OUTPUT_DIR}/${LOAD_TYPE}/log_file.log"
$(date +%Y-%m-%d-%H:%M:%S.%N)
EOF

    echo "========================================"

    exit 0
}

# Invoke main
main "$@"
