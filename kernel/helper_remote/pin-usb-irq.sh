#!/bin/bash
# Find the IRQ for the USB/Ethernet controller (dwc2 or dwc_otg)
IRQ=$(grep -E 'dwc2|dwc_otg' /proc/interrupts | awk '{print $1}' | tr -d ':')
if [ -n "$IRQ" ]; then
    # 4 is the hex bitmask for Core 2 (0b0100)
    echo 4 > /proc/irq/$IRQ/smp_affinity
    echo "Pinned USB/Eth IRQ $IRQ to Core 2"
else
    echo "Could not find dwc2/dwc_otg IRQ"
fi
