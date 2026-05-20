import argparse
import os
import processing_utils as proc


# ---- Function -----
# -------------------
# Plot histograms
def plot_histograms(plots_idle, plots_load):
    # Plot histogram idle
    proc.plot_histograms(plots_idle)        
    
    # Plot histogram load
    proc.plot_histograms(plots_load)

# Plot phase shift
def plot_phase_shift(plots_idle, plots_load, phase_idle, phase_load):
    # Plot phase
    proc.plot_phase_shift_combined(phase_idle, plots_idle)
    proc.plot_phase_shift_combined(phase_load, plots_load)

# Plot signal drift
def plot_signal_drift(plots_idle, plots_load):
    # Individual
    proc.plot_signal_drift(plots_idle)
    proc.plot_signal_drift(plots_load)

    # Combined
    proc.plot_signal_drift_combined(plots_idle[0], plots_idle[1])
    proc.plot_signal_drift_combined(plots_load[0], plots_load[1])

# Plot duty cycle
def plot_duty_cycle(plots_idle, plots_load):
    # Plot duty cycle idle
    pli = plots_idle[0]
    pll = plots_load[0]
    plp = plots_idle[0]
    title = f"Duty Cycle comparison. Channel {pli.channel} from {pli.load_type} and {pll.load_type}"
    proc.plot_duty_cycle_combined(pli.result, pll.result, title, proc.plot_path(plp, "duty_cycle", "",combined=True))

    # Plot duty cycle idle
    pli = plots_idle[1]
    pll = plots_load[1]
    plp = plots_load[0]
    title = f"Duty Cycle comparison. Channel {pli.channel} from {pli.load_type} and {pll.load_type}"
    proc.plot_duty_cycle_combined(pli.result, pll.result, title, proc.plot_path(plp, "duty_cycle", "",combined=True))



# ------- MAIN ------
# -------------------
def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Automate processing of Saleae capture.")
    parser.add_argument('--test-type', type=str, required=True, help='Type of test, like: idle, load-net, load-usb and so on.')
    parser.add_argument('--loads-type', type=str, nargs='+', required=True, help='List of load typeds used to capture data.')
    parser.add_argument('--nominal-period-us', type=int, required=True, help='Nominal period in seconds.')
    parser.add_argument('--duration-s', type=float, required=True, help='Capture duration in seconds.')
    parser.add_argument('--input-dir', type=str, required=True, help='Directory to process captureed and exported data.')
    parser.add_argument('--channels', type=int, nargs='+', required=True, help='List of digital channels used for capture.')
    args = parser.parse_args()

    # Create array of data to use in the loop
    plots = []
    for load_type in args.loads_type:
        for channel in args.channels:
            plots.append(proc.Plot_obj(args.input_dir, args.test_type, load_type, channel, args.nominal_period_us, args.duration_s))

    # --- Data Analysis ---
    # Separate to idle and load
    plots_idle = [obj for obj in plots if obj.load_type == "idle"]
    phase_idle = proc.perform_phase_shift_analysis(plots_idle[0].result['edges_rise'], plots_idle[1].result['edges_rise'], args.nominal_period_us)

    plots_load = [obj for obj in plots if obj.load_type == "load-net"]
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