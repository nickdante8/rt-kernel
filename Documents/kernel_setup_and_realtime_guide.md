# Linux Kernel Customization & Real-Time Setup Guide for Raspberry Pi 3B+

This guide provides a comprehensive reference for configuring, compiling, installing, and optimizing custom Baseline and Real-Time (PREEMPT_RT) Linux kernels (v6.18.13) for the Raspberry Pi 3 Model B+. It also details the system-level optimizations (core isolation, IRQ pinning, ZRAM management) and hardware interfacing safety standards (`led-toggle` service).

---

## Table of Contents
1. [Kernel Build Framework & Host Setup](#1-kernel-build-framework--host-setup)
2. [Kernel Configuration (`configure.sh`)](#2-kernel-configuration-configuresh)
   - [Platform Hardening (BCM2837 / Cortex-A53)](#platform-hardening-bcm2837--cortex-a53)
   - [Baseline vs. Real-Time (RT) Configuration](#baseline-vs-real-time-rt-configuration)
   - [Subsystem Stripping (WiFi, Bluetooth, Video/Sound)](#subsystem-stripping-wifi-bluetooth-videosound)
3. [Dual-Boot Isolation & Deployment](#3-dual-boot-isolation--deployment)
   - [Staging & Module Cleanup](#staging--module-cleanup)
   - [Isolated Boot Prefixes (`os_prefix`)](#isolated-boot-prefixes-os_prefix)
   - [Kernel Switching Utility](#kernel-switching-utility)
4. [Real-Time Command Line Optimization (`cmdline.txt`)](#4-real-time-command-line-optimization-cmdlinetxt)
   - [Core Isolation & Tickless Settings](#core-isolation--tickless-settings)
   - [Interrupt Affinity & FIQ Disabling](#interrupt-affinity--fiq-disabling)
5. [USB/Ethernet IRQ Pinning](#5-usbethernet-irq-pinning)
6. [ZRAM & Real-Time Swap Constraints](#6-zram--real-time-swap-constraints)
   - [Why the system hangs on `dev-zram0.device`](#why-the-system-hangs-on-dev-zram0device)
   - [Why Swap is Bad for RT Determinism](#why-swap-is-bad-for-rt-determinism)
   - [Fixing the Boot Hang](#fixing-the-boot-hang)
7. [Disabling Onboard Heartbeat LED Triggers](#7-disabling-onboard-heartbeat-led-triggers)

---

## 1. Kernel Build Framework & Host Setup

The build system utilizes a cross-compilation framework on the host machine to target the ARM64 architecture of the Raspberry Pi 3B+.

### Host Dependencies
Install the required compilation and patching tools on the host system:
```bash
sudo apt-get update && sudo apt-get install -y \
    git bc bison flex libssl-dev make gcc-aarch64-linux-gnu \
    g++-aarch64-linux-gnu libc6-dev libncurses-dev \
    crossbuild-essential-arm64 libelf-dev rsync tar wget patch xz-utils
```

### Sourcing and Patching (`setup.sh`)
1. **Shallow Clone**: Clones the official Raspberry Pi Linux repository targeting the `rpi-6.18.y` branch with `--depth 1` to optimize disk usage and download speed.
2. **Commit Verification**: Checks out the specific commit hash defined in `config.env` (`25e0b1c206e3def1bd3bf9dcba980c5138c637a9`) to guarantee exact matching with the target Real-Time patch.
3. **Applying PREEMPT_RT Patch**: If `DOWNLOAD_RT_PATCH=true`, the script downloads the corresponding `patch-6.18.13-rt4.patch.xz` from the kernel archives, verifies it matches the checked-out source tree version, and applies/commits it cleanly to the git history.

---

## 2. Kernel Configuration (`configure.sh`)

The script programmatically edits kernel configurations using the kernel's `scripts/config` utility, applying real-time settings and optional driver stripping.

### Platform Configuration and Build Stability
Initially, the configuration framework attempted aggressive, platform-specific manual stripping (disabling other SoC architectures like Qualcomm or Rockchip, disabling enterprise-level clock drivers, and locking core counts). However, in modern kernels (v6.18+), these manual deletions broke deep driver dependencies, causing compilation stalls and unresolved link errors during the final dependency resolution phase (`make olddefconfig`).

To guarantee absolute build stability, the manual platform stripping functions were removed from `configure.sh`. Instead, the build system relies on official, battle-tested configuration templates provided in the Raspberry Pi kernel source tree:
* **Baseline Defconfig**: `bcm2711_defconfig` (the official downstream unified 64-bit config supporting Pi 3B+, Pi 4, and other Broadcom architectures).
* **Real-Time Defconfig**: `bcm2711_rt_defconfig` (the official downstream config containing the necessary real-time and preemption structure changes).

Using these base configurations ensures that all clock drivers, architecture dependencies, and essential platform drivers are correctly linked and compile out-of-the-box.

### Baseline vs. Real-Time (RT) Configuration

Depending on the `ENABLE_RT` flag in `config.env`, the script configures the scheduling behavior and tick rate:

| Parameter | Baseline Kernel Configuration | Real-Time (RT) Kernel Configuration |
| :--- | :--- | :--- |
| **Preemption Model** | `CONFIG_PREEMPT=y`<br>*(Standard preemption for desktop workloads)* | `CONFIG_PREEMPT_RT=y`<br>*(Forces all locks/handlers to be preemptible)* |
| **Timer Frequency** | `CONFIG_HZ_250=y` / `CONFIG_HZ=250`<br>*(250 Hz tick rate for low overhead)* | `CONFIG_HZ_1000=y` / `CONFIG_HZ=1000`<br>*(1000 Hz tick rate for 1ms precision)* |
| **RCU Offloading** | `CONFIG_RCU_NOCB_CPU` is disabled. | `CONFIG_RCU_NOCB_CPU=y`<br>*(Offloads RCU callbacks from isolated CPU cores)* |
| **Local Version Suffix**| `-BASELINE-CUSTOM` | `-RT-CUSTOM` |

### Subsystem Stripping (WiFi, Bluetooth, Video/Sound)
To optimize real-time latency (as drivers for wireless devices and GPUs often trigger high-priority system interrupts or long-running critical sections), the configurations can be stripped:
* **Wireless Support (`STRIP_WIFI=true`)**: Disables `CONFIG_CFG80211` and `CONFIG_MAC80211`, removing the Wi-Fi stack and drivers.
* **Bluetooth Support (`STRIP_BLUETOOTH=true`)**: Disables `CONFIG_BT`, removing the Bluetooth subsystem.
* **Sound/Video Support (`STRIP_SOUND_VIDEO=true`)**: Disables `CONFIG_SOUND` (soundcard architecture) and `CONFIG_DRM` (Direct Rendering Manager / GPU drivers).
  > [!NOTE]
  > Keeping `STRIP_SOUND_VIDEO=false` retains HDMI video output capability (`CONFIG_DRM_VC4=y`) for physical monitor support.

---

## 3. Dual-Boot Isolation & Deployment

### Staging & Module Cleanup
Running `./make.sh` compiles the kernel, device trees, and modular drivers, placing them in `dist/linux-6.18.13-[baseline|rt]/`:
* **Dangling Symlinks**: The build system automatically deletes the `build` and `source` symlinks created inside `lib/modules/6.18.13-*/` during modular driver installation.
  > [!WARNING]
  > If these symlinks are not removed, `scp` will follow them and attempt to transfer the entire multi-gigabyte kernel source code directory from the host to the Pi over the network, causing disk exhaustion and deployment failure.

### Isolated Boot Prefixes (`os_prefix`)
Instead of overwriting the default OS kernel (`/boot/firmware/kernel8.img`), which risks bricking the Pi if a configuration fails to boot, the custom kernels are installed in isolated directories inside `/boot/firmware/`:
* Baseline path: `/boot/firmware/6.18.13-baseline/`
* RT path: `/boot/firmware/6.18.13-rt/`

The Raspberry Pi bootloader is redirected to these folders dynamically via the `os_prefix` configuration key in `/boot/firmware/config.txt`. For example, setting:
```config
os_prefix=6.18.13-rt/
```
tells the firmware to load the kernel image (`kernel8.img`), standard device trees, and overlays from that folder instead of the root directory.

### Deployment Subcommands
The `install.sh` script exposes several subcommands to manage remote kernel deployment and parameter updates:
* `./install.sh kernel-deploy`: Installs the staged kernel modules, device trees, and overlays, and updates the boot parameters (`cmdline.txt`) on the remote Pi.
* `./install.sh kernel-boot-update`: Re-evaluates configurations from `config.env` and regenerates `/boot/firmware/<os_prefix>/cmdline.txt` on the Pi without copying kernel images or modules, saving time during command-line testing.
* `./install.sh dual-boot-helpers`: Configures or updates remote scripts like `switch-kernel.sh` and the IRQ pinning daemon.
* `./install.sh switch-kernel`: Runs the interactive switch tool directly, prompting you to boot to default, baseline, or real-time.

### Kernel Switching Utility
The script installs a helper script on the Pi at `/usr/local/bin/switch-kernel.sh`. It modifies `/boot/firmware/config.txt` to safely toggle between setups:
* `sudo switch-kernel default`: Restores factory default Raspberry Pi OS boot.
* `sudo switch-kernel 6.18.13-baseline`: Loads the custom baseline kernel.
* `sudo switch-kernel 6.18.13-rt`: Loads the custom PREEMPT_RT kernel.

---

## 4. Real-Time Command Line Optimization (`cmdline.txt`)

When deploying or updating boot parameters, `install.sh` generates a custom `cmdline.txt` inside the kernel's isolated prefix directory. This configuration is dynamically evaluated using environment variables in `config.env`, decoupling CPU scheduling and latency settings:

### Core Isolation & Tickless Settings (Enabled via `ENABLE_ISOLATION=true`)
To isolate CPU Cores 2 and 3 and reserve them exclusively for real-time applications (such as our `led-toggle` C daemon), set `ENABLE_ISOLATION=true` in `config.env`. The deployment script will append the following parameters to the kernel command line:
* `isolcpus=2,3`: Instructs the scheduler to never allocate general user-space processes or threads to Cores 2 and 3.
* `rcu_nocbs=2,3`: Offloads RCU (Read-Copy-Update) callback processing from Cores 2 and 3 to Cores 0 and 1.
* `nohz_full=2,3`: Places Cores 2 and 3 in adaptive tickless mode. If only a single thread runs on an isolated core, the periodic system timer interrupt is disabled, eliminating a major source of scheduling jitter.
* `irqaffinity=0,1`: Directs all default hardware interrupt handlers to execute on Core 0 or Core 1, protecting the real-time cores (2 and 3) from hardware interrupt overhead.

### Interrupt Affinity & FIQ Disabling (Enabled via `ENABLE_RT=true`)
Real-time latency constraints require turning off legacy Raspberry Pi hardware engines that conflict with deterministic scheduling. When `ENABLE_RT=true`, the following settings are appended:
* `dwc_otg.fiq_enable=0 dwc_otg.fiq_fsm_enable=0`: Disables the Raspberry Pi's USB/Ethernet Fast Interrupt Queue (FIQ) state machine.
  > [!IMPORTANT]
  > The Broadcom USB FIQ implementation is highly incompatible with the kernel `PREEMPT_RT` patch. Leaving FIQ enabled on an RT kernel triggers massive latency spikes and frequent kernel panics. Disabling it is mandatory for RT stability.

---

## 5. IRQ Offloading & Network Steering Helper

While `irqaffinity=0,1` in `cmdline.txt` suggests to the kernel to relocate standard interrupts, it does not completely prevent network packets, hardware interrupts, or driver workers from running on isolated Cores 2 and 3. To enforce strict determinism, the system installs an offloading daemon `/usr/local/bin/pin-usb-irq.sh` on the Pi.

This script performs three distinct levels of offloading to shield Cores 2 and 3 from interrupt and network overhead:

### 1. Software Network Stack Offloading (Receive Packet Steering - RPS)
When network packets arrive, they generate hardware interrupts, which are followed by software interrupt processing (softirqs) to run the TCP/IP stack. 
* The script writes mask `2` (binary `0010` -> CPU1) to `/sys/class/net/eth0/queues/rx-0/rps_cpus`.
* This forces all software-level network stack packet processing (RPS) to run exclusively on CPU1, shielding both CPU0 and the isolated Cores 2/3.

### 2. Hardware USB/Ethernet Interrupt Routing
* The script finds the active hardware IRQ number for the USB controller (`dwc_otg` or `dwc2`).
* It writes mask `3` (binary `0011` -> CPU0 & CPU1) to `/proc/irq/<IRQ>/smp_affinity`.
* This restricts the hardware USB/Ethernet interrupts from executing on Cores 2 and 3, keeping them strictly on the non-isolated CPU0 and CPU1.
* *Note:* Because some kernel configurations or hardware versions of the BCM2837/dwc2 do not support redirecting the USB hardware interrupt away from Core 0, the script catches write errors (`2>/dev/null`) and logs a warning instead of failing the startup.

### 3. Threaded IRQ Workers Pinning
On a `PREEMPT_RT` kernel (or baseline booted with the `threadirqs` command-line option), the kernel runs hardware interrupt handlers inside dedicated kernel threads (named `irq/[IRQ]-...`). 
* The script searches for these threads using `pgrep -f 'irq/[0-9]+-'`.
* It uses `taskset -cp 1` to pin them to CPU1 (Core index 1).
* This prevents interrupt handling threads from migrating to or executing on the isolated Cores 2 and 3.

```bash
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
```

### Automation & Decoupled Activation
A systemd unit file `/etc/systemd/system/pin-usb-irq.service` executes this routine on boot. 

The activation of this helper service is **completely decoupled from the kernel type**:
* The `switch-kernel.sh` script scans the target kernel's `cmdline.txt` for `isolcpus` or `irqaffinity`.
* If isolation flags are found (meaning `ENABLE_ISOLATION=true` was set when generating that kernel's boot parameter list), the IRQ Offloading service is automatically **enabled**.
* If no isolation flags are present (meaning `ENABLE_ISOLATION=false` was set), the service is automatically **disabled**.

This decoupling allows you to test:
1. **RT kernels with or without core isolation** (evaluating raw PREEMPT_RT capabilities versus core shielding).
2. **Baseline kernels with or without core isolation** (evaluating if core shielding alone can improve GPOS latency bounds).

---

## 6. ZRAM & Real-Time Swap Constraints

### Why the system hangs on `dev-zram0.device`
On standard Raspberry Pi OS installations, a compressed RAM swap daemon (like `zram-generator` or `zram-tools`) is active. When booting your custom baseline or RT kernels, you will see a boot delay:
```log
job dev-zram0.device/start running (1min 30s)
```
This hang happens because systemd waits for `/dev/zram0` to be initialized by the kernel. Because the custom kernel configs have `CONFIG_ZRAM` disabled to reduce kernel complexity, the driver is missing, `/dev/zram0` is never created, and systemd halts the boot sequence until it hits its 90-second timeout.

### Why Swap is Bad for RT Determinism
For real-time control, **swap memory (including ZRAM) must be disabled**. 

If a real-time thread executes a critical control loop and accesses a memory section that has been compressed/swapped out, a **page fault** is triggered. The OS must suspend your real-time process, run the decompression routine, allocate physical memory, and swap the pages back. This introduces massive, unpredictable scheduling delays (jitter) that destroy real-time guarantees.

### Fixing the Boot Hang
To eliminate the 90-second boot delay and safely disable ZRAM without recompiling the kernel, mask the device unit in systemd on the Pi:
```bash
sudo systemctl mask dev-zram0.device
```

---

## 7. Disabling Onboard Heartbeat LED Triggers

The Raspberry Pi's default firmware assigns the green onboard LED to the kernel's `heartbeat` trigger. This trigger generates frequent kernel interrupts and CPU cycles to blink the LED. For real-time execution, this must be disabled to prevent jitter.

Run the following commands on the Pi (or include them in your setup scripts):
```bash
# Disable PWR and ACT LED triggers
echo none | sudo tee /sys/class/leds/PWR/trigger || true
echo none | sudo tee /sys/class/leds/default-on/trigger || true
```
