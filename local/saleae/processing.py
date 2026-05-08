import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import argparse
import os # Import os module for path manipulation

# Class to store the output naming and locations
class Graph:
    def __init__(self, input_dir, test_type, load_type, channel):
        self.input_dir = input_dir
        self.csv_path = os.path.join(input_dir, load_type, "digital.csv")
        self.test_type = test_type
        self.load_type = load_type
        self.jitter_title = "Jitter Distribution (" + test_type + " under " + load_type + ")"
        self.jitter_file_name = "jitter_histogram_" + test_type + "_" + load_type + ".png"
        self.jitter_file_path = os.path.join(input_dir, self.jitter_file_name)

# ---- Functions ----
# -------------------
def analyze_jitter(csv_path, nominal_period):
    """
    Loads period data from a Saleae CSV, calculates jitter,
    and returns key statistics.
    """
    try:
        # Saleae period exports have one column, usually named 'Time [s]' or the measurement name
        df = pd.read_csv(csv_path)
        # We rename the column for consistency, assuming it's the first one.
        if df.empty:
            print(f"Warning: CSV file '{csv_path}' is empty. Skipping analysis.")
            return None, None
        df.rename(columns={df.columns[0]: 'period_s'}, inplace=True)
    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        return None

    # Print the column names
    print(df.columns.tolist())
    columns = df.columns.tolist()

    # Calculate jitter in microseconds (µs)
    # Jitter = (Measured Period - Nominal Period)
    # df['jitter_us'] = (df['period_s'] - nominal_period) * 1_000_000
    # Identify 'Channel 0' toggles
    toggles = df[df[columns[1]].diff() != 0].copy()
    # Calculte the time between toggles (intervals)
    toggles['interval'] = toggles[columns[0]].diff()
    # Remove the first NaN values
    intervals = toggles['interval'].dropna()

    # Calculate key statistics
    stats = {
        # 'mean_jitter_us': df['jitter_us'].mean(),
        # 'std_dev_us': df['jitter_us'].std(),
        # 'max_jitter_us': df['jitter_us'].max(),
        # 'min_jitter_us': df['jitter_us'].min(),
        # 'peak_to_peak_jitter_us': df['jitter_us'].max() - df['jitter_us'].min(),
        # 'sample_count': len(df)
        'mean_jitter_us': intervals.mean(),
        'std_dev_us': intervals.std(),
        'max_jitter_us': intervals.max(),
        'min_jitter_us': intervals.min(),
        'peak_to_peak_jitter_us': intervals.max() - intervals.min(),
        'sample_count': len(df)
    }

    # return df['jitter_us'], stats
    return intervals, stats

def plot_histogram(jitter_data, stats, title, output_file):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    ax.hist(jitter_data, bins='auto', density=True, alpha=0.75, label='Jitter Distribution')

    # Add a vertical line for the mean
    ax.axvline(stats['mean_jitter_us'], color='r', linestyle='--', linewidth=2, label=f"Mean: {stats['mean_jitter_us']:.2f} µs")

    # --- Formatting the Plot ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Jitter (µs) from Nominal Period', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {stats['sample_count']}\n"
        f"Std Dev: {stats['std_dev_us']:.2f} µs\n"
        f"Min Jitter: {stats['min_jitter_us']:.2f} µs\n"
        f"Max Jitter (WCET): {stats['max_jitter_us']:.2f} µs\n"
        f"Peak-to-Peak: {stats['peak_to_peak_jitter_us']:.2f} µs"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig) # Close the figure to free up memory
    print(f"Histogram saved to '{output_file}'")

# ------- MAIN ------
# -------------------
def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Automate processing of Saleae capture.")
    parser.add_argument('--duration', type=int, required=True, help='Capture duration in seconds.')
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
    graphs = [
        Graph(args.input_dir, test_type, "idle"),
        Graph(args.input_dir, test_type, "load")
    ]

    # --- Data Analysis ---
    for graph in graphs:
        jitter_values, statistics = analyze_jitter(graph.csv_path, args.duration)
        if jitter_values is not None:
            print("\n--- Jitter Analysis Results for ", graph.load_type, " Test---")
            for key, value in statistics.items():
                print(f"{key.replace('_', ' ').title()}: {value:.2f}")
            print("-----------------------------\n")
            plot_histogram(jitter_values, statistics, graph.jitter_title, graph.jitter_file_path)

if __name__ == '__main__':
    main()