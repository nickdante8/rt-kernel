import argparse
import os
import processing_utils as proc


# ---- Function -----
# -------------------


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
        plots.append(proc.Plot_obj(args.input_dir, args.test_type, load_type, args.channels, args.nominal_period_us, args.duration_s))

    # Load and process data
    for plot in plots:
        plot.load_and_process_datas()

    # --- Data Analysis ---
    for plot in plots:
        proc.plot_histograms(plot)
        proc.plot_phase_shift_combined(plot)
        proc.plot_signal_drift(plot)
        proc.plot_signal_drift_combined(plot)
        proc.plot_interrupts_stacked_bar(plot)

    # Check type of analysis to run
    if len(args.loads_type) > 1:
        # Multiple ploting with different load types is possible
        for i in range(len(args.channels)):
            proc.plot_duty_cycle_combined(plots[0], plots[1], i)

if __name__ == '__main__':
    main()