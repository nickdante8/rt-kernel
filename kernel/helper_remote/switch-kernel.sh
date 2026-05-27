#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: sudo switch-kernel [prefix_name|default]"
    echo "Example: sudo switch-kernel 6.18.13-rt"
    exit 1
fi

# Strip any existing os_prefix or custom kernel definitions to ensure a clean slate
sed -i '/^os_prefix=/d' /boot/firmware/config.txt
sed -i '/^kernel=/d' /boot/firmware/config.txt

if [ "$1" == "default" ]; then
    systemctl disable pin-usb-irq.service
    echo "Switched to Factory Default kernel. Reboot to apply."
else
    PREFIX_DIR="/boot/firmware/$1"
    if [ ! -d "$PREFIX_DIR" ]; then
        echo "ERROR: Kernel prefix directory '$PREFIX_DIR' does not exist!"
        exit 1
    fi
    
    echo "os_prefix=$1/" >> /boot/firmware/config.txt
    
    # Automatically enable IRQ pinning if the prefix implies an RT kernel
    if [[ "$1" == *"-rt"* ]]; then
        systemctl enable pin-usb-irq.service
        echo "Switched to RT kernel ($1). IRQ Pinning ENABLED. Reboot to apply."
    else
        systemctl disable pin-usb-irq.service
        echo "Switched to Baseline kernel ($1). IRQ Pinning DISABLED. Reboot to apply."
    fi
fi
