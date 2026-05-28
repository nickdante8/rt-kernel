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

---

## 2. Jitter & Drift Performance Summary

The combination of the custom kernel architecture and the user-space implementation yields the following latency results:

| Kernel Setup | Jitter (Cycle-to-Cycle variation) | Drift (Long-term phase shift) | Rationale |
| :--- | :--- | :--- | :--- |
| **Baseline + `usleep`** | **SEVERE** | **SEVERE** | Network softirqs delay `usleep` wake-ups. Jitter delay stacks cumulatively every cycle. |
| **Baseline + `absolute_sleep`** | **SEVERE** | **NONE** | Softirqs still delay the wake-up (causing edge jitter), but the absolute waking target forces the next cycle to shorten, preventing drift. |
| **PREEMPT_RT + `usleep`** | **LOW** | **MODERATE** | The RT kernel preempts lower priority network traffic, resulting in stable wake-ups. However, C-code execution time overhead still stacks, causing slow phase drift. |
| **PREEMPT_RT + `absolute_sleep`**| **LOW** | **NONE** | **The Ideal Setup.** RT kernel guarantees immediate scheduling on wakeup, and absolute clock tracking (`clock_nanosleep` with `TIMER_ABSTIME`) prevents drift over infinite periods. |
