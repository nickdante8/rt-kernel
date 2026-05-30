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
    echo "SERVER_IP: ${SERVER_IP}"
    echo "OUTPUT_DIR: ${OUTPUT_DIR}"
    echo "***************************"
}

# CPU, commands and interrupts measurement
timing_measurement() {
    local measure_state="$1"
    local cyclictest_interval="$2"
    local cyclictest_hist="$3"

    # Background Logging
    if [[ "${measure_state}" == "start" ]]; then
        # Local variables to detect led-toggle start and record its pid
        local led_pid=""
        local timeout=1
        local count=0

        # Capture System-wide SoftIRQs and Interrupts
        mpstat -I SUM -P ALL --dec=2 1 ${CAPTURE_DURATION_S_EXTENDED} -o JSON > "${OUTPUT_DIR}/${LOAD_TYPE}/mpstat_sum_itr.log" &
        MPSTAT_INT_PID=$!
        mpstat -A --dec=2 1 ${CAPTURE_DURATION_S_EXTENDED} -o JSON > "${OUTPUT_DIR}/${LOAD_TYPE}/mpstat_all.log" &
        MPSTAT_ALL_PID=$!

        # Capture vmstat
        vmstat -twn 1 ${CAPTURE_DURATION_S_EXTENDED} > "${OUTPUT_DIR}/${LOAD_TYPE}/vmstat.log" &
        VMSTAT_PID=$!

        # Capture Interrupt Counts (Start)
        cat /proc/interrupts > "${OUTPUT_DIR}/${LOAD_TYPE}/interrupts_start.txt"

        # Start cyclictest (Internal Latency)
        sudo cyclictest -m -s -t4 -p99 -i${cyclictest_interval} -h${cyclictest_hist} -D ${CAPTURE_DURATION_S_EXTENDED} \
            --json="${OUTPUT_DIR}/${LOAD_TYPE}/cyclictest.json" --histfile="${OUTPUT_DIR}/${LOAD_TYPE}/cyclictest.log" &
        CYCLIC_PID=$!

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
                echo "<3>ERROR: Timed out waiting for led-toggle service to start!"
                sudo kill -SIGKILL $CYCLIC_PID $VMSTAT_PID $MPSTAT_ALL_PID $MPSTAT_INT_PID || true
                exit 1
            fi
        done

        echo "Found led-toggle PID: ${led_pid}"
        local pid_list="${led_pid}"
        pgrep iperf3 > /dev/null 2>&1 && pid_list="${pid_list},$(pgrep -d, iperf3)"
        pgrep fio > /dev/null 2>&1 && pid_list="${pid_list},$(pgrep -d, fio)"
        pgrep stress-ng > /dev/null 2>&1 && pid_list="${pid_list},$(pgrep -d, stress-ng)"
        pidstat -p "${pid_list}" -u -w 1 ${CAPTURE_DURATION_S_EXTENDED} > "${OUTPUT_DIR}/${LOAD_TYPE}/pidstat.log" &
        PID_STAT_PID=$!

        # Save pid state for future logging
        chrt -p ${MPSTAT_INT_PID} > "${OUTPUT_DIR}/${LOAD_TYPE}/pid_chrt.log"
        chrt -p ${MPSTAT_ALL_PID} >> "${OUTPUT_DIR}/${LOAD_TYPE}/pid_chrt.log"
        chrt -p ${VMSTAT_PID} >> "${OUTPUT_DIR}/${LOAD_TYPE}/pid_chrt.log"
        chrt -p ${CYCLIC_PID} >> "${OUTPUT_DIR}/${LOAD_TYPE}/pid_chrt.log"
        chrt -p ${PID_STAT_PID} >> "${OUTPUT_DIR}/${LOAD_TYPE}/pid_chrt.log"
    else
        # Cleanup and Finalize
        cat /proc/interrupts > "${OUTPUT_DIR}/${LOAD_TYPE}/interrupts_end.txt"
        sudo kill -SIGKILL $CYCLIC_PID $VMSTAT_PID $MPSTAT_ALL_PID $MPSTAT_INT_PID $PID_STAT_PID || true
    fi
}

