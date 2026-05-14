#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Variables and configurations
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
PROJECT_LOCATION="${SCRIPT_DIR}"
PROJECT_NAME="led-toggle"
SYS_SERVICE_FILE_NAME="${PROJECT_NAME}@.service"
SYS_SERVICE_ENABLE_FILE_NAME="${PROJECT_NAME}@period.service"
SYS_SERVICE_FILE_LOCAL_PATH="${SCRIPT_DIR}/${SYS_SERVICE_FILE_NAME}"
SYS_SERVICE_FILE_GLOBAL_PATH="/etc/systemd/system/${SYS_SERVICE_FILE_NAME}"
LED_TOGGLE_WORKING_DIRECTORY="${PROJECT_LOCATION}/build"
LED_TOGGLE_EXE_PATH="${LED_TOGGLE_WORKING_DIRECTORY}/${PROJECT_NAME}"


# The environment file will be placed in the user's home directory for clarity
#Identify the real user
IF_SUDO_USER=${SUDO_USER:-$USER}
REAL_HOME=$(getent passwd "$IF_SUDO_USER" | cut -d: -f6)

# Check if Project file exists
if [ -f "${PROJECT_LOCATION}/${PROJECT_NAME}.c" ]; then
    echo "${PROJECT_NAME}.c file exists. Continue..."
else
    echo "${PROJECT_NAME}.c file doesn't exists. Check if the script is started from the right path."
    exit 1
fi

# Set the right file mod
chmod +x ${PROJECT_LOCATION}/build.sh

# Check if library is installed
echo "Checking for pigpio library..."

if [ -f "/usr/local/include/pigpio.h" ]; then
    echo "pigpio is already installed (Version: $(pigpiod -v))"
else
    echo "pigpio not found. Starting installation..."

    # Update package list
    sudo apt update
    sudo apt install -y wget unzip make gcc

    # Download and Build from source (Official abyz.me.uk method)
    # Using a temporary directory to keep things clean
    TEMP_DIR=$(mktemp -d)
    cd "$TEMP_DIR" || exit

    echo "Downloading pigpio source..."
    wget https://github.com/joan2937/pigpio/archive/master.zip
    unzip master.zip
    cd pigpio-master || exit

    echo "Compiling pigpio (this may take a few minutes)..."
    make
    sudo make install

    # Clean up
    cd /tmp
    rm -rf "$TEMP_DIR"

    echo "Status: pigpio installed successfully."

    # Refresh library links
    sudo ldconfig
fi

# Check if system service file exists to start/stop led-toggle
if [ -f "$SYS_SERVICE_FILE_GLOBAL_PATH" ]; then
    echo "Status: $SYS_SERVICE_FILE_GLOBAL_PATH already exists. Skipping installation."
else
    echo "Status: Installing system service..."

    # Install the system service
    tee "$SYS_SERVICE_FILE_LOCAL_PATH" > /dev/null <<EOF
[Unit]
Description=Raspberry Pi GPIO Toggle Service
After=network.target
# Ensure we don't conflict with the standard pigpio daemon
Conflicts=pigpiod.service

[Service]
# Real-Time Scheduling Configuration
# This forces the kernel to prioritize this task over the network stack
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99
# Adjust the path to where your binary is actually located
Environment="SCRIPT_ARGS=%I"
ExecStart=${LED_TOGGLE_EXE_PATH} \$SCRIPT_ARGS
WorkingDirectory=${LED_TOGGLE_WORKING_DIRECTORY}
# Handling logs
StandardOutput=append:/var/log/led-toggle.log
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

    mv $SYS_SERVICE_FILE_LOCAL_PATH $SYS_SERVICE_FILE_GLOBAL_PATH
    # Reload systemd to recognize the new file
    systemctl daemon-reload

    # Enable the service to start automatically on boot
    systemctl enable ${SYS_SERVICE_ENABLE_FILE_NAME}

    echo "Success: ${SYS_SERVICE_FILE_NAME} is now active and enabled."
    echo "To start it run: sudo systemctl start ${SYS_SERVICE_FILE_NAME}"
fi
