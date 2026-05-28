#!/bin/bash
# ==============================================================================
# IRQ Offloading & Network Steering Helper
# ==============================================================================

# 1. Configure Receive Packet Steering (RPS) to offload network stack processing to CPU1
RPS_PATH="/sys/class/net/eth0/queues/rx-0/rps_cpus"
if [ -f "$RPS_PATH" ]; then
    # 2 is the hex bitmask for CPU1 (0b0010)
    if echo 2 2>/dev/null > "$RPS_PATH"; then
        echo "Successfully configured RPS for eth0 to CPU1"
    else
        echo "WARNING: Failed to configure RPS for eth0"
    fi
else
    echo "Notice: eth0 RPS queue not found"
fi

# 2. Set USB/Ethernet hardware IRQ affinity to CPU0/CPU1 (mask 3 = CPU0 & CPU1)
IRQ=$(grep -E 'dwc2|dwc_otg' /proc/interrupts | awk '{print $1}' | tr -d ':')
if [ -n "$IRQ" ]; then
    # 3 is the hex bitmask for CPU0 & CPU1 (0b0011)
    if echo 3 2>/dev/null > /proc/irq/$IRQ/smp_affinity; then
        echo "Set USB/Eth IRQ $IRQ smp_affinity to CPU0/CPU1 (mask 3)"
    else
        echo "WARNING: Failed to set smp_affinity for USB/Eth IRQ $IRQ (this is a hardware limitation on BCM2837/dwc2)"
    fi
else
    echo "Could not find dwc2/dwc_otg IRQ"
fi

# 3. Pin all threaded IRQ threads to CPU1 (CPU index 1)
# These threads exist on RT kernels (or baseline booted with threadirqs)
PINNED_COUNT=0
for pid in $(pgrep -f 'irq/[0-9]+-'); do
    if taskset -cp 1 "$pid" >/dev/null 2>&1; then
        PINNED_COUNT=$((PINNED_COUNT + 1))
    fi
done

if [ "$PINNED_COUNT" -gt 0 ]; then
    echo "Successfully pinned $PINNED_COUNT threaded IRQ workers to CPU1"
else
    echo "Notice: No threaded IRQ workers found to pin (running standard baseline kernel?)"
fi
