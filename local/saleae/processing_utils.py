import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import re
import os

# Class to store the output naming and locations
class Plot_obj:
    def __init__(self, input_dir, test_type, load_type, channel, nominal_period_us):
        self.input_dir = input_dir
        self.csv_path = os.path.join(input_dir, load_type, "digital.csv")
        self.test_type = test_type
        self.load_type = load_type
        self.channel = channel
        self.nominal_period_us = nominal_period_us
        self.jitter_title = "Jitter Distribution (" + test_type + " under " + load_type + ", Channel " + str(channel) + ")"

        # Load the data
        df, columns = load_csv_data(self.csv_path)

        # Process it
        self.result = _extract_analysis(self, df, columns)


# ---- Private Functions ----
# -------------------
def _extract_analysis(self, df, columns):
    # Regex patern to match column name
    pattern = rf"Channel\s*{self.channel}\b"

    # Search by the pattern
    matched_idx, matched_col = next(
        ((i, col) for i, col in enumerate(columns) if re.search(pattern, col, re.IGNORECASE)),
        (None, None)
    )

    # Check if a column was found
    if matched_idx is not None:
        print(f"Successfully matched graph channel {self.channel} to column '{matched_col}'")
        result = perform_timing_analysis(df, columns[0], matched_col, self.nominal_period_us)
    else:
        print(f"Warning: No column found matching pattern '{pattern}'")
        result = None

    return result


# ---- Public Functions ----
# -------------------
def load_csv_data(csv_path):
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
    columns = df.columns.tolist()

    return df, columns

def perform_timing_analysis(df, time_col, channel_col, nominal_period_us):
    """
    Calculates Jitter, Drift, Latency, and Phase based on a nominal period.
    """
    # Using .fillna to ensure we don't miss an edge on row 0 if signal starts High
    prev_val = df[channel_col].shift(1).fillna(df[channel_col].iloc[0])

    # Detect Edges (0 -> 1 transition) - rising
    # Detect Edges (1 -> 0 transition) - falling
    # rising = df[(df[channel_col] == 1) & (df[channel_col].shift(1) == 0)][time_col].values
    # falling = df[(df[channel_col] == 0) & (df[channel_col].shift(1) == 1)][time_col].values
    rising = df[(df[channel_col] == 1) & (prev_val == 0)][time_col].values
    falling = df[(df[channel_col] == 0) & (prev_val == 1)][time_col].values

    # Convert to microseconds and get values
    rising_us = np.round(rising * 1_000_000).astype(np.float64)
    falling_us = np.round(falling * 1_000_000).astype(np.float64)

    # Ensure alignment: Start with Rising, End with Falling
    if len(falling_us) > 0 and len(rising_us) > 0 and falling_us[0] < rising_us[0]: 
        falling_us = falling_us[1:]
        
    min_len = min(len(rising_us), len(falling_us))
    if min_len < 2:
        return {"error": "Not enough pulses detected for analysis"}
    
    rising_us = rising_us[:min_len]
    falling_us = falling_us[:min_len]

    # 1. Rising Edge Metrics (N-1 samples)
    # Time axis for jitter is the time of the edge that "arrived" (rising_us[1:])
    periods_rise = np.diff(rising_us)
    time_jitter_rise = rising_us[1:] 
    jitter_rise = (periods_rise - nominal_period_us)
    drift_rise = np.cumsum(jitter_rise)

    # 2. Falling Edge Metrics (N-1 samples)
    periods_fall = np.diff(falling_us)
    time_jitter_fall = falling_us[1:]
    jitter_fall = (periods_fall - nominal_period_us)
    drift_fall = np.cumsum(jitter_fall)

    # 3. Pulse Metrics (N samples)
    # Time axis is the start of each pulse
    time_pulse = rising_us 
    pulse_widths = falling_us - rising_us
    duty_cycles = (pulse_widths.astype(float) / nominal_period_us) * 100

    return {
        # Time Axes
        'time_jitter_rise': time_jitter_rise,  # For jitter_rise and drift_rise
        'time_jitter_fall': time_jitter_fall,  # For jitter_fall and drift_fall
        'time_pulse': time_pulse,              # For duty_cycles and pulse_widths
        'nominal_period_us': nominal_period_us,
        
        # Data Arrays
        'edges_rise': rising_us,
        'edges_fall': falling_us,
        'jitter_rise': jitter_rise,
        'jitter_fall': jitter_fall,
        'drifts_rise': drift_rise,
        'drifts_fall': drift_fall,
        'duty_cycles': duty_cycles,
        'pulse_widths': pulse_widths,
        
        # Metadata & Stats
        'channel': channel_col,
        'mean_jitter_rise_us': jitter_rise.mean() if len(jitter_rise) > 0 else 0,
        'std_dev_rise_us': jitter_rise.std() if len(jitter_rise) > 0 else 0,
        'max_jitter_rise_us': jitter_rise.max() if len(jitter_rise) > 0 else 0,
        'min_jitter_rise_us': jitter_rise.min() if len(jitter_rise) > 0 else 0,
        'peak_to_peak_jitter_rise_us': (jitter_rise.max() - jitter_rise.min()) if len(jitter_rise) > 0 else 0,
        'mean_jitter_fall_us': jitter_fall.mean() if len(jitter_fall) > 0 else 0,
        'std_dev_fall_us': jitter_fall.std() if len(jitter_fall) > 0 else 0,
        'max_jitter_fall_us': jitter_fall.max() if len(jitter_fall) > 0 else 0,
        'min_jitter_fall_us': jitter_fall.min() if len(jitter_fall) > 0 else 0,
        'peak_to_peak_jitter_fall_us': (jitter_fall.max() - jitter_fall.min()) if len(jitter_fall) > 0 else 0,
        'sample_count': len(df)
    }

