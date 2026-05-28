# 00 - Custom linux kernel

Standart General-Purpose Operation Systems (GPOS) like standard Raspberry Pi OS, Ubuntu or even Arch Linux are designed for throughput, not latency. There are certain problems for real time operating systems like:

* Non-deterministic – the Linux scheduler may delay a critical task to handle a background process like WiFi update or system log

* The “Jitter” Issue – every task requested to run every 1ms might actually run at 1.2ms or 0.8ms. This 200us “jitter” may be fatal in high-speed systems

* Bloat and Interference – standard distributions include hundreds of drivers that trigger “Interrupts”. These interrupts steal CPU cycles.

* Lack os Resource Isolation – a memory-heavy process (like an AI camera stream) can starve the CPU cache, slowing down the real-time control loop.

# Goal

The goal of the entire project would imply the following:

* **Kernel Optimization:** Compile a custom Linux kernel (v6.x) using the `PREEMPT_RT` patchset, specifically configured for the Broadcom SoC (System on Chip).

* **Minimal Footprint:** Strip the kernel of all non-essential drivers (USB-C, Sound, Wi-Fi, Video) to reduce the "Attack Surface" and "Interrupt Latency." – Improve security and CPU usage.

* **Hard Isolation:** Implement `Isolcpus` and `Cgroups` to "shield" a specific CPU core exclusively for the real-time application.

* **Benchmarking:** Create a testing framework to prove that the custom kernel maintains a jitter of < 50 microseconds even under 100% CPU/Memory stress.

There is **a famous problem** for Raspberry Pi 3B+ which can be used for testing this new Linux build. **The USB/Ethernet Hub.** On the 3B+, the Ethernet port is actually connected internally via the USB 2.0 bus. This causes a lot of interrupts when there is heavy network traffic, which can spike latency in the kernel. The topic could specifically focus on _how to tune the kernel's __interrupt handling _to prevent network traffic from "lagging" the real-time control loop on the 3B+ hardware.

# Implementation

For this implementation a Raspberry Pi 3B+ will be used with SD Card and a logic analyzer for signal measurement.

**Environment and tool-chain**

* Build system setup by using Yocto Project or Buildroot

* Cross – compilation on a Linux build host (Ubuntu like PC) to compile the kernel for the ARMv8 architecture of the Raspberry Pi

**Kernel configuration**

* Applying kernel patches from 6.x.y-rt series to the Linux source code

* Optimization by disabling bake essential drivers directly into the kernel image for speed

* Scheduler tuning by setting kernel tick rate to 1KHz and enable full preemption

**Hardware – software integration**

* Manually map hardware interrupts to specific CPU cores so they don’t interfere with the “Real-Time Core”

* Optimize u-boot and initramfs to achieve a fast boot time under 5 seconds

**Validation**

* Use stress-ng to max out the CPU/RAM

* use cyclictest (part of the rt-tests suite) to measure latency

* Use a Raspberry Pi GPIO pin to output a square wave. Measure the time with an oscilloscope or a logic analyzer to see if the wave stays perfectly stable while the Pi is under heavy load.

**The USB/Ethernet hub improvement**

* Interrupt time and functionality improvement of the high network traffic and USB data transfer

**Documentation**

* Kernel Config file

* Latency Histograms in comparison with “Standard Linux” vs “Arch RT” and dissertation custom build

* Show boot graph using systemd-analyze plot

* GPIO or high-speed motor measurement
