import argparse
from models import ExperimentConfig
from experiment import ExperimentProcessor, ExperimentPlotter

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

    # Create array of datasets to use in the loop
    datasets = []
    for load_type in args.loads_type:
        config = ExperimentConfig(
            input_dir=args.input_dir,
            test_type=args.test_type,
            load_type=load_type,
            channels=args.channels,
            nominal_period_us=args.nominal_period_us,
            duration_s=args.duration_s
        )
        datasets.append(ExperimentProcessor(config))

    # Load and process data, then generate plots
    for dataset in datasets:
        dataset.load_and_process_datas()
        dataset.generate_all_plots()

    # Duty cycle combination
    ExperimentPlotter.plot_duty_cycle_combined(datasets, 0, show=True)
    ExperimentPlotter.plot_duty_cycle_combined(datasets, 1, show=True, y_lim=(49.99, 50.02))
    
if __name__ == '__main__':
    main()