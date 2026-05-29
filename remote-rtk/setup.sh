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
# install pakages true name
INSTALL_PKG=("build-essential" "cmake" "sysstat" "iperf3" "fio" "libgpiod-dev" "gpiod" "rt-tests" "stress-ng")
# command name to check if they are available
REQUIRED_PKG=("gcc" "cmake" "pidstat" "iperf3" "fio" "gpiodetect" "gpiodetect" "cyclictest" "stress-ng")


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
}

# Checks if a list of packages is installed and installs missing ones.
# Arguments: None
check_global_dependencies() {
    # Software dependencies
    local -n _required_ref=$1
    local -n _install_ref=$2
    local missing_pkg=()

    # Check for missing packages
    for i in "${!_required_ref[@]}"; do
        local cmd="${_required_ref[$i]}"
        local pkg="${_install_ref[$i]}"

        if ! command -v "$cmd" &> /dev/null; then
            echo "[!] Missing: $cmd (Requires: $pkg)"
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

    # Create variable setup file
    echo "Status: Creating environment file for the system service..."
    tee "${SETUP_FILE_CURRENT}" > /dev/null <<EOF
# Global testing
SYSTEM_SERVICE_ENV_VAR_FILE_NAME="${SYSTEM_SERVICE_ENV_VAR_FILE_NAME}"
SYSTEM_SERVICE_ENV_VAR_FILE_PATH="${SYSTEM_SERVICE_ENV_VAR_FILE_PATH}"
SETUP_FILE_CURRENT="${SETUP_FILE_CURRENT}"

# LED project location
LED_PROJECT_NAME="${LED_PROJECT_NAME}"
LED_PROJECT_LOCATION="${LED_PROJECT_LOCATION}"
LED_SERVICE_DELAY_START_TIME="${LED_SERVICE_DELAY_START_TIME}"
LED_SERVICE_FILE_NAME="${LED_SERVICE_FILE_NAME}"
LED_SERVICE_ENABLE_FILE_NAME="${LED_SERVICE_ENABLE_FILE_NAME}"
LED_SERVICE_FILE_LOCAL_PATH="${LED_SERVICE_FILE_LOCAL_PATH}"
LED_SERVICE_FILE_GLOBAL_PATH="${LED_SERVICE_FILE_GLOBAL_PATH}"
LED_TOGGLE_WORKING_DIRECTORY="${LED_TOGGLE_WORKING_DIRECTORY}"
LED_TOGGLE_EXE_PATH="${LED_TOGGLE_EXE_PATH}"
LED_SERVICE_ENV_FILE_PATH="${LED_SERVICE_ENV_FILE_PATH}"

# test exec service
TEST_EXEC_PROJECT_NAME="${TEST_EXEC_PROJECT_NAME}"
TEST_EXEC_PROJECT_LOCATION="${TEST_EXEC_PROJECT_LOCATION}"
TEST_EXEC_SERVICE_DELAY_START_TIME="${TEST_EXEC_SERVICE_DELAY_START_TIME}"
TEST_EXEC_SERVICE_FILE_NAME="${TEST_EXEC_SERVICE_FILE_NAME}"
TEST_EXEC_SERVICE_ENABLE_FILE_NAME="${TEST_EXEC_SERVICE_ENABLE_FILE_NAME}"
TEST_EXEC_SERVICE_FILE_LOCAL_PATH="${TEST_EXEC_SERVICE_FILE_LOCAL_PATH}"
TEST_EXEC_SERVICE_FILE_GLOBAL_PATH="${TEST_EXEC_SERVICE_FILE_GLOBAL_PATH}"
TEST_EXEC_WORKING_DIRECTORY="${TEST_EXEC_WORKING_DIRECTORY}"
TEST_EXEC_EXE_PATH="${TEST_EXEC_EXE_PATH}"
TEST_EXEC_START_PATH="${TEST_EXEC_START_PATH}"
TEST_EXEC_STATE_PATH="${TEST_EXEC_STATE_PATH}"
TEST_EXEC_SERVICE_ENV_FILE_PATH="${TEST_EXEC_SERVICE_ENV_FILE_PATH}"
EOF
}

