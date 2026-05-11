import argparse
import os
import processing_utils as proc


# ---- Function -----
# -------------------
# Plot histograms
def plot_histograms(plots_idle, plots_load):
    # Plot histogram idle
    for plot in plots_idle:
        proc.plot_histogram_rise(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "rise"))
        proc.plot_histogram_fall(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "fall"))
        proc.plot_histogram_combined(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "rise_fall"))
        
    # Plot histogram load
    for plot in plots_load:
        proc.plot_histogram_rise(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "rise"))
        proc.plot_histogram_fall(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "fall"))
        proc.plot_histogram_combined(plot.result, plot.jitter_title, proc.plot_path(plot, "histogram", "rise_fall"))

# Plot phase shift
def plot_phase_shift(plots_idle, plots_load, phase_idle, phase_load):
    # Plot phase
    label = [
        f"Latency Channel {plots_idle[0].channel} in comparison\nwith Channel {plots_idle[1].channel} (idle)",
        f"Phase Difference Channel {plots_idle[0].channel} in\ncomparison with Channel {plots_idle[1].channel} (idle)",
    ]
    proc.plot_phase_shift_combined(phase_idle, label, proc.plot_path(plots_idle[0], "phase_shift", "", combined=True))

    label = [
        f"Latency Channel {plots_load[0].channel} in comparison\nwith Channel {plots_load[1].channel} (load)",
        f"Phase Difference Channel {plots_load[0].channel} in\ncomparison with Channel {plots_load[1].channel} (load)",
    ]
    label = f"Latency Channel {plots_load[0].channel} in comparison with Channel {plots_load[1].channel} (load)"
    proc.plot_phase_shift_combined(phase_load, label, proc.plot_path(plots_load[0], "phase_shift", "", combined=True))

# Plot signal drift
def plot_signal_drift(plots_idle, plots_load):
    # Individual
    label = [
        f"Channel {plots_idle[0].channel} rise ({plots_idle[0].load_type})",
        f"Channel {plots_idle[0].channel} fall ({plots_idle[0].load_type})",
    ]
    proc.plot_signal_drift(plots_idle[0].result, label, proc.plot_path(plots_idle[0], "signal_drift", "rise_fall"))
    label = [
        f"Channel {plots_load[0].channel} rise ({plots_load[0].load_type})",
        f"Channel {plots_load[0].channel} fall ({plots_load[0].load_type})",
    ]
    proc.plot_signal_drift(plots_load[0].result, label, proc.plot_path(plots_load[0], "signal_drift", "rise_fall"))

    # Combined
    label = [
        f"Channel {plots_idle[0].channel} ({plots_idle[0].load_type})",
        f"Channel {plots_idle[1].channel} ({plots_idle[1].load_type})",
    ]
    proc.plot_signal_drift_combined(plots_idle[0].result, plots_idle[1].result, label, proc.plot_path(plots_idle[0], "signal_drift", f"{plots_idle[0].channel}_{plots_idle[1].channel}", combined=True))
    label = [
        f"Channel {plots_load[0].channel} ({plots_load[0].load_type})",
        f"Channel {plots_load[1].channel} ({plots_load[1].load_type})",
    ]
    proc.plot_signal_drift_combined(plots_load[0].result, plots_load[1].result, label, proc.plot_path(plots_load[0], "signal_drift", f"{plots_load[0].channel}_{plots_load[1].channel}", combined=True))

# Plot duty cycle
def plot_duty_cycle(plots_idle, plots_load):
    # Plot duty cycle idle
    title = "Duty Cycle comparison. Channel 0 from idle and load"
    proc.plot_duty_cycle_combined(plots_idle[0].result, plots_load[0].result, title, proc.plot_path(plots_idle[0], "duty_cycle", "",combined=True))
    # Plot duty cycle load
    title = "Duty Cycle comparison. Channel 1 from idle and load"
    proc.plot_duty_cycle_combined(plots_idle[1].result, plots_load[1].result, title, proc.plot_path(plots_load[1], "duty_cycle", "",combined=True), y_lim=(50.0025, 50.004))

# ------- MAIN ------
# -------------------
def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Automate processing of Saleae capture.")
    parser.add_argument('--nominal-period-us', type=int, required=True, help='Nominal period in seconds.')
    parser.add_argument('--duration-s', type=float, required=True, help='Capture duration in seconds.')
    parser.add_argument('--input-dir', type=str, required=True, help='Directory to process captureed and exported data.')
    parser.add_argument('--channels', type=int, nargs='+', required=True, help='List of digital channels used for capture.')
    args = parser.parse_args()

    test_type = os.path.basename(os.path.normpath(args.input_dir))
    if "default" in test_type:
        test_type = "default"
    elif "rt" in test_type:
        test_type = "rt"
    else:
        exit(1)

    # Create array of data to use in the loop
    plots = []
    for load_type in ["idle", "load"]:
        for channel in args.channels:
            plots.append(proc.Plot_obj(args.input_dir, test_type, load_type, channel, args.nominal_period_us))

    # --- Data Analysis ---
    # Separate to idle and load
    plots_idle = [obj for obj in plots if obj.load_type == "idle"]
    phase_idle = proc.perform_phase_shift_analysis(plots_idle[0].result['edges_rise'], plots_idle[1].result['edges_rise'], args.nominal_period_us)

    plots_load = [obj for obj in plots if obj.load_type == "load"]
    phase_load = proc.perform_phase_shift_analysis(plots_load[0].result['edges_rise'], plots_load[1].result['edges_rise'], args.nominal_period_us)

    # Plot histograms
    plot_histograms(plots_idle, plots_load)

    # Plot phases_shift
    plot_phase_shift(plots_idle, plots_load, phase_idle, phase_load)

    # Plot signal drift
    plot_signal_drift(plots_idle, plots_load)

    # Plot duty cycle
    plot_duty_cycle(plots_idle, plots_load)

if __name__ == '__main__':
    main()