test_start() {
    # Load type
    local load_type="$1"

    # Variable calculations
    # Calculate cyclictest interval: semi-period minus 3% offset to break phase-locking
    local cyclictest_interval=$(( (NOMINAL_PERIOD_US / 2) * 97 / 100 ))
    # Update it for all load types
    local cyclictest_hist=1000

    # Create a directory for the test results
    echo "<6>INFO: Start test ${LOAD_TYPE}, ${CAPTURE_DURATION_S}"
    echo "Results will be saved in: ${OUTPUT_DIR}/${LOAD_TYPE}"
    # Test specific behavior based on requested load type
    if [[ "${load_type}" == "${LOAD_TYPE_IDLE}" ]]; then
        # Idle
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    elif [[ "${load_type}" == "${LOAD_TYPE_CPU}" ]]; then
        # Start stress load
        chrt -o 0 nice -n 19 stress-ng --cpu 4 --timeout ${CAPTURE_DURATION_S_EXTENDED}s &
        STRESS_NG_PID=$!

        # CPU load
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    elif [[ "${load_type}" == "${LOAD_TYPE_NET}" ]]; then
        # iperf3 network load
        iperf3 -c ${SERVER_IP} -R -i 1 -t ${CAPTURE_DURATION_S_EXTENDED} &
        IPERF3_PID=$!

        # Net load
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    elif [[ "${load_type}" == "${LOAD_TYPE_USB}" ]]; then
        # fio USB load
        sudo fio --name=${load_type} --filename=/dev/sda --size=100M --time_based --runtime=${CAPTURE_DURATION_S_EXTENDED} \
            --ioengine=libaio --direct=1 --rw=randrw --rwmixread=50 --bs=4k --iodepth=16 --numjobs=4 --group_reporting \
            --write_lat_log=${OUTPUT_DIR}/${load_type}/fio_latency --write_iops_log=${OUTPUT_DIR}/${load_type}/oufio_iops \
            --write_bw_log=${OUTPUT_DIR}/${load_type}/fio_bw --log_avg_msec=500 \
            --output-format=json --output=${OUTPUT_DIR}/${load_type}/fio_summary.json &
        FIO_PID=$!

        # USB load
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    elif [[ "${load_type}" == "${LOAD_TYPE_NET_USB}" ]]; then
        # fio USB load
        sudo fio --name=${load_type} --filename=/dev/sda --size=100M --time_based --runtime=${CAPTURE_DURATION_S_EXTENDED} \
            --ioengine=libaio --direct=1 --rw=randrw --rwmixread=50 --bs=4k --iodepth=16 --numjobs=4 --group_reporting \
            --write_lat_log=${OUTPUT_DIR}/${load_type}/fio_latency --write_iops_log=${OUTPUT_DIR}/${load_type}/oufio_iops \
            --write_bw_log=${OUTPUT_DIR}/${load_type}/fio_bw --log_avg_msec=500 \
            --output-format=json --output=${OUTPUT_DIR}/${load_type}/fio_summary.json &
        FIO_PID=$!
        # iperf3 network load
        iperf3 -c ${SERVER_IP} -R -i 1 -t ${CAPTURE_DURATION_S_EXTENDED} &
        IPERF3_PID=$!

        # Net and USB load
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    elif [[ "${load_type}" == "${LOAD_TYPE_FULL}" ]]; then
        # fio USB load
        sudo fio --name=${load_type} --filename=/dev/sda --size=100M --time_based --runtime=${CAPTURE_DURATION_S_EXTENDED} \
            --ioengine=libaio --direct=1 --rw=randrw --rwmixread=50 --bs=4k --iodepth=16 --numjobs=4 --group_reporting \
            --write_lat_log=${OUTPUT_DIR}/${load_type}/fio_latency --write_iops_log=${OUTPUT_DIR}/${load_type}/oufio_iops \
            --write_bw_log=${OUTPUT_DIR}/${load_type}/fio_bw --log_avg_msec=500 \
            --output-format=json --output=${OUTPUT_DIR}/${load_type}/fio_summary.json &
        FIO_PID=$!
        # iperf3 network load
        iperf3 -c ${SERVER_IP} -R -i 1 -t ${CAPTURE_DURATION_S_EXTENDED} &
        IPERF3_PID=$!

        # Start stress load (CPU and memory)
        chrt -o 0 nice -n 19 stress-ng --cpu 4 --vm 2 --vm-bytes 50% --timeout ${CAPTURE_DURATION_S_EXTENDED}s &
        STRESS_NG_PID=$!

        # Full load
        timing_measurement "start" "${cyclictest_interval}" "${cyclictest_hist}"
    else
        echo "<3>ERROR: Load test type request isn't known: ${load_type}"
        exit 1
    fi
}

test_stop() {
    # Load type
    local load_type="$1"

    # Message of finished test
    echo "Test finished: ${load_type}"
    # Test specific behavior based on requested load type
    if [[ "${load_type}" == "${LOAD_TYPE_IDLE}" ]]; then
        # Idle
        echo ""
    elif [[ "${load_type}" == "${LOAD_TYPE_CPU}" ]]; then
        # CPU load
        sudo kill -SIGKILL $STRESS_NG_PID || true
    elif [[ "${load_type}" == "${LOAD_TYPE_NET}" ]]; then
        # Net load
        sudo kill -SIGKILL $IPERF3_PID || true
    elif [[ "${load_type}" == "${LOAD_TYPE_USB}" ]]; then
        # USB load
        sudo kill -SIGKILL $FIO_PID || true
    elif [[ "${load_type}" == "${LOAD_TYPE_NET_USB}" ]]; then
        # Net and USB load
        sudo kill -SIGKILL $IPERF3_PID $FIO_PID || true
    elif [[ "${load_type}" == "${LOAD_TYPE_FULL}" ]]; then
        # Full load
        sudo kill -SIGKILL $IPERF3_PID $FIO_PID $STRESS_NG_PID || true
    else
        echo "<3>ERROR: Load test type request isn't known: ${load_type}"
        exit 1
    fi

    echo "<6>INFO: End test ${LOAD_TYPE}, ${CAPTURE_DURATION_S}"

    # Stop timing measurement
    timing_measurement "stop"
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

    # Create an updated time parameter for tools to run
    CAPTURE_DURATION_S_EXTENDED=$((CAPTURE_DURATION_S + 1))

    # Actual testing
    echo "=== Executing Test: ${TEST_TYPE_FOLDER_NAME}, ${LOAD_TYPE} ==="

    # Temporary
    cat <<EOF > "${OUTPUT_DIR}/${LOAD_TYPE}/log_file.log"
$(date +%Y-%m-%d-%H:%M:%S.%N)
EOF

    # Start testing. Initialize all tooling
    test_start "${LOAD_TYPE}"

    # Wait untill all tests are executed
    sleep $((CAPTURE_DURATION_S + 2))

    # Stop testing. Close and clean
    test_stop "${LOAD_TYPE}"

    # Temporary
    cat <<EOF >> "${OUTPUT_DIR}/${LOAD_TYPE}/log_file.log"
$(date +%Y-%m-%d-%H:%M:%S.%N)
EOF

    echo "========================================"

    exit 0
}

# Invoke main
main "$@"
