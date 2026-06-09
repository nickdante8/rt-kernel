# Test Execution Interfacing & GPIO/PWM Settings

This document details the hardware-level interfacing safety mechanisms and signal measurement configurations established for the real-time execution testing.

---

## 1. GPIO & PWM Interfacing Safety (`led-toggle`)

The `led-toggle` C daemon drives a Software toggle (GPIO 17) and a Hardware PWM (GPIO 18) to provide synchronization boundaries for Saleae measurements.

### libgpiod v2 Migration
To avoid low-level POSIX `ioctl` calls on `/dev/gpiochip0` (which are complex, hard to debug, and prone to breaking across kernel updates), the code uses the modern **`libgpiod` v2** C library:
```c
struct gpiod_chip *chip = gpiod_chip_open("/dev/gpiochip0");
struct gpiod_line_settings *settings = gpiod_line_settings_new();
gpiod_line_settings_set_direction(settings, GPIOD_LINE_DIRECTION_OUTPUT);
gpiod_line_settings_set_output_value(settings, GPIOD_LINE_VALUE_INACTIVE);

struct gpiod_line_config *output_line_cfg = gpiod_line_config_new();
unsigned int offset = SOFT_PIN; // GPIO 17
gpiod_line_config_add_line_settings(output_line_cfg, &offset, 1, output_settings);

struct gpiod_request_config *req_cfg = gpiod_request_config_new();
gpiod_request_config_set_consumer(req_cfg, "led-toggle");

struct gpiod_line_request *request = gpiod_chip_request_lines(chip, req_cfg, output_line_cfg);
```

### Glitch-Free PWM Initialization Sequence
Direct writes to sysfs files (`/sys/class/pwm/pwmchip0/pwm0/...`) can lead to `-EINVAL` errors or signal glitches if the period and duty cycle are set in the wrong order (e.g. if the new period is shorter than the currently active duty cycle). The daemon implements a robust sequence:
1. **Disable PWM** (`enable` $\rightarrow$ `0`).
2. **Reset duty cycle to 0** (`duty_cycle` $\rightarrow$ `0`). This ensures that setting the period next will never trigger an `invalid argument` error (since `0` is always less than the new period).
3. **Set the new period** in nanoseconds.
4. **Set the target duty cycle** in nanoseconds.
5. **Enable PWM** (`enable` $\rightarrow$ `1`).

### High-Impedance Safety Exit
If a GPIO pin is configured as an output driving HIGH (3.3V) and is accidentally shorted to the metal chassis or ground, the high current draw will destroy the internal output transistors on the SoC.

To protect the board, the daemon intercepts termination signals (`SIGTERM`, `SIGINT`) and reconfigures the soft pin (GPIO 17) to **Input mode (High-Impedance)** before exiting:
```c
struct gpiod_line_settings *input_settings = gpiod_line_settings_new();
struct gpiod_line_config *input_cfg = gpiod_line_config_new();
if (input_settings && input_cfg) {
    gpiod_line_settings_set_direction(input_settings, GPIOD_LINE_DIRECTION_INPUT);
    unsigned int offset = SOFT_PIN;
    gpiod_line_config_add_line_settings(input_cfg, &offset, 1, input_settings);
    // Apply configuration change to active request
    gpiod_line_request_reconfigure_lines(request, input_cfg);
}
```

### Real-Time Execution Environment Hardening
To prevent scheduling delays caused by OS memory management or generic task scheduling, `led-toggle` actively hardens its own execution context on startup:
1. **Memory Paging Lock (`mlockall`)**: It locks all current and future virtual memory pages into physical RAM. If this fails, the process immediately exits, as relying on swapped or compressed (ZRAM) pages guarantees massive real-time jitter.
2. **Strict CPU Affinity (`sched_setaffinity`)**: The daemon binds itself exclusively to the isolated **CPU 3** (`CPU_SET(3, &cpuset)`), keeping it entirely segregated from software RPS handling and generic hardware interrupts.
3. **FIFO Scheduling (`sched_setscheduler`)**: It elevates itself to the `SCHED_FIFO` real-time class at priority `99`, ensuring it preempts any other user-space processes that might wander onto Core 3.

---

## 2. Jitter & Drift Performance Summary

The combination of the custom kernel architecture and the user-space implementation yields the following latency results:

