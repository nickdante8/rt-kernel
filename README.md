# rt-kernel
Real Time Linux kernel for Raspberry PI 3B+.

# Goal
The primary goals of this project are:
*   Compile a custom 64-bit Linux Kernel (v6.x) with the `PREEMPT_RT` patchset for the Raspberry Pi 3B+.
*   Isolate real-time operations to a single CPU core (the 3rd one).
*   Reduce the maximum "Worst-Case" latency from ~200-500μs (on a standard OS) to under 50μs when under synthetic stress.
*   Provide empirical proof of determinism using a physical logic analyzer connected to the GPIO pins.
*   Demonstrate latency reduction on the USB/Ethernet bus. High network or USB traffic can trigger a large number of Interrupt Requests (IRQs), which cause unpredictable latency spikes (jitter) in a standard kernel.
*   Add the new kernel to the Raspberry Pi to be able to switch between the default and the real-time one.

# Documentation

All related documentation to RPI 3B+ is taken directly from the official [source](https://www.raspberrypi.com/documentation/computers/raspberry-pi.html#introduction). A set of documents can be found in [Documents](./Documents/) folder and some provided links, like:
 * single-board computer (SBC) [BCM2837B0](https://www.raspberrypi.com/documentation/computers/processors.html#bcm2837b0)
 * [schematic](RP-008339-DS-1-raspberry-pi-3-b-plus-reduced-schematics.pdf)

For pinout mapping a wonderful mapping is made and shown on [pinout.xyz](https://pinout.xyz/)

# Setup

This guide details the cross-compilation process on a host Linux machine to build the kernel for the Raspberry Pi 3B+.

The setup is made on the latest available [Raspberry Pi Os Lite](https://www.raspberrypi.com/software/operating-systems/) of:
 * __Release date:__ 21 Aprl 2026
 * __System:__ 64-bit
 * __Kernel Version:__ 6.12.75+rpt-rpi-v8
 * __Debian version:__ 13 (trixie)

The goal is to add an additional kernel to be able to switch between them.

The pin is toggle by a small code made in C. Check [SDK Setup](https://www.raspberrypi.com/documentation/microcontrollers/c_sdk.html#sdk-setup) and the examples to setup and compile a C project.

### 1. Prerequisites

Ensure your host machine has the necessary cross-compilation toolchain and kernel build dependencies. For Debian-based systems (like Ubuntu):

```bash
sudo apt update
sudo apt install -y git bc bison flex libssl-dev make libc6-dev libncurses5-dev
sudo apt install -y crossbuild-essential-arm64 # For the 64-bit kernel
```

### 2. Get Kernel and RT Patch

```bash
# Clone the specific Raspberry Pi Linux source tree
# Pick a version that has a corresponding RT patch (e.g., 6.1.y)
git clone --depth=1 --branch rpi-6.1.y https://github.com/raspberrypi/linux.git
cd linux

# Download the corresponding PREEMPT_RT patch from kernel.org
# The patch version must match the kernel version
wget https://cdn.kernel.org/pub/linux/kernel/v6.x/patches/rt/patch-6.1.21-rt8.patch.xz
xz -d patch-6.1.21-rt8.patch.xz
patch -p1 < patch-6.1.21-rt8.patch
```

### 3. Configure and Build

```bash
# Set up the default configuration for RPi 3 (bcm2711 is for RPi4, but its 64-bit config is the one to use)
KERNEL=kernel8
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- bcm2711_defconfig

# Open the menu to enable RT options
make ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- menuconfig
```
Inside `menuconfig`, navigate to `General setup` -> `Preemption Model` and select `Fully Preemptible Kernel (Real-Time)`. Save the configuration and exit.

```bash
# Compile the kernel, modules, and device tree blobs
make -j$(nproc) ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu- Image modules dtbs
```

# Testing

After installing and booting the new kernel on the Raspberry Pi, you can verify its real-time capabilities.

### Kernel Verification

Check the kernel version string to ensure the `PREEMPT_RT` patch is active.

```bash
uname -v
```
The output should contain the `PREEMPT_RT` identifier.

### Latency Testing

To measure the real-time performance and confirm the latency reduction, you can use `cyclictest`.

```bash
# Install real-time testing tools
sudo apt update
sudo apt install -y rt-tests

# Run cyclictest under high system load to find the worst-case latency
# This example runs on core 3 with high priority, while stress-ng loads all other cores
sudo taskset -c 3 chrt -f 99 cyclictest -t1 -p 99 -n -i 1000 -l 1000000 &
stress-ng --cpu 3 --cpu-method all -t 10m
```

### GPIO Determinism Test

To provide empirical proof with a logic analyzer, you can write a simple program to toggle a GPIO pin at a precise interval. Connect the logic analyzer to the corresponding pin and ground to measure the jitter.