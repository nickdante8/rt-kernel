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
    
    # Automatically enable IRQ offloading if the target kernel's cmdline.txt contains isolcpus or irqaffinity
    if grep -qE "isolcpus|irqaffinity" "${PREFIX_DIR}/cmdline.txt" 2>/dev/null; then
        systemctl enable pin-usb-irq.service
        echo "Switched to kernel ($1). Isolation detected -> IRQ Pinning & RPS ENABLED. Reboot to apply."
    else
        systemctl disable pin-usb-irq.service
        echo "Switched to kernel ($1). No isolation -> IRQ Pinning & RPS DISABLED. Reboot to apply."
    fi
fi
