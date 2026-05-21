import pandas as pd
import json
import math
import matplotlib.pyplot as plt
import numpy as np
import re
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
import processing_plots as proc_plt

@dataclass
class ChannelResults:
    # Use a dictionary to hold an arbitrary number of channels.
    # Key could be the channel index (int) or name (str).
    channels: Dict[str, Any] = field(default_factory=dict)
    common: Optional[Dict[str, Any]] = None

@dataclass
class ProcessedResults:
    saleae: Optional[dict[str, Any]] = field(default_factory=ChannelResults)
    cyclictest: Optional[dict[str, Any]] = None
    interrupts: Optional[dict[str, Any]] = None
    pid: Optional[dict[str, Any]] = None

# Class to store the output naming and locations
class Plot_obj:
    def __init__(self, input_dir, test_type, load_type, channel, nominal_period_us, duration_s):
        self.input_dir = input_dir
        self.test_type = test_type
        self.load_type = load_type
        self.channels = channel
        self.duration_s = duration_s
        self.nominal_period_us = nominal_period_us

        # result class
        self.result = ProcessedResults()
    
    def load_and_process_datas(self):
        # Process it
        self.result.saleae = _extract_analysis_saleae(self)
        self.result.cyclictest = _extract_analysis_cyclictest(self)
        self.result.interrupts = _extract_analysis_interrupts(self)


# ---- Private Functions ----
# -------------------
def _extract_analysis_saleae(plot_obj: Plot_obj) -> ChannelResults:
    # Create the result object
    out = ChannelResults()

    # File path
    csv_path = os.path.join(plot_obj.input_dir, plot_obj.load_type, "digital.csv")

    # Load the data
    df, columns = load_csv_data(csv_path)

    # Fill the data
    for ch in plot_obj.channels:
        # Regex patern to match column name
        pattern = rf"Channel\s*{ch}\b"

        # Search by the pattern
        matched_idx, matched_col = next(
            ((i, col) for i, col in enumerate(columns) if re.search(pattern, col, re.IGNORECASE)),
            (None, None)
        )

        # Check if a column was found
        if matched_idx is not None:
            print(f"Successfully matched graph channel {ch} to column '{matched_col}'")
            out.channels[ch] = perform_timing_analysis(plot_obj, df, columns[0], matched_col)
        else:
            print(f"Warning: No column found matching pattern '{pattern}'")
            out.channels[ch] = None

    out.common = perform_phase_shift_analysis(out.channels[0]['edges_rise'], out.channels[1]['edges_rise'], plot_obj.nominal_period_us)

    return out

