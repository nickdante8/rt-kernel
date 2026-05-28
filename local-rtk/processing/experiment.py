import pandas as pd
import json
import os
import re
import numpy as np
from typing import Any

from models import ExperimentConfig, ExperimentDataset
import plots as proc_plt
import saleae as proc_sl
import linux as proc_linux

def load_csv_data(csv_path):
    """
    Loads period data from a Saleae CSV, calculates jitter,
    and returns key statistics.
    """
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            print(f"Warning: CSV file '{csv_path}' is empty. Skipping analysis.")
            return None, None
        df.rename(columns={df.columns[0]: 'period_s'}, inplace=True)
    except FileNotFoundError:
        print(f"Error: The file '{csv_path}' was not found.")
        return None, None

    columns = df.columns.tolist()
    return df, columns

class ExperimentProcessor:
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.dataset = ExperimentDataset(config=config)

    def load_and_process_datas(self):
        self._extract_analysis_saleae()
        self.dataset.cyclictest = self._extract_analysis_cyclictest()
        self.dataset.proc_interrupts = self._extract_analysis_interrupts()
        self.dataset.mpstat = self._extract_analysis_mpstat()

    def _extract_analysis_saleae(self):
        csv_path = os.path.join(self.config.input_dir, self.config.load_type, "digital.csv")
        df, columns = load_csv_data(csv_path)

        if df is None:
            return

        for ch in self.config.channels:
            pattern = rf"Channel\s*{ch}\b"
            matched_idx, matched_col = next(
                ((i, col) for i, col in enumerate(columns) if re.search(pattern, col, re.IGNORECASE)),
                (None, None)
            )

            if matched_idx is not None:
                print(f"Successfully matched graph channel {ch} to column '{matched_col}'")
                self.dataset.saleae[ch] = proc_sl.timing_analysis(self.config, df, columns[0], matched_col)
            else:
                print(f"Warning: No column found matching pattern '{pattern}'")

        if 0 in self.dataset.saleae and 1 in self.dataset.saleae:
            self.dataset.saleae_common = proc_sl.phase_shift_analysis(
                self.dataset.saleae[0].edges_rise, 
                self.dataset.saleae[1].edges_rise, 
                self.config.nominal_period_us
            )

    def _extract_analysis_cyclictest(self):
        cyclictest_path = os.path.join(self.config.input_dir, self.config.load_type, "cyclictest.json")
        try:
            with open(cyclictest_path, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"Error: The file '{cyclictest_path}' was not found.")
            return None
        
        return proc_linux.cyclictest(data)

    def _extract_analysis_interrupts(self):
        def parse_snapshot(file_path):
            irq_dict = {}
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Snapshot file not found: {file_path}")
            
            with open(file_path, 'r') as f:
                cpu_headers = f.readline().strip().split()
                num_cpus = len(cpu_headers)
                
                for line in f:
                    line_str = line.strip()
                    if not line_str:
                        continue
                    
                    parts = re.split(r'\s+', line_str, maxsplit=num_cpus + 1)
                    if len(parts) < num_cpus + 1:
                        continue
                        
                    irq_id = parts[0].rstrip(':')
                    try:
                        cpu_counts = [int(parts[i]) for i in range(1, num_cpus + 1)]
                        cpu_total = sum(cpu_counts)
                        
                        description_raw = parts[-1] if len(parts) > num_cpus + 1 else "Unknown"
                        description_split = re.split(r'\s+', description_raw, maxsplit=num_cpus + 1)
                        description = description_split[-1] if len(description_split) >= num_cpus else description_raw

                        irq_dict[irq_id] = {'cpu': np.array(cpu_counts),
                                            'cpu_total': cpu_total,
                                            'desc': description
                                            }
                    except ValueError:
                        continue
            return irq_dict, num_cpus
        
        try:
            start_snap, num_cpus = parse_snapshot(os.path.join(self.config.input_dir, self.config.load_type, "interrupts_start.txt"))
            end_snap, _ = parse_snapshot(os.path.join(self.config.input_dir, self.config.load_type, "interrupts_end.txt"))
            return proc_linux.proc_interrupts(start_snap, end_snap, num_cpus)
        except FileNotFoundError as e:
            print(e)
            return None

    def _extract_analysis_mpstat(self):
        mpstat_sum_itr_path = os.path.join(self.config.input_dir, self.config.load_type, "mpstat_all.log")
        try:
            with open(mpstat_sum_itr_path, 'r') as file:
                data = json.load(file)
        except FileNotFoundError:
            print(f"Error: The file '{mpstat_sum_itr_path}' was not found.")
            return None
        
        return proc_linux.mpstat(data)

    def generate_all_plots(self, show=False):
        self.plot_histograms(show)
        self.plot_phase_shift_combined(show)
        self.plot_signal_drift(show)
        self.plot_signal_drift_combined(show)
        self.plot_interrupts_stacked_bar(show)

    def plot_histograms(self, show=False):
        for ch in self.config.channels:
            if ch in self.dataset.saleae:
                title = f"Jitter Distribution ({self.config.test_type} under {self.config.load_type}, Channel {ch})"
                proc_plt.plot_histogram_rise(self.dataset.saleae[ch],
                                            proc_plt.plot_path(self.config, "histogram", f"rise_{ch}"),
                                            title, None, show=show)
                proc_plt.plot_histogram_fall(self.dataset.saleae[ch],
                                            proc_plt.plot_path(self.config, "histogram", f"fall_{ch}"),
                                            title, None, show=show)
                proc_plt.plot_histogram_combined(self.dataset.saleae[ch],
                                                proc_plt.plot_path(self.config, "histogram", f"rise_fall_{ch}"),
                                                title, None, show=show)
            
        if self.dataset.cyclictest:
            title = f"Jitter Distribution CyclicTest ({self.config.test_type} under {self.config.load_type})"
            proc_plt.plot_histogram_cyclic_test(self.dataset.cyclictest, 
                                                proc_plt.plot_path(self.config, "histogram", "cyclic_test"),
                                                title, None, show=show)

    def plot_phase_shift_combined(self, show=False):
        if self.dataset.saleae_common:
            title = f"Latency and Phase alignment over time ({self.config.test_type}, under {self.config.load_type} for both channels)"
            proc_plt.plot_phase_shift_combined(self.dataset.saleae_common,
                                    proc_plt.plot_path(self.config, "phase_shift", "", combined=True),
                                    title, None, show=show)

    def plot_signal_drift(self, show=False):
        for ch in self.config.channels:
            if ch in self.dataset.saleae:
                title = f"Cumulative Signal Drift (Relative to nominal period of {self.config.nominal_period_us} µs)"
                label = [
                    f"Channel {ch} rise ({self.config.load_type})",
                    f"Channel {ch} fall ({self.config.load_type})",
                ]
                proc_plt.plot_signal_drift(self.dataset.saleae[ch],
                                            proc_plt.plot_path(self.config, "signal_drift", f"rise_fall_{ch}"),
                                            title, label, show=show)

    def plot_signal_drift_combined(self, show=False):
        if len(self.config.channels) >= 2:
            ch0, ch1 = self.config.channels[0], self.config.channels[1]
            if ch0 in self.dataset.saleae and ch1 in self.dataset.saleae:
                title = f'Combined cumulative Signal Drift (Relative to nominal period of {self.config.nominal_period_us} µs)'
                label = [
                    f"Channel {ch0} ({self.config.load_type})",
                    f"Channel {ch1} ({self.config.load_type})",
                ]
                proc_plt.plot_signal_drift_combined(self.dataset.saleae[ch0],
                                                    self.dataset.saleae[ch1],
                                                    proc_plt.plot_path(self.config, "signal_drift", f"{ch0}_{ch1}", combined=True),
                                                    title, label, show=show)

    def plot_interrupts_stacked_bar(self, show=False):
        if not self.dataset.proc_interrupts:
            return
            
        active_interrupts = [
            item for item in self.dataset.proc_interrupts
            if item.get('delta_total', 0) > 0
        ]

        if active_interrupts:
            num_cpus = len(active_interrupts[0]['delta_cpu'])
            cpu_indices = [f"CPU{i}" for i in range(num_cpus)]

            plot_dict = {f"{item['irq']} ({item['description']})": item['delta_cpu'] for item in active_interrupts}
            df_matrix = pd.DataFrame(plot_dict, index=cpu_indices)

            title = f"Interrupt Load Distribution per Processor Core ({self.config.load_type})"
            proc_plt.plot_interrupts_stacked_bar(df_matrix,
                                                  proc_plt.plot_path(self.config, "bar", "proc_interrupts"),
                                                  title, None, show=show)

class ExperimentPlotter:
    @staticmethod
    def plot_duty_cycle_combined(obj1: ExperimentProcessor, obj2: ExperimentProcessor, channel: int, show=False, y_lim=None):
        if channel in obj1.dataset.saleae and channel in obj2.dataset.saleae:
            title = f"Duty Cycle comparison of channel {channel}"
            label = [
                f"{obj1.config.load_type}",
                f"{obj2.config.load_type}"
            ]
            proc_plt.plot_duty_cycle_combined(obj1.dataset.saleae[channel],
                                              obj2.dataset.saleae[channel], 
                                              proc_plt.plot_path(obj1.config, "duty_cycle", f"{obj2.config.load_type}_{channel}",combined=True),
                                              title, label, show=show, y_lim=y_lim)