| Kernel Setup | Jitter (Cycle-to-Cycle variation) | Drift (Long-term phase shift) | Rationale |
| :--- | :--- | :--- | :--- |
| **Baseline + `usleep`** | **SEVERE** | **SEVERE** | Network softirqs delay `usleep` wake-ups. Jitter delay stacks cumulatively every cycle. |
| **Baseline + `absolute_sleep`** | **SEVERE** | **NONE** | Softirqs still delay the wake-up (causing edge jitter), but the absolute waking target forces the next cycle to shorten, preventing drift. |
| **PREEMPT_RT + `usleep`** | **LOW** | **MODERATE** | The RT kernel preempts lower priority network traffic, resulting in stable wake-ups. However, C-code execution time overhead still stacks, causing slow phase drift. |
| **PREEMPT_RT + `absolute_sleep`**| **LOW** | **NONE** | **The Ideal Setup.** RT kernel guarantees immediate scheduling on wakeup, and absolute clock tracking (`clock_nanosleep` with `TIMER_ABSTIME`) prevents drift over infinite periods. |

---

## 3. Automated Test Execution & Latency Profiling

The testing suite automatically triggers stress scenarios, measures hardware-level and kernel-level timing, and profiles system statistics on the target Raspberry Pi.

### Host-Target Time Synchronization & Alignment
Because physical signal measurement (Logic Analyzer via `local-rtk`) and software metrics generation (`test_exec.sh` via `remote-rtk`) run on completely separate hardware, aligning their timelines is paramount. 
Before test execution, the local host pushes its exact local timestamp and timezone to the remote Raspberry Pi via `timedatectl` to force millisecond-level clock synchronization. To prevent permission errors during non-interactive scripts, `run_test.sh` securely pipes the target's `.sshpass` password directly into `sudo -S` when executing the synchronization routine. During the remote execution, the script logs `SYNC_WALL` (wall clock time) and `SYNC_MONO` (`/proc/uptime`) markers into `test_exec.log`. This ensures that all remotely captured datasets (cyclictest histograms, fio IOPS/bandwidth) perfectly correlate with the external Saleae physical measurements on a unified timeline. Additionally, the active kernel version (`uname -a`) and boot parameters (`/boot/firmware/config.txt`) are recorded to definitively link the resulting datasets to their specific real-time or baseline kernel configuration.

### Test Instrumentation Tools
We deploy standard real-time profiling utilities on the target system:
* **`cyclictest`** (from the `rt-tests` package): Measures internal kernel scheduling jitter by recording the latency between a timer wake-up event and the actual execution of the measurement thread.
* **`stress-ng`**: Injects synthetic computational and memory load into the system.
* **`iperf3`**: Generates high-throughput TCP/IP network traffic to stress the shared USB/Ethernet bus.
* **`fio`**: Conducts continuous raw disk read/write block operations to stress the USB mass storage interface.

### Background Load Service Prioritization
Crucially, the `test-exec.service` which manages the execution of stress tools is explicitly configured to run as `CPUSchedulingPolicy=other` and `CPUSchedulingPriority=0` (the default, unprivileged Linux scheduler class). If the stress injection tools were allowed to run at `SCHED_FIFO` or `SCHED_RR`, they would compete with the real-time `led-toggle` daemon and destroy temporal determinism.

### Upgraded Multi-Thread Jitter Profiling (`-t4`)
Originally, the benchmark execution script (`test_exec.sh`) executed a single-threaded cyclictest instance pinned to a single core (`-a 0 -t1`). This configuration hid the latency distribution across the other CPU cores, making it impossible to evaluate core isolation effects.

The instrumentation suite was upgraded to **4-thread CPU-wide profiling (`-t4`)** to monitor scheduling jitter across all 4 cores simultaneously. In addition, the histogram depth was increased to **`-h1000`** to capture scheduling outliers and Worst-Case Execution Time (WCET) delays up to 1000 microseconds (1ms). Finally, to prevent test phase-locking (where `cyclictest` and `led-toggle` inadvertently fall into a synchronized cadence), the benchmark calculates the measurement interval dynamically by subtracting a 3% offset from the nominal toggle semi-period.