def _extract_analysis_cyclictest(plot_obj: Plot_obj):
    # File path
    cyclictest_path = os.path.join(plot_obj.input_dir, plot_obj.load_type, "cyclictest.json")

    # Extract data
    try:
        with open(cyclictest_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{cyclictest_path}' was not found.")
        return None
    
    # Extract thread 0 statistics
    thread_data = data['thread']['0']
    hist_data = thread_data['histogram']
    
    # Convert histogram to latency
    latencies = [int(k) for k in hist_data.keys()]
    frequencies = list(hist_data.values())

    # Calculate weighted standard deviation
    avg_lat = thread_data['avg']
    total_cycles = thread_data['cycles']
    
    if total_cycles > 0 and len(latencies) > 0:
        # Sum up the squared deviations weighted by their frequencies
        variance_sum = sum(
            freq * ((int(lat_str) - avg_lat) ** 2) 
            for lat_str, freq in hist_data.items()
        )
        std_dev = math.sqrt(variance_sum / total_cycles)
    else:
        std_dev = 0.0

    return {
        # Extract start/end dates
        't0': data['start_time'],
        't1': data['end_time'],
        
        # histogram and latency
        'histogram': hist_data,
        'latencies': latencies,
        'frequencies': frequencies,

        # Summary metrics
        'cycles': total_cycles,
        'min': thread_data['min'],
        'max': thread_data['max'],
        'avg': avg_lat,
        'std_dev': std_dev,
        'peak_to_peak': (thread_data['max'] - thread_data['min']) if len(latencies) > 0 else 0,
    }

def _extract_analysis_interrupts(plot_obj: Plot_obj):
    def parse_snapshot(file_path):
        """
        arses /proc/interrupts into a dictionary mapping IRQ/Type to counts across CPUs.
        """
        irq_dict = {}
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Snapshot file not found: {file_path}")
        
        with open(file_path, 'r') as f:
            # First line contains CPU headers (e.g., CPU0, CPU1...)
            cpu_headers = f.readline().strip().split()
            num_cpus = len(cpu_headers)
            
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                
                # Split line into maximum components based on column count
                parts = re.split(r'\s+', line_str, maxsplit=num_cpus + 1)
                if len(parts) < num_cpus + 1:
                    continue
                    
                irq_id = parts[0].rstrip(':')
                try:
                    # Dynamically collect counts across all available CPU cores
                    cpu_counts = [int(parts[i]) for i in range(1, num_cpus + 1)]
                    cpu_total = sum(cpu_counts)
                    
                    # Extract descriptive name (e.g., local timer interrupts 'LOC', 'eth0', or 'GPIO')
                    description_raw = parts[-1] if len(parts) > num_cpus + 1 else "Unknown"
                    description_split = re.split(r'\s+', description_raw, maxsplit=num_cpus + 1)
                    description = description_split[-1] if len(description_split) >= num_cpus else description_raw

                    irq_dict[irq_id] = {'cpu': np.array(cpu_counts),
                                        'cpu_total': cpu_total,
                                        'desc': description
                                        }
                except ValueError:
                    # Skip non-numeric initialization metadata rows
                    continue
        return irq_dict, num_cpus
    
    """
    Calculates absolute delta counts of interrupts handled during the run.
    """
    start_snap, num_cpus = parse_snapshot(os.path.join(plot_obj.input_dir, plot_obj.load_type, "interrupts_start.txt"))
    end_snap, _ = parse_snapshot(os.path.join(plot_obj.input_dir, plot_obj.load_type, "interrupts_end.txt"))
    
    delta_records = []
    delta_cpus_total = np.zeros(num_cpus)
    for irq, end_data in end_snap.items():
        # Safeguard in case an interrupt type wasn't present in the start snapshot
        start_data = start_snap.get(irq, {'cpu': np.zeros(num_cpus), 'cpu_total': 0})
        
        # Fixed: Real matrix subtraction (End - Start)
        delta_cpus = end_data['cpu'] - start_data['cpu']
        delta_total = end_data['cpu_total'] - start_data['cpu_total']
        delta_cpus_total = delta_cpus_total + delta_cpus
        
        # Only keep records where interrupts actually fired to keep the data clean
        if delta_total >= 0:
            delta_records.append({
                'irq': irq,
                'delta_cpu': delta_cpus.tolist(),  # Convert to list for clean DataFrame rendering
                'delta_total': delta_total,
                'description': end_data['desc']
            })
    
    # Total counts per CPU
    delta_records.append({'delta_cpus_total': delta_cpus_total.tolist()})

    return delta_records

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

def perform_timing_analysis(obj: Plot_obj, df, time_col, channel_col):
    """
    Calculates Jitter, Drift, Latency, and Phase based on a nominal period.
    """
    expected_edges = (obj.duration_s * 1_000_000) / obj.nominal_period_us
    
    # Using .fillna to ensure we don't miss an edge on row 0 if signal starts High
    prev_val = df[channel_col].shift(1).fillna(df[channel_col].iloc[0])
    
    # Detect Edges (1 -> 0 transition) - falling
    # Detect Edges (0 -> 1 transition) - rising
    falling_dt = df[(df[channel_col] == 0) & (prev_val == 1)][time_col].values
    rising_dt = df[(df[channel_col] == 1) & (prev_val == 0)][time_col].values

    # -------- NORMAL TIMING CONVERSION --------
    # Doesn't use iso8601_timestamp for time capture
    # ------------------------------------------
    # Establish T0 (the first timestamp in the dataset) to keep X-axis relative to the front
    # t0 = pd.to_datetime(falling_dt[0]).tz_localize(None)
    # Convert to microseconds and get values
    # falling_us = np.round(falling_dt * 1_000_000).astype(np.float64)
    # rising_us = np.round(rising_dt * 1_000_000).astype(np.float64)
    # ------------------------------------------

    # --- TIMESTAMP CONVERSION & NORMALIZATION ---
    # Usage of iso8601_timestamp
    # --------------------------------------------
    # Establish T0 (the first timestamp in the dataset) to keep X-axis relative to the front
    t0 = pd.to_datetime(falling_dt[0]).tz_localize(None)

    # Convert edge timestamps to datetime objects, strip timezone
    falling_pts = pd.to_datetime(falling_dt).tz_localize(None)
    rising_pts = pd.to_datetime(rising_dt).tz_localize(None)

    # Subtract T0, convert the delta to total nanoseconds (float64)
    falling_us = np.round((falling_pts - t0).total_seconds().values * 1_000_000).astype(np.float64)
    rising_us = np.round((rising_pts - t0).total_seconds().values * 1_000_000).astype(np.float64)
    # --------------------------------------------

    # Ensure alignment: Start with Falling, End with Rising
    if len(falling_us) > 0 and len(rising_us) > 0 and falling_us[0] > rising_us[0]: 
        rising_us = rising_us[1:]
        
    min_len = min(len(rising_us), len(falling_us))
    if min_len < 2:
        return {'error': "Not enough pulses detected for analysis"}
    
    # Filter out end jitter for PWM signal
    if min_len > expected_edges:
        print(f"Number of edges exceeded. Expected {expected_edges}, got {min_len}.")
        return {'error': f"Expected {expected_edges}, got {min_len}."}
    
    # Construct data
    falling_us = falling_us[:min_len]
    rising_us = rising_us[:min_len]

    # Falling Edge Metrics (N-1 samples)
    periods_fall = np.diff(falling_us)
    time_jitter_fall = falling_us[1:]
    jitter_fall = (periods_fall - obj.nominal_period_us)
    drift_fall = np.cumsum(jitter_fall)

    # Rising Edge Metrics (N-1 samples)
    # Time axis for jitter is the time of the edge that "arrived" (rising_us[1:])
    periods_rise = np.diff(rising_us)
    time_jitter_rise = rising_us[1:] 
    jitter_rise = (periods_rise - obj.nominal_period_us)
    drift_rise = np.cumsum(jitter_rise)

    # Pulse Metrics (N samples)
    # Time axis is the start of each pulse
    time_pulse = falling_us 
    pulse_widths = rising_us - falling_us
    duty_cycles = (pulse_widths.astype(float) / obj.nominal_period_us) * 100

    return {
        # Reference time
        'reference_time': t0,

        # Time Axes
        'time_jitter_rise': time_jitter_rise,  # For jitter_rise and drift_rise
        'time_jitter_fall': time_jitter_fall,  # For jitter_fall and drift_fall
        'time_pulse': time_pulse,              # For duty_cycles and pulse_widths
        'nominal_period_us': obj.nominal_period_us,
        
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

def plot_path(obj: Plot_obj, type, name, combined=False):
    # Check how to combine it
    if combined == False:
        if name == None or name == "":
            combined_path = "jitter_" + type + "_" + obj.test_type + "_" + obj.load_type + "_" + ".png"
        else:
            combined_path = "jitter_" + type + "_" + obj.test_type + "_" + obj.load_type + "_" + name + ".png"
    else:
        if name == None or name == "":
            combined_path = "jitter_" + type + "_" + obj.test_type + "_" + obj.load_type + ".png"
        else:
            combined_path = "jitter_" + type + "_" + obj.test_type + "_" + obj.load_type + "_" + name + ".png"
    
    # Combined result
    combined_path = os.path.join(obj.input_dir, combined_path)
    
    return combined_path

def plot_histograms(obj: Plot_obj, show=False):
    # Plot all histogram types
    for i in range(len(obj.channels)):
        title = "Jitter Distribution (" + obj.test_type + " under " + obj.load_type + ", Channel " + str(obj.channels[i]) + ")"
        proc_plt._plot_histogram_rise(obj.result.saleae.channels[i],
                                      plot_path(obj, "histogram", "rise"),
                                      title, None, show=show)
        proc_plt._plot_histogram_fall(obj.result.saleae.channels[i],
                                      plot_path(obj, "histogram", "fall"),
                                      title, None, show=show)
        proc_plt._plot_histogram_combined(obj.result.saleae.channels[i],
                                          plot_path(obj, "histogram", "rise_fall"),
                                          title, None, show=show)
        
    # Cyclictest histogram
    title = "Jitter Distribution CyclicTest (" + obj.test_type + " under " + obj.load_type + ")"
    proc_plt._plot_histogram_cyclic_test(obj.result.cyclictest, 
                                         plot_path(obj, "histogram", "cyclic_test"),
                                         title, None, show=show)

def plot_phase_shift_combined(obj: Plot_obj, show=False):
    title = "Latency and Phase alignment over time (" + obj.test_type + ", under " + obj.load_type + " for both channels)"
    proc_plt._plot_phase_shift_combined(obj.result.saleae.common,
                               plot_path(obj, "phase_shift", "", combined=True),
                               title, None, show=show)

def plot_signal_drift(obj: Plot_obj, show=False):
    for i in range(len(obj.channels)):
        # Individual
        title = "Cumulative Signal Drift (Relative to nominal period of " + str(obj.nominal_period_us) + " µs)"
        label = [
            f"Channel {obj.channels[i]} rise ({obj.load_type})",
            f"Channel {obj.channels[i]} fall ({obj.load_type})",
        ]
        proc_plt._plot_signal_drift(obj.result.saleae.channels[i],
                                    plot_path(obj, "signal_drift", f"rise_fall_{obj.channels[i]}"),
                                    title, label, show=show)

def plot_signal_drift_combined(obj: Plot_obj, show=False):
    title = f'Combined cumulative Signal Drift (Relative to nominal period of ' + str(obj.nominal_period_us) + ' µs)'
    label = [
        f"Channel {obj.channels[0]} ({obj.load_type})",
        f"Channel {obj.channels[1]} ({obj.load_type})",
    ]
    proc_plt._plot_signal_drift_combined(obj.result.saleae.channels[0],
                                         obj.result.saleae.channels[1],
                                         plot_path(obj, "signal_drift", f"{obj.channels[0]}_{obj.channels[1]}", combined=True),
                                         title, label, show=show)

def plot_duty_cycle_combined(obj1: Plot_obj, obj2: Plot_obj, channel, show=False, y_lim=None):
    title = f"Duty Cycle comparison of channel {obj1.channels[channel]}"
    label = [
        f"{obj1.load_type}",
        f"{obj2.load_type}"
    ]
    proc_plt._plot_duty_cycle_combined(obj1.result.saleae.channels[channel],
                                       obj2.result.saleae.channels[channel], 
                                       plot_path(obj1, "duty_cycle", f"{obj2.load_type}_{channel}",combined=True),
                                       title, label, show=show, y_lim=y_lim)

def plot_interrupts_stacked_bar(obj: Plot_obj, show=False):
    # Filter out interrupts with 0 activity to keep the plot clean
    active_interrupts = [
        item for item in obj.result.interrupts
        if item.get('delta_total', 0) > 0
    ]

    # Determine number of CPUs dynamically from the remaining data
    if active_interrupts:
        num_cpus = len(active_interrupts[0]['delta_cpu'])
        cpu_indices = [f"CPU{i}" for i in range(num_cpus)]

        # Restructure data: { 'irq': [CPU0_val, CPU1_val, ...] }
        plot_dict = {f"{item['irq']} ({item['description']})": item['delta_cpu'] for item in active_interrupts}
        df_matrix = pd.DataFrame(plot_dict, index=cpu_indices)

        # /proc/interrupts bar chart
        proc_plt._plot_interrupts_stacked_bar(df_matrix,
                                              plot_path(obj, "bar", "proc_interrupts"),
                                              None, None, show=show)