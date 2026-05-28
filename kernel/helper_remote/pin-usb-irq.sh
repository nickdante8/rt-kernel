#!/bin/bash
# Find the IRQ for the USB/Ethernet controller (dwc2 or dwc_otg)
IRQ=$(grep -E 'dwc2|dwc_otg' /proc/interrupts | awk '{print $1}' | tr -d ':')
if [ -n "$IRQ" ]; then
    # 4 is the hex bitmask for Core 2 (0b0100)
    if echo 4 2>/dev/null > /proc/irq/$IRQ/smp_affinity; then
        echo "Pinned USB/Eth IRQ $IRQ to Core 2"
    else
        echo "WARNING: Failed to set smp_affinity for USB/Eth IRQ $IRQ (this is a hardware limitation on BCM2837/dwc2)"
    fi
else
    echo "Could not find dwc2/dwc_otg IRQ"
fi