### Synthesized Load Profiles
The test framework supports six distinct load scenarios to isolate scheduling and hardware bottlenecks:
1. **Idle (`idle`)**: Runs the measurement daemon without external stress to capture the baseline jitter under clean conditions.
2. **CPU Stress (`load-cpu`)**: Launches `chrt -o 0 nice -n 19 stress-ng --cpu 4` to saturate all CPU cores with compute-heavy, idle-priority loops, verifying the kernel's scheduler preemption hierarchy.
3. **Network Stress (`load-net`)**: Runs an `iperf3` client to saturate the LAN7515 bus with packet processing interrupts.
4. **Storage Stress (`load-usb`)**: Launches `fio` random read/write blocks on a USB storage drive to saturate the USB host controller bus. The test specifically caps file generation (`--size=100M`) and exports telemetry in `json+` format (`--output-format=json+`). To prevent disk exhaustion and high I/O blocking during lengthy captures, raw latency logging (`write_lat_log`) was removed in favor of 1-second averaged IOPS and Bandwidth tracking (`--log_avg_msec=1000`).
5. **Network + Storage Stress (`load-net-usb`)**: Combines `iperf3` and `fio` execution to stress the shared USB 2.0 downstream bus.
6. **Full Synthetic Stress (`load-full`)**: Executes a combined storm of CPU stress (`stress-ng --cpu 4`), memory pressure (`stress-ng --vm 2 --vm-bytes 50%` with nice 19), disk block I/O (`fio`), and network traffic (`iperf3`). This represents the ultimate stress vector to test worst-case scheduling latencies.

---

## 4. Multi-Core Jitter Visualization

### Parsing & Aligning Multi-Domain Data Streams
The Python processing library (`local-rtk/processing/linux.py` and `local-rtk/processing/models.py`) is responsible for extracting individual telemetry datasets (Saleae edge events, `cyclictest` JSON threads, `fio` JSON+, and `pidstat` outputs). Crucially, the parser utilizes the `SYNC_WALL` baseline timestamps extracted from `test_exec.log` to align the independent axes (local host time vs. remote monotonic uptime) into a single, synchronized timeline.

### Unified Timeline & Combined Plots
The test framework now supports generating comprehensive **Combined Plots** that map hardware events directly against software metrics. This allows us to visually observe how a spike in disk writes (from `fio`) or network interrupts directly correlates with a jitter outlier in the `led-toggle` real-time cycle at exactly the same microsecond. To maximize readability and prevent overlapping plotted data, statistical summaries for the combined correlation plots (System, Network, and Storage) are dynamically embedded at the bottom of the graphs. 

### Phase Drift & Signal Plots
The evaluation library (`local-rtk/processing/plots.py`) generates highly detailed signal behavior plots for phase shift and duty cycle drift. To provide immediate quantitative validation, comprehensive statistics boxes containing Minimum, Maximum, Average, and comparative differential metrics are systematically embedded onto every generated drift and phase plot canvas.

### Overlaid Latency Histograms
Using `local-rtk/processing/plots.py`, multi-threaded `cyclictest` measurements are extracted and mapped to `CyclictestThreadMetrics`. These are visualized in an **overlaid, semi-transparent bar plot**:
* A dedicated color palette is applied (CPU0 in blue, CPU1 in green, CPU2 in orange, CPU3 in purple) to clearly distinguish housekeeping cores from isolated real-time cores.
* On a system booted with `ENABLE_ISOLATION=true` (which isolates Core 3 via `isolcpus=3` and pins threaded IRQs to Core 2), the plot visually validates the shielding:
  * **CPU0 & CPU1 (General Housekeeping)**: Show wide, scattered latency distributions (means shifting right, high standard deviations, and maximum latencies extending into hundreds of microseconds) due to handling hardware interrupts (USB/Eth on CPU0) and software network packet processing (RPS on CPU1), alongside background load processes.
  * **CPU2 (Threaded IRQ Housekeeping)**: Handles the offloaded PREEMPT_RT threaded hardware interrupts. Its latency profile reflects the bursty nature of hardware events but remains detached from generic software processing.
  * **CPU3 (Strictly Isolated Real-Time)**: Exhibits a sharp, highly uniform vertical spike clustered tightly near 0–20µs. Since `led-toggle` exclusively binds to this isolated core, the maximum latency even under the extreme `load-full` scenario remains tightly bounded under 50–100µs.
* A detailed breakdown of statistics per CPU core (Total Cycles, Min, Max/WCET, Average, Standard Deviation, and Overflows) is embedded in a monospace legend box inside the chart for immediate comparison.