def perform_phase_shift_analysis(edges0, edges1, nominal_period_us):
    # Cross-Channel Calculations (Latency & Phase)
    # Ensure we compare the same number of pulses
    min_len = min(len(edges0), len(edges1))
    latency = edges1[:min_len] - edges0[:min_len]
    phase_diff = (latency / nominal_period_us) * 360

    return {
        'latency': latency,
        'phase': phase_diff,
        'time_axis': edges0[:min_len]
    }

def plot_path(plot, type, name, combined=False):
    if combined == False:
        if name == None or name == "":
            combined_path = "jitter_" + type + "_" + plot.test_type + "_" + plot.load_type + "_" + str(plot.channel) + ".png"
        else:
            combined_path = "jitter_" + type + "_" + plot.test_type + "_" + plot.load_type + "_" + name + "_" + str(plot.channel) + ".png"
    else:
        if name == None or name == "":
            combined_path = "jitter_" + type + "_" + plot.test_type + "_" + plot.load_type + ".png"
        else:
            combined_path = "jitter_" + type + "_" + plot.test_type + "_" + plot.load_type + "_" + name + ".png"
    combined_path = os.path.join(plot.input_dir, combined_path)
    return combined_path

def plot_histogram_rise(stats, title, output_file, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    ax.hist(stats['jitter_rise'], bins='auto', density=True, alpha=0.75, label='Jitter Distribution (Rise)')

    # Add a vertical line for the mean
    ax.axvline(stats['mean_jitter_rise_us'], color='r', linestyle='--', linewidth=2, label=f"Mean: {stats['mean_jitter_rise_us']:.2f} µs")

    # --- Formatting the Plot ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({stats['nominal_period_us']} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {stats['sample_count']}\n"
        f"Std Dev: {stats['std_dev_rise_us']:.2f} µs\n"
        f"Min Jitter: {stats['min_jitter_rise_us']:.2f} µs\n"
        f"Max Jitter (WCET): {stats['max_jitter_rise_us']:.2f} µs\n"
        f"Peak-to-Peak: {stats['peak_to_peak_jitter_rise_us']:.2f} µs"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
        
def plot_histogram_fall(stats, title, output_file, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    ax.hist(stats['jitter_fall'], bins='auto', density=True, alpha=0.75, label='Jitter Distribution (Fall)')

    # Add a vertical line for the mean
    ax.axvline(stats['mean_jitter_fall_us'], color='r', linestyle='--', linewidth=2, label=f"Mean: {stats['mean_jitter_fall_us']:.2f} µs")

    # --- Formatting the Plot ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({stats['nominal_period_us']} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {stats['sample_count']}\n"
        f"Std Dev: {stats['std_dev_fall_us']:.2f} µs\n"
        f"Min Jitter: {stats['min_jitter_fall_us']:.2f} µs\n"
        f"Max Jitter (WCET): {stats['max_jitter_fall_us']:.2f} µs\n"
        f"Peak-to-Peak: {stats['peak_to_peak_jitter_fall_us']:.2f} µs"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory

def plot_histogram_combined(stats, title, output_file, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax2 = ax1.twinx()

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    ax1.hist(stats['jitter_rise'], bins='auto', density=True, color='r', alpha=0.75, label='Jitter Distribution Rise')
    ax2.hist(stats['jitter_fall'], bins='auto', density=True, color='b', alpha=0.45, label='Jitter Distribution Fall')

    # Add a vertical line for the mean
    ax1.axvline(stats['mean_jitter_rise_us'], color='r', linestyle='dashed', linewidth=2, label=f"Mean: {stats['mean_jitter_fall_us']:.2f} µs")
    ax2.axvline(stats['mean_jitter_fall_us'], color='b', linestyle='dotted', linewidth=2, label=f"Mean: {stats['mean_jitter_fall_us']:.2f} µs")

    # --- Formatting the Plot ---
    ax1.set_title(title, fontsize=16)
    ax1.set_xlabel(f'Jitter (µs) from Nominal Period ({stats['nominal_period_us']} µs)', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.grid(True)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    # Add a text box with detailed statistics
    stats_rise_fall_text = (
        f"Samples: {stats['sample_count']}\n"
        f"Std Dev Rise: {stats['std_dev_rise_us']:.2f} µs\n"
        f"Std Dev Fall: {stats['std_dev_fall_us']:.2f} µs\n"
        f"Min Jitter Rise: {stats['min_jitter_rise_us']:.2f} µs\n"
        f"Min Jitter Fall: {stats['min_jitter_fall_us']:.2f} µs\n"
        f"Max Jitter Rise (WCET): {stats['max_jitter_rise_us']:.2f} µs\n"
        f"Max Jitter Fall (WCET): {stats['max_jitter_fall_us']:.2f} µs\n"
        f"Peak-to-Peak Rise: {stats['peak_to_peak_jitter_rise_us']:.2f} µs\n"
        f"Peak-to-Peak Fall: {stats['peak_to_peak_jitter_fall_us']:.2f} µs"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax1.text(0.02, 0.97, stats_rise_fall_text, transform=ax1.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory

def plot_phase_shift_combined(phase, label, output_file, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    ax1.plot(phase['time_axis'], phase['latency'], alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(phase['time_axis'], phase['phase'], alpha=0.2, color='red', label=f"{label[1]}")

    # --- Formatting the Plot ---
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Latency [us]', color='blue')
    ax2.set_ylabel('Phase Difference [Degrees]', color='red')
    plt.title('Latency and Phase Alignment Over Time')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory

def plot_signal_drift(plot, label, output_file, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    ax1.plot(plot['time_jitter_rise'], plot['drifts_rise'], alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(plot['time_jitter_fall'], plot['drifts_fall'], alpha=0.2, color='red', label=f"{label[1]}")

    # --- Formatting the Plot ---
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Accumulated Error [us]', color='blue')
    ax2.set_ylabel('Accumulated Error [us]', color='red')
    plt.title('Cumulative Signal Drift (Relative to nominal period of ' + str(plot['nominal_period_us']) + ' µs)')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory

def plot_signal_drift_combined(plot_1, plot_2, label, output_file, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()

    # for phase in phase_idle.values():
    ax1.plot(plot_1['time_jitter_rise'], plot_1['drifts_rise'], alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(plot_2['time_jitter_rise'], plot_2['drifts_rise'], alpha=0.2, color='red', label=f"{label[1]}")

    # --- Formatting the Plot ---
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Accumulated Error [us]', color='blue')
    ax2.set_ylabel('Accumulated Error [us]', color='red')
    plt.title('Combined cumulative Signal Drift (Relative to nominal period of ' + str(plot_1['nominal_period_us']) + ' µs)')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory

def plot_duty_cycle_combined(stats_idle, stats_load, title, output_file, show=False, y_lim=None):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the plot
    # The number of bins can be adjusted. 'auto' is a good starting point.
    ax.plot(stats_idle['time_pulse'], stats_idle['duty_cycles'], marker='.', linestyle='dashed', color='r', alpha=0.75, label='Duty Cycle Idle')
    ax.plot(stats_load['time_pulse'], stats_load['duty_cycles'], marker='.', linestyle='dotted', color='b', alpha=0.45, label='Duty Cycle Load')

    # Add a vertical line for the mean
    ax.axhline(50, color='black', linestyle='dashed', linewidth=1, alpha=0.3, label=f"Target (50%)")

    # --- Formatting the Plot ---
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Time [s]', fontsize=12)
    ax.set_ylabel('Duryt Cycle (%)', fontsize=12)
    ax.grid(True)
    ax.legend(loc='best')

    # --- SET Y AXIS RANGE ---
    # ax.set_ylim(50)
    # Change this in your plotting function to see the tiny fluctuations
    ax.set_ylim(y_lim)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory