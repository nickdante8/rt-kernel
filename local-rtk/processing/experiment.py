import pandas as pd
import json
import os
import re
import numpy as np
from typing import Any

from models import ExperimentConfig, ExperimentDataset, SyncMetadata
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
        self._extract_analysis_sync()
        self.dataset.cyclictest = self._extract_analysis_cyclictest()
        self.dataset.proc_interrupts = self._extract_analysis_interrupts()
        self.dataset.mpstat = self._extract_analysis_mpstat()
        self.dataset.pidstat = proc_linux.pidstat(os.path.join(self.config.input_dir, self.config.load_type, 'pidstat.log'))
        self.dataset.vmstat = proc_linux.vmstat(os.path.join(self.config.input_dir, self.config.load_type, 'vmstat.log'))
        self.dataset.iperf3 = proc_linux.iperf3(os.path.join(self.config.input_dir, self.config.load_type, 'network_results.json'))
        self.dataset.fio = proc_linux.fio(os.path.join(self.config.input_dir, self.config.load_type))

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

    def _extract_analysis_sync(self):        
        # 1. Parse pid_chrt.log
        pid_chrt_path = os.path.join(self.config.input_dir, self.config.load_type, "pid_chrt.log")
        pid_policies = proc_linux.parse_pid_chrt(pid_chrt_path)
        
        # 2. Extract software start time (CLOCK_MONOTONIC)
        led_edges_path = os.path.join(self.config.input_dir, self.config.load_type, 'led_toggle_edges.csv')
        t_software = proc_linux.parse_led_toggle_edges(led_edges_path)
        
        # 3. Extract hardware start time (Saleae)
        t_hardware = 0.0
        # Channel 0 is the software pin. The first toggle is HIGH (state 1), so rising edge.
        if 0 in self.dataset.saleae and len(self.dataset.saleae[0].edges_rise) > 0:
            t_hardware = self.dataset.saleae[0].edges_rise[0]
            
        offset = t_software - t_hardware if t_software > 0.0 else 0.0
        
        self.dataset.sync_metadata = SyncMetadata(
            clock_monotonic_offset_s=offset,
            pid_policies=pid_policies
        )
        
        # Print validation warning if any monitoring tool is NOT in SCHED_OTHER
        for pid, policy in pid_policies.items():
            if policy != 'SCHED_OTHER':
                print(f"WARNING: Process {pid} has policy {policy}. It should be SCHED_OTHER to avoid interfering with PREEMPT_RT tasks.")

    def _extract_analysis_cyclictest(self):
        cyclictest_json_path = os.path.join(self.config.input_dir, self.config.load_type, "cyclictest.json")
        cyclictest_log_path = os.path.join(self.config.input_dir, self.config.load_type, "cyclictest.log")
        try:
            with open(cyclictest_json_path, 'r') as file:
                data = json.load(file)
            return proc_linux.cyclictest(data, log_file=cyclictest_log_path)
        except Exception as e:
            return None

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
        mpstat_all_path = os.path.join(self.config.input_dir, self.config.load_type, "mpstat_all.log")
        mpstat_sum_itr_path = os.path.join(self.config.input_dir, self.config.load_type, "mpstat_sum_itr.log")
        
        data = None
        try:
            with open(mpstat_all_path, 'r') as file:
                data = json.load(file)
        except Exception as e:
            print(f"Error loading {mpstat_all_path}: {e}")
            
        try:
            with open(mpstat_sum_itr_path, 'r') as file:
                itr_data = json.load(file)
                if data and 'sysstat' in data and 'sysstat' in itr_data:
                    # Merge statistics
                    stats_all = data['sysstat']['hosts'][0]['statistics']
                    stats_itr = itr_data['sysstat']['hosts'][0]['statistics']
                    
                    # Assuming they have the same length and align by timestamp
                    for i in range(min(len(stats_all), len(stats_itr))):
                        stats_all[i].update(stats_itr[i])
                    return proc_linux.mpstat(stats_all)
        except Exception as e:
            pass # It might not exist, that's fine
            
        if data and 'sysstat' in data:
            return proc_linux.mpstat(data['sysstat']['hosts'][0]['statistics'])
        return None
    
    def generate_all_plots(self, show=False):
        self.plot_histograms(show)
        self.plot_phase_shift_combined(show)
        self.plot_signal_drift(show)
        self.plot_signal_drift_combined(show)
        self.plot_interrupts_stacked_bar(show)

        self.plot_vmstat_cpu(show)
        self.plot_vmstat_system_activity(show)
        self.plot_vmstat_io(show)
        self.plot_mpstat_interrupts(show)
        self.plot_pidstat_cpu(show)
        self.plot_network_throughput(show)
        self.plot_fio_hist(show)
        self.plot_fio_bandwidth(show)
        self.plot_fio_iops(show)
        
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
            proc_plt.plot_histogram_cyclictest(self.dataset.cyclictest, 
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
            item for item in self.dataset.proc_interrupts.records
            if getattr(item, 'delta_total', 0) > 0
        ]
        
        if active_interrupts:
            num_cpus = len(active_interrupts[0].delta_cpu)
            cpu_indices = [f"CPU{i}" for i in range(num_cpus)]
            plot_dict = {f"{item.irq} ({item.description})": item.delta_cpu for item in active_interrupts}
            
            df_matrix = pd.DataFrame(plot_dict, index=cpu_indices)

            title = f"Interrupt Load Distribution per Processor Core ({self.config.load_type})"
            proc_plt.plot_interrupts_stacked_bar(df_matrix,
                                                  proc_plt.plot_path(self.config, "bar", "proc_interrupts"),
                                                  title, None, show=show)

    def plot_vmstat_cpu(self, show=False):
        if not self.dataset.vmstat:
            return
        out = proc_plt.plot_path(self.config, 'vmstat_cpu', '')
        proc_plt.plot_vmstat_cpu(self.dataset.vmstat, out, title=f'CPU Breakdown Over Time ({self.config.load_type})', show=show)

    def plot_vmstat_system_activity(self, show=False):
        if not self.dataset.vmstat:
            return
        out = proc_plt.plot_path(self.config, 'vmstat_activity', '')
        proc_plt.plot_vmstat_system_activity(self.dataset.vmstat, out, title=f'System Activity Over Time ({self.config.load_type})', show=show)

    def plot_vmstat_io(self, show=False):
        if not self.dataset.vmstat:
            return
        out = proc_plt.plot_path(self.config, 'vmstat_io', '')
        proc_plt.plot_vmstat_io(self.dataset.vmstat, out, title=f'Disk I/O Activity Over Time ({self.config.load_type})', show=show)

    def plot_mpstat_interrupts(self, show=False):
        if not self.dataset.mpstat:
            return
        out = proc_plt.plot_path(self.config, 'mpstat_interrupts', '')
        proc_plt.plot_mpstat_interrupts(self.dataset.mpstat, out, title=f'Selected System Interrupts ({self.config.load_type})', show=show)

    def plot_pidstat_cpu(self, show=False):
        if not self.dataset.pidstat:
            return
        out = proc_plt.plot_path(self.config, 'pidstat_cpu', '')
        proc_plt.plot_pid_cpu(self.dataset.pidstat, out, title=f'Process CPU Usage Over Time ({self.config.load_type})', show=show)

        out_cs = proc_plt.plot_path(self.config, 'pidstat_cswch', '')
        proc_plt.plot_pid_cswch(self.dataset.pidstat, out_cs, title=f'Process Context Switches ({self.config.load_type})', show=show)

    def plot_network_throughput(self, show=False):
        if not self.dataset.iperf3:
            return
        out = proc_plt.plot_path(self.config, 'iperf3', '')
        proc_plt.plot_network_throughput(self.dataset.iperf3, out, title=f'Network Throughput Over Time ({self.config.load_type})', show=show)

    def plot_fio_hist(self, show=False):
        if not self.dataset.fio:
            return
        
        has_read = hasattr(self.dataset.fio, 'clat_bins_read') and self.dataset.fio.clat_bins_read
        has_write = hasattr(self.dataset.fio, 'clat_bins_write') and self.dataset.fio.clat_bins_write
        
        if not has_read and not has_write:
            return
        out = proc_plt.plot_path(self.config, 'fio_latency', '')
        proc_plt.plot_fio_hist(self.dataset.fio, out, title=f'FIO Latency Distribution ({self.config.load_type})', show=show)
        
    def plot_fio_bandwidth(self, show=False):
        if not self.dataset.fio:
            return
        if len(self.dataset.fio.bandwidth_read_kbps) == 0 and len(self.dataset.fio.bandwidth_write_kbps) == 0:
            return
        out = proc_plt.plot_path(self.config, 'fio_bandwidth', '')
        proc_plt.plot_fio_bandwidth(self.dataset.fio, out, title=f'FIO USB Bandwidth ({self.config.load_type})', show=show)

    def plot_fio_iops(self, show=False):
        if not self.dataset.fio:
            return
        if len(self.dataset.fio.iops_read) == 0 and len(self.dataset.fio.iops_write) == 0:
            return
        out = proc_plt.plot_path(self.config, 'fio_iops', '')
        proc_plt.plot_fio_iops(self.dataset.fio, out, title=f'FIO USB IOPS ({self.config.load_type})', show=show)
        
class ExperimentPlotter:
    @staticmethod
    def plot_duty_cycle_combined(datasets: list, channel: int, show=False, y_lim=None):
        valid_datasets = [ds for ds in datasets if channel in ds.dataset.saleae]
        if len(valid_datasets) > 1:
            title = f"Duty Cycle comparison of channel {channel}"
            labels = [ds.config.load_type for ds in valid_datasets]
            datasets_data = [ds.dataset.saleae[channel] for ds in valid_datasets]
            
            output_file = proc_plt.plot_path(valid_datasets[0].config, "duty_cycle", f"combined_{channel}", combined=True)
            proc_plt.plot_duty_cycle_combined(datasets_data, output_file, title, labels=labels, show=show, y_lim=y_lim)