# Checl led-toggle dependencies
check_led_toggle_dependencies() {
    # Check if Project file exists
    if [ -f "${LED_PROJECT_LOCATION}/${LED_PROJECT_NAME}.c" ]; then
        echo "${LED_PROJECT_LOCATION}/${LED_PROJECT_NAME}.c file exists. Continue..."
    else
        echo "${LED_PROJECT_LOCATION}/${LED_PROJECT_NAME}.c file doesn't exists. Check if the script is started from the right path."
        exit 1
    fi

    # Set the right file mod
    chmod +x ${LED_PROJECT_LOCATION}/build.sh

    # Check if library is installed
    echo "pigpio dependency has been completely removed in favor of standard Linux GPIO and PWM APIs!"

    # Check if system service file exists to start/stop led-toggle
    if [ -f "$LED_SERVICE_FILE_GLOBAL_PATH" ]; then
        echo "Status: $LED_SERVICE_FILE_GLOBAL_PATH already exists. Skipping installation."
    else
        echo "Status: Installing system service..."

        # Install the system service
        tee "$LED_SERVICE_FILE_LOCAL_PATH" > /dev/null <<EOF
[Unit]
Description=Raspberry Pi GPIO Toggle Service
After=network.target

[Service]
# Real-Time Scheduling Configuration
# This forces the kernel to prioritize this task over the network stack
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99

# Adjust the path to where binary is actually located
ExecStartPre=/bin/sleep ${LED_SERVICE_DELAY_START_TIME}
EnvironmentFile=${LED_SERVICE_ENV_FILE_PATH}
ExecStart=${LED_TOGGLE_EXE_PATH} -p \${NOMINAL_PERIOD_US} -d \${CAPTURE_DURATION_S} -o \${OUTPUT_DIR}/\${LOAD_TYPE} \$LED_TOGGLE_OPTIONAL_PARAMS
WorkingDirectory=${LED_TOGGLE_WORKING_DIRECTORY}

# Handling logs
StandardOutput=journal
StandardError=inherit

# Shutdown behaviour
KillSignal=SIGTERM
TimeoutStopSec=10s
KillMode=process
SuccessExitStatus=0
Restart=no
User=root

[Install]
WantedBy=multi-user.target
EOF

        echo "Status: File created. Finalizing systemd configuration..."

        mv $LED_SERVICE_FILE_LOCAL_PATH $LED_SERVICE_FILE_GLOBAL_PATH
        # Reload systemd to recognize the new file
        systemctl daemon-reload

        # Enable the service to start automatically on boot
        systemctl enable ${LED_SERVICE_ENABLE_FILE_NAME}

        echo "Success: ${LED_SERVICE_FILE_NAME} is now active and enabled."
        echo "To start it run: sudo systemctl start ${LED_SERVICE_FILE_NAME}"
    fi
}

# Check test-exec service and file
check_test_exec_dependencies() {
    # Set the right file mod
    chmod +x ${TEST_EXEC_EXE_PATH}
    chmod +x ${TEST_EXEC_START_PATH}
    chmod +x ${TEST_EXEC_STATE_PATH}

    # Check if system service file exists
    if [ -f "$TEST_EXEC_SERVICE_FILE_GLOBAL_PATH" ]; then
        echo "Status: $TEST_EXEC_SERVICE_FILE_GLOBAL_PATH already exists. Skipping installation."
    else
        echo "Status: Installing system service..."

        # Install the system service
        tee "$TEST_EXEC_SERVICE_FILE_LOCAL_PATH" > /dev/null <<EOF
[Unit]
Description=Raspberry Pi Test execution Service
After=network.target

[Service]
# Real-Time Scheduling Configuration
# This forces the kernel to prioritize this task over the network stack
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99

# Adjust the path to where binary is actually located
ExecStartPre=/bin/sleep ${TEST_EXEC_SERVICE_DELAY_START_TIME}
ExecStart=${TEST_EXEC_EXE_PATH}
WorkingDirectory=${TEST_EXEC_WORKING_DIRECTORY}

# Handling logs
StandardOutput=journal
StandardError=inherit

# Shutdown behaviour
KillSignal=SIGTERM
TimeoutStopSec=10s
KillMode=process
SuccessExitStatus=0
Restart=no
User=root

[Install]
WantedBy=multi-user.target
EOF

        echo "Status: File created. Finalizing systemd configuration..."

        mv $TEST_EXEC_SERVICE_FILE_LOCAL_PATH $TEST_EXEC_SERVICE_FILE_GLOBAL_PATH
        # Reload systemd to recognize the new file
        systemctl daemon-reload

        # Enable the service to start automatically on boot
        systemctl enable ${TEST_EXEC_SERVICE_ENABLE_FILE_NAME}

        echo "Success: ${TEST_EXEC_SERVICE_FILE_NAME} is now active and enabled."
        echo "To start it run: sudo systemctl start ${TEST_EXEC_SERVICE_FILE_NAME}"
    fi
}


# ==============================================================================
# 3. MAIN LOGIC (The "Entry Point")
# ==============================================================================
main() {
    # Ensure sudo access early so it doesn't prompt in the middle of a loop
    sudo -v 
    
    environment_var
    check_global_dependencies REQUIRED_PKG INSTALL_PKG
    check_led_toggle_dependencies
    check_test_exec_dependencies

    echo -e "\n[✔] Setup complete. System ready."
}

# Invoke main
main "$@"
