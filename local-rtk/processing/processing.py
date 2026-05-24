import pandas as pd
import json
import math
import matplotlib.pyplot as plt
import numpy as np
import re
import os
from dataclasses import dataclass, field
from typing import Any, Optional, Dict, List
import plots as proc_plt
import saleae as proc_sl
import linux as proc_linux

# ---- Classes ----
# -------------------
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
    mpstat: Optional[dict[str, Any]] = None

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
        self.result.mpstat = _extract_analysis_mpstat(self)


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
            out.channels[ch] = proc_sl.timing_analysis(plot_obj, df, columns[0], matched_col)
        else:
            print(f"Warning: No column found matching pattern '{pattern}'")
            out.channels[ch] = None

    out.common = proc_sl.phase_shift_analysis(out.channels[0]['edges_rise'], out.channels[1]['edges_rise'], plot_obj.nominal_period_us)

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
    
    return proc_linux.cyclictest(data)

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

    return proc_linux.proc_interrupts(start_snap, end_snap, num_cpus)

def _extract_analysis_mpstat(plot_obj: Plot_obj):
    # File path
    mpstat_sum_itr_path = os.path.join(plot_obj.input_dir, plot_obj.load_type, "mpstat_sum_itr.log")

    # Extract data
    try:
        with open(mpstat_sum_itr_path, 'r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f"Error: The file '{mpstat_sum_itr_path}' was not found.")
        return None
    
    # Call and process mpstat
    
    return None

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

def plot_histograms(obj: Plot_obj, show=False):
    # Plot all histogram types
    for i in range(len(obj.channels)):
        title = "Jitter Distribution (" + obj.test_type + " under " + obj.load_type + ", Channel " + str(obj.channels[i]) + ")"
        proc_plt._plot_histogram_rise(obj.result.saleae.channels[i],
                                      proc_plt.plot_path(obj, "histogram", f"rise_{obj.channels[i]}"),
                                      title, None, show=show)
        proc_plt._plot_histogram_fall(obj.result.saleae.channels[i],
                                      proc_plt.plot_path(obj, "histogram", f"fall_{obj.channels[i]}"),
                                      title, None, show=show)
        proc_plt._plot_histogram_combined(obj.result.saleae.channels[i],
                                          proc_plt.plot_path(obj, "histogram", f"rise_fall_{obj.channels[i]}"),
                                          title, None, show=show)
        
    # Cyclictest histogram
    title = "Jitter Distribution CyclicTest (" + obj.test_type + " under " + obj.load_type + ")"
    proc_plt._plot_histogram_cyclic_test(obj.result.cyclictest, 
                                         proc_plt.plot_path(obj, "histogram", "cyclic_test"),
                                         title, None, show=show)

def plot_phase_shift_combined(obj: Plot_obj, show=False):
    title = "Latency and Phase alignment over time (" + obj.test_type + ", under " + obj.load_type + " for both channels)"
    proc_plt._plot_phase_shift_combined(obj.result.saleae.common,
                               proc_plt.plot_path(obj, "phase_shift", "", combined=True),
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
                                    proc_plt.plot_path(obj, "signal_drift", f"rise_fall_{obj.channels[i]}"),
                                    title, label, show=show)

def plot_signal_drift_combined(obj: Plot_obj, show=False):
    title = f'Combined cumulative Signal Drift (Relative to nominal period of ' + str(obj.nominal_period_us) + ' µs)'
    label = [
        f"Channel {obj.channels[0]} ({obj.load_type})",
        f"Channel {obj.channels[1]} ({obj.load_type})",
    ]
    proc_plt._plot_signal_drift_combined(obj.result.saleae.channels[0],
                                         obj.result.saleae.channels[1],
                                         proc_plt.plot_path(obj, "signal_drift", f"{obj.channels[0]}_{obj.channels[1]}", combined=True),
                                         title, label, show=show)

def plot_duty_cycle_combined(obj1: Plot_obj, obj2: Plot_obj, channel, show=False, y_lim=None):
    title = f"Duty Cycle comparison of channel {obj1.channels[channel]}"
    label = [
        f"{obj1.load_type}",
        f"{obj2.load_type}"
    ]
    proc_plt._plot_duty_cycle_combined(obj1.result.saleae.channels[channel],
                                       obj2.result.saleae.channels[channel], 
                                       proc_plt.plot_path(obj1, "duty_cycle", f"{obj2.load_type}_{channel}",combined=True),
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

        title = f"Interrupt Load Distribution per Processor Core ({obj.load_type})"
        # /proc/interrupts bar chart
        proc_plt._plot_interrupts_stacked_bar(df_matrix,
                                              proc_plt.plot_path(obj, "bar", "proc_interrupts"),
                                              title, None, show=show)