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

The script initializes the default config using `make defconfig` (unified configuration for ARM64) and programmatically edits configurations using the kernel's `scripts/config` utility.

### Platform Hardening (BCM2837 / Cortex-A53)
To reduce compilation times, kernel memory overhead, and interrupt context-switching delay, non-target hardware support is stripped:
* **Core Count Lock**: Configures `CONFIG_NR_CPUS=4` to match the physical core layout of the Broadcom BCM2837.
* **Address Bit Sizing**: Configures `CONFIG_ARM64_VA_BITS=48` and `CONFIG_ARM64_PA_BITS=48` for Cortex-A53 address translation.
* **Architecture Stripping**: Disables all non-Broadcom system-on-chip architectures (e.g. `CONFIG_ARCH_QCOM`, `CONFIG_ARCH_SUNXI`, `CONFIG_ARCH_ROCKCHIP`) and non-essential Broadcom families (e.g. `CONFIG_ARCH_BRCMSTB` for set-top boxes, `CONFIG_ARCH_BCM_IPROC`).
* **Clock Driver Stripping**: Disables enterprise-level clocks like `CONFIG_CLK_BCM_63XX` and `CONFIG_COMMON_CLK_IPROC`.
* **Built-in Drivers**: Forces the SMSC/Microchip Ethernet driver (`CONFIG_USB_LAN78XX=y`) to be built-in to the kernel image. This eliminates the dependency on an initial RAM disk (initramfs) for mounting network filesystems on boot.

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

## 5. USB/Ethernet IRQ Pinning

While `irqaffinity=0,1` relocates standard interrupts, the primary USB controller interrupt (`dwc_otg` or `dwc2`) can still bleed onto other cores. To enforce strict determinism when the RT kernel is running, a dedicated script `/usr/local/bin/pin-usb-irq.sh` pins this interrupt.

Because some kernel architectures or hardware revisions on BCM2837/dwc2 do not support redirecting the USB interrupt from Core 0, the script includes logic to detect when the operation is rejected and log a warning instead of failing:

```bash
#!/bin/bash
# Find the active IRQ number of the USB controller
IRQ=$(grep -E 'dwc2|dwc_otg' /proc/interrupts | awk '{print $1}' | tr -d ':')
if [ -n "$IRQ" ]; then
    # Write mask 4 (binary 0100 -> Core 2) to the interrupt affinity file
    if echo 4 2>/dev/null > /proc/irq/$IRQ/smp_affinity; then
        echo "Pinned USB/Eth IRQ $IRQ to Core 2"
    else
        echo "WARNING: Failed to set smp_affinity for USB/Eth IRQ $IRQ (this is a hardware limitation on BCM2837/dwc2)"
    fi
else
    echo "Could not find dwc2/dwc_otg IRQ"
fi
```

### Automation Service
A systemd unit file `/etc/systemd/system/pin-usb-irq.service` executes this pinning routine automatically on boot:
* It is automatically **enabled** by the `switch-kernel` utility when switching to the **RT kernel**.
* It is automatically **disabled** when switching to the **Baseline** or **Default** kernels.

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
