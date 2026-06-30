# ==============================================================================
# 1. SETTINGS & GLOBALS
# ==============================================================================
# Exit immediately if a command exits with a non-zero status.
set -e

# --- AUTOMATIC PATH SETTING ---
# This ensures the script always runs inside the folder where it lives
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
cd "$SCRIPT_DIR"

NUMBER_RUNS=50
TEST_OUTPUT_PATH="${SCRIPT_DIR}/test_results"


# ==============================================================================
# 2. HELPER FUNCTIONS
# ==============================================================================


# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Check if folder exists
    mkdir -p "${TEST_OUTPUT_PATH}/journal"

    # Execute loop
    for i in $(seq -w 1 $NUMBER_RUNS); do
        bash run_test.sh --test-type rt --load-type idle,load-full --duration-s 60 --nominal-period-us 200000
        # Rename the timestamped output to run_NNN
        latest=$(ls -td ${TEST_OUTPUT_PATH}/rt_* | head -1)
        mv "$latest" "${TEST_OUTPUT_PATH}/journal/run_${i}"
        echo "Completed run ${i}/${NUMBER_RUNS}"
        sleep 30  # Cool-down between runs to avoid thermal bias
    done
}

main "$@"