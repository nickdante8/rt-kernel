#!/usr/bin/env python3
import os
import sys
import csv
import numpy as np
import matplotlib.pyplot as plt

from models import ExperimentConfig
from experiment import ExperimentProcessor

def get_data(exp_dir, profile):
    """
    Extracts max software latency (cyclictest) and max hardware jitter (Saleae)
    for a given experiment directory and load profile.
    """
    if not os.path.exists(exp_dir):
        return None, None
        
    config = ExperimentConfig(
        input_dir=exp_dir,
        test_type="extraction",
        load_type=profile,
        channels=[0, 1],
        nominal_period_us=200000, # 200ms period
        duration_s=60
    )
    processor = ExperimentProcessor(config)
    
    # Extract hardware data via logic analyzer
    # Temporarily suppress print statements from saleae processing
    sys.stdout = open(os.devnull, 'w')
    
    hw_max, hw_mean, hw_std, hw_p2p = None, None, None, None
    sw_max, sw_avg = None, None
    
    try:
        processor._extract_analysis_saleae()
        if 0 in processor.dataset.saleae:
            sig = processor.dataset.saleae[0]
            hw_max = sig.max_jitter_rise_us
            hw_mean = sig.mean_jitter_rise_us
            hw_std = sig.std_dev_rise_us
            hw_p2p = sig.peak_to_peak_jitter_rise_us

        # Extract software data via cyclictest
        try:
            processor.dataset.cyclictest = processor._extract_analysis_cyclictest()
        except Exception:
            processor.dataset.cyclictest = None

        if processor.dataset.cyclictest and hasattr(processor.dataset.cyclictest, 'threads'):
            for t_id, t_data in processor.dataset.cyclictest.threads.items():
                if hasattr(t_data, 'max') and hasattr(t_data, 'avg'):
                    if sw_max is None or t_data.max > sw_max:
                        sw_max = t_data.max
                        sw_avg = t_data.avg
    finally:
        sys.stdout = sys.__stdout__

    return sw_max, sw_avg, hw_max, hw_mean, hw_std, hw_p2p

def extract_data_for_plot(exp_dir, prof_str):
    """Helper to extract saleae data silently"""
    config = ExperimentConfig(
        input_dir=exp_dir, test_type="extraction", load_type=prof_str,
        channels=[0, 1], nominal_period_us=200000, duration_s=60
    )
    processor = ExperimentProcessor(config)
    devnull = open(os.devnull, 'w')
    old_stdout = sys.stdout
    sys.stdout = devnull
    try:
        processor._extract_analysis_saleae()
        if processor.dataset.saleae:
            sigSW = processor.dataset.saleae.get(0)
            sigHW = processor.dataset.saleae.get(1)
            return sigSW, sigHW
    except Exception:
        pass
    finally:
        sys.stdout = old_stdout
        devnull.close()
    return None, None

def get_run_colors():
    """Maps every known run configuration to a fixed color from the active style cycle"""
    all_runs = [
        "Relative-def", "Absolute-def", "Relative-base", "Absolute-base",
        "Baseline (No Iso)", "Baseline (Iso)", "RT (No Iso)", "RT (Iso)",
        "Upstream (6.18.13)", "Downstream (6.18.29)"
    ]
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    return {run: colors[i % len(colors)] for i, run in enumerate(all_runs)}

def plot_multi_signal_drift_symlog(signal_drift_config, phases_dir_map, output_file):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(14, 7))
    
    run_colors = get_run_colors()
    
    plotted = 0
    stats_lines = []
    
    for phase_name, runs in signal_drift_config.items():
        if phase_name not in phases_dir_map: continue
        for run_name, profiles in runs.items():
            if profiles is None: continue
            if run_name not in phases_dir_map[phase_name]: continue
            
            exp_dir = phases_dir_map[phase_name][run_name]
            for profile in profiles:
                sigSW, sigHW = extract_data_for_plot(exp_dir, profile)
                if sigSW and profile != "idle":
                    ax.plot(sigSW.time_jitter_rise, sigSW.drifts_rise, alpha=0.8, 
                            color=run_colors.get(run_name, 'white'),
                            label=f"[{phase_name[:7]}] {run_name} ({profile})")
                    plotted += 1
                    
                    if sigHW:
                        min_len = min(len(sigSW.drifts_rise), len(sigHW.drifts_rise))
                        diff = sigSW.drifts_rise[:min_len] - sigHW.drifts_rise[:min_len]
                        stats_lines.append(f"[{phase_name[:7]}] {run_name}: Min={np.min(diff):.2f} µs, Max={np.max(diff):.2f} µs, Avg={np.mean(diff):.2f} µs")
                        
                if sigHW and profile == "idle":
                    ax.plot(sigHW.time_jitter_rise, sigHW.drifts_rise, alpha=0.8, linestyle='--',
                            color='red', label=f"[{phase_name[:7]}] {run_name} ({profile} HW Ref)")
                    plotted += 1

    if plotted > 0:
        ax.set_xlabel('Time [s]', fontsize=12)
        ax.set_ylabel('Software Accumulated Error [us]', fontsize=12)
        ax.set_yscale('symlog', linthresh=100)
        plt.title('Combined Signal Drift (SymLog Scale)', fontsize=14)
        # ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1))
        ax.legend(loc='lower right')
        ax.set_ylim(0, 100000)
        
        if stats_lines:
            stats_text = "Deviations from HW Ref:\n" + "\n".join(stats_lines)
            props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
            ax.text(0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=9,
                    verticalalignment='top', bbox=props)
            
        plt.tight_layout()
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        print(f"Combined symlog signal drift plot saved to '{output_file}'")
    else:
        print("No data found for symlog signal drift plot.")
    plt.close(fig)

def plot_multi_signal_drift_by_phase(signal_drift_config, phases_dir_map, base_dir):
    plt.style.use('dark_background')
    
    run_colors = get_run_colors()
    
    phase_idx = 1
    for phase_name, runs in signal_drift_config.items():
        if phase_name not in phases_dir_map: continue
        
        fig, ax1 = plt.subplots(figsize=(14, 7))
        ax2 = ax1.twinx()
        plotted = 0
        stats_lines = []
        
        for run_name, profiles in runs.items():
            if profiles is None: continue
            if run_name not in phases_dir_map[phase_name]: continue
            
            exp_dir = phases_dir_map[phase_name][run_name]
            for profile in profiles:
                sigSW, sigHW = extract_data_for_plot(exp_dir, profile)
                if sigSW and profile != "idle":
                    ax1.plot(sigSW.time_jitter_rise, sigSW.drifts_rise, alpha=0.8, 
                            color=run_colors.get(run_name, 'white'),
                            label=f"{run_name} ({profile})")
                    plotted += 1
                    
                    if sigHW:
                        min_len = min(len(sigSW.drifts_rise), len(sigHW.drifts_rise))
                        diff = sigSW.drifts_rise[:min_len] - sigHW.drifts_rise[:min_len]
                        stats_lines.append(f"{run_name}: Min={np.min(diff):.2f} µs, Max={np.max(diff):.2f} µs, Avg={np.mean(diff):.2f} µs")
                        
                if sigHW and profile == "idle":
                    ax2.plot(sigHW.time_jitter_rise, sigHW.drifts_rise, alpha=0.8, linestyle='--',
                             color='red', label=f"{run_name} ({profile} HW Ref)")
                    plotted += 1

        if plotted > 0:
            ax1.set_xlabel('Time [s]', fontsize=12)
            ax1.set_ylabel('Software Accumulated Error [us]', fontsize=12, color='blue')
            ax2.set_ylabel('Hardware Reference Accumulated Error [us]', fontsize=12, color='red')
            plt.title(f'Signal Drift - {phase_name}', fontsize=14)
            
            lines1, labels1 = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            # ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right', bbox_to_anchor=(1.35, 1))
            ax1.legend(lines1 + lines2, labels1 + labels2, loc='lower right')
            
            if stats_lines:
                stats_text = "Deviations from HW Ref:\n" + "\n".join(stats_lines)
                props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
                ax1.text(0.02, 0.98, stats_text, transform=ax1.transAxes, fontsize=9,
                        verticalalignment='top', bbox=props)
            
            plt.tight_layout()
            output_file = os.path.join(base_dir, f"drift_phase_{phase_idx}.png")
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"Phase {phase_idx} plot saved to '{output_file}'")
        plt.close(fig)
        phase_idx += 1

def plot_dark_histogram_saleae(data, output_file, title):
    plt.style.use('dark_background')
    fig, ax1 = plt.subplots(figsize=(14, 7))
    ax2 = ax1.twinx()

    ax1.hist(data.jitter_rise, bins='auto', density=True, color='r', alpha=0.75, label="Jitter Rise")
    ax2.hist(data.jitter_fall, bins='auto', density=True, color='b', alpha=0.45, label="Jitter Fall")

    ax1.axvline(data.mean_jitter_rise_us, color='r', linestyle='dashed', linewidth=2, label=f"Mean Rise: {data.mean_jitter_rise_us:.2f} µs")
    ax2.axvline(data.mean_jitter_fall_us, color='b', linestyle='dotted', linewidth=2, label=f"Mean Fall: {data.mean_jitter_fall_us:.2f} µs")

    ax1.set_title(title, fontsize=16)
    ax1.set_xlabel(f'Jitter (µs) from Nominal Period ({data.nominal_period_us} µs)', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    stats_text = (
        f"Samples: {data.sample_count}\n"
        f"Std Dev Rise: {data.std_dev_rise_us:.2f} µs\n"
        f"Std Dev Fall: {data.std_dev_fall_us:.2f} µs\n"
        f"Min Jitter Rise: {data.min_jitter_rise_us:.2f} µs\n"
        f"Min Jitter Fall: {data.min_jitter_fall_us:.2f} µs\n"
        f"Max Jitter Rise (WCET): {data.max_jitter_rise_us:.2f} µs\n"
        f"Max Jitter Fall (WCET): {data.max_jitter_fall_us:.2f} µs\n"
        f"Peak-to-Peak Rise: {data.peak_to_peak_jitter_rise_us:.2f} µs\n"
        f"Peak-to-Peak Fall: {data.peak_to_peak_jitter_fall_us:.2f} µs"
    )
    props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
    ax1.text(0.02, 0.97, stats_text, transform=ax1.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)

def plot_dark_histogram_cyclictest(data, output_file, title):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(14, 7))

    colors = ['#2196F3', '#4CAF50', '#FF5722', '#9C27B0']
    sorted_threads = sorted(data.threads.items(), key=lambda x: int(x[0]))

    for idx, (thread_id, thread) in enumerate(sorted_threads):
        color = colors[idx % len(colors)]
        cpu_label = f"CPU{thread.cpu}"
        
        ax.bar(thread.latencies, thread.frequencies, width=1.0, alpha=0.6,
               color=color, label=f"{cpu_label}")
        ax.axvline(thread.avg, color=color, linestyle='--', linewidth=1.5, alpha=0.8,
                   label=f"{cpu_label} Mean: {thread.avg:.2f} µs")

    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Latency (µs)', fontsize=12)
    ax.set_ylabel('Frequency (Number of Occurrences)', fontsize=12)
    ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    
    ax.legend(loc='upper right')

    stats_lines = []
    for thread_id, thread in sorted_threads:
        overflow_text = f"  ⚠ Overflow: {thread.overflow}" if thread.overflow > 0 else ""
        stats_lines.append(
            f"CPU{thread.cpu}: Cycles={thread.cycles}  "
            f"Min={thread.min:.0f}  Max={thread.max:.0f}  "
            f"Avg={thread.avg:.2f}  Std={thread.std_dev:.2f}  "
            f"P2P={thread.peak_to_peak:.0f}{overflow_text}"
        )
    stats_text = "\n".join(stats_lines)
    props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
    ax.text(0.02, 0.97, stats_text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)

def generate_dark_histograms(signal_drift_config, phases_dir_map, base_dir):
    print("\nGenerating individual dark mode histograms for Cyclictest and Saleae...")
    for phase_name, runs in signal_drift_config.items():
        if phase_name not in phases_dir_map: continue
        for run_name, profiles in runs.items():
            if profiles is None: continue
            if run_name not in phases_dir_map[phase_name]: continue
            
            exp_dir = phases_dir_map[phase_name][run_name]
            for profile in profiles:
                # We skip idle profile for histograms if it's strictly HW reference, 
                # but let's generate it anyway to see the pure HW distribution!
                config = ExperimentConfig(
                    input_dir=exp_dir, test_type="extraction", load_type=profile,
                    channels=[0, 1], nominal_period_us=200000, duration_s=60
                )
                processor = ExperimentProcessor(config)
                
                devnull = open(os.devnull, 'w')
                old_stdout = sys.stdout
                sys.stdout = devnull
                try:
                    processor._extract_analysis_saleae()
                    try:
                        processor.dataset.cyclictest = processor._extract_analysis_cyclictest()
                    except Exception:
                        pass
                finally:
                    sys.stdout = old_stdout
                    devnull.close()
                
                safe_name = run_name.replace(" ", "_").replace("(", "").replace(")", "")
                
                if processor.dataset.saleae and 0 in processor.dataset.saleae:
                    sigSW = processor.dataset.saleae[0]
                    out_saleae = os.path.join(base_dir, f"hist_saleae_{safe_name}_{profile}.png")
                    plot_dark_histogram_saleae(sigSW, out_saleae, title=f"Saleae Jitter - {run_name} ({profile})")
                    
                if processor.dataset.cyclictest:
                    out_cyc = os.path.join(base_dir, f"hist_cyclictest_{safe_name}_{profile}.png")
                    plot_dark_histogram_cyclictest(processor.dataset.cyclictest, out_cyc, title=f"Cyclictest Latency - {run_name} ({profile})")

def plot_dark_system_correlation(dataset, output_file, title=None, show=False):
    plt.style.use('dark_background')
    has_saleae = dataset.saleae_common is not None and len(dataset.saleae_common.time_axis) > 0
    has_mpstat = dataset.mpstat is not None
    has_vmstat = dataset.vmstat is not None and len(dataset.vmstat.timestamps) > 0
    
    panes = sum([has_saleae | has_mpstat, has_vmstat])
    if panes < 2:
        return
        
    fig, axes = plt.subplots(panes, 1, figsize=(16, 4 * panes), sharex=True)
    ax_idx = 0
    
    if has_saleae and has_mpstat:
        ax = axes[ax_idx] if panes > 1 else axes
        ax_idx += 1
        jitter = np.array(dataset.saleae_common.latency)
        ax.plot(dataset.saleae_common.time_axis, jitter, color='#e0a8ff', marker='.', linestyle='dashed', alpha=0.7, label='Hardware Jitter (us)')
        
        ax2 = ax.twinx()
        if dataset.mpstat is not None and len(dataset.mpstat.cores) > 0:
            core_all = dataset.mpstat.cores['all']
            for irq_name, values in core_all.individual_interrupts.items():
                if ('ipi' in irq_name.lower() or '180' in irq_name) and (np.mean(values) > 0):
                    avg_val = np.mean(values)
                    ax2.plot(core_all.timestamps, values, marker='.', alpha=0.7, label=f'IRQ {irq_name} (Avg: {avg_val:.1f}/s)')
            ax2.set_ylabel('System/Timer IRQs / sec', fontsize=12)
            
        ax.set_ylabel('HW Jitter (us)', color='#e0a8ff', fontsize=12)
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        ax.set_title("Hardware Jitter vs System IRQs", fontsize=14)
        
    if has_vmstat:
        ax = axes[ax_idx] if panes > 1 else axes
        ax.plot(dataset.vmstat.timestamps, dataset.vmstat.context_switches, color='cyan', alpha=0.7, label=f"Context Switches (Avg: {np.mean(dataset.vmstat.context_switches):.0f} cs/s)")
        ax.set_ylabel('CS / sec', color='cyan', fontsize=12)
        ax.set_ylim(bottom=0)
        
        ax2 = ax.twinx()
        ax2.plot(dataset.vmstat.timestamps, dataset.vmstat.usr + dataset.vmstat.sys, color='red', alpha=0.7, label=f"Total CPU Usage (Avg: {np.mean(dataset.vmstat.usr + dataset.vmstat.sys):.1f} %)")
        ax2.set_ylabel('CPU Usage (%)', color='red', fontsize=12)
        ax2.set_ylim(bottom=0, top=105)
        
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.set_title("System Context Switches and CPU Usage", fontsize=14)
        
    bottom_ax = axes[-1] if panes > 1 else axes
    bottom_ax.set_xlabel('Time (s)', fontsize=14)
    
    if has_saleae and has_vmstat:
        jitter = np.array(dataset.saleae_common.latency)
        stats_text = (
            f"Hardware Jitter: Avg {np.mean(jitter):.2f} us, Max/Min {np.max(jitter):.2f}/{np.min(jitter):.2f} us\n"
        )
        props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
        top_ax = axes[0] if panes > 1 else axes
        top_ax.text(0.38, 0.09, stats_text, transform=top_ax.transAxes, fontsize=11,
                     verticalalignment='bottom', horizontalalignment='right', bbox=props)
                     
    plt.suptitle(title if title else "System Overhead Correlation", fontsize=16)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    if show: plt.show()
    plt.close(fig)

def plot_dark_network_correlation(dataset, output_file, title=None, show=False):
    plt.style.use('dark_background')
    has_saleae = dataset.saleae_common is not None and len(dataset.saleae_common.time_axis) > 0
    has_iperf3 = dataset.iperf3 is not None and len(dataset.iperf3.timestamps) > 0
    has_mpstat = dataset.mpstat is not None
    
    panes = sum([has_saleae | has_mpstat, has_iperf3])
    if panes < 2:
        return
        
    fig, axes = plt.subplots(panes, 1, figsize=(16, 4 * panes), sharex=True)
    ax_idx = 0
    
    if has_saleae and has_mpstat:
        ax = axes[ax_idx] if panes > 1 else axes
        ax_idx += 1
        jitter = np.array(dataset.saleae_common.latency)
        ax.plot(dataset.saleae_common.time_axis, jitter, color='#e0a8ff', marker='.', linestyle='dashed', alpha=0.7, label='Hardware Jitter (us)')
        
        ax2 = ax.twinx()
        if dataset.mpstat is not None and len(dataset.mpstat.cores) > 0:
            core_all = dataset.mpstat.cores['all']
            for irq_name, values in core_all.individual_interrupts.items():
                if ('74' in irq_name or '51' in irq_name) or 'eth' in irq_name.lower():
                    avg_val = np.mean(values)
                    ax2.plot(core_all.timestamps, values, color='red', marker='.', alpha=0.7, label=f'IRQ {irq_name} (Avg: {avg_val:.1f}/s)')
            ax2.set_ylabel('Network IRQs / sec', color='red', fontsize=12)
            
        ax.set_ylabel('HW Jitter (us)', color='#e0a8ff', fontsize=12)
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        ax.set_title("Hardware Jitter vs Network IRQs", fontsize=14)
        
    if has_iperf3:
        ax = axes[ax_idx] if panes > 1 else axes
        ax.plot(dataset.iperf3.timestamps, dataset.iperf3.rtt, color='lime', marker='.', linestyle='-', alpha=0.7, label='Network RTT')
        ax.set_ylabel('RTT Latency (us)', color='lime', fontsize=12)
        ax.set_ylim(bottom=0)
        
        ax2 = ax.twinx()
        ax2.plot(dataset.iperf3.timestamps, dataset.iperf3.retransmits, color='red', marker='x', linestyle='None', alpha=0.7, label='Retransmits')
        ax2.set_ylabel('Retransmits', color='red', fontsize=12)
        ax2.set_ylim(bottom=0)
        
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        ax.set_title("Network TCP Performance", fontsize=14)
        
    bottom_ax = axes[-1] if panes > 1 else axes
    bottom_ax.set_xlabel('Time (s)', fontsize=14)
    
    if has_saleae and has_iperf3:
        jitter = np.array(dataset.saleae_common.latency)
        stats_text = (
            f"Hardware Jitter: Avg {np.mean(jitter):.2f} us, Max/Min {np.max(jitter):.2f}/{np.min(jitter):.2f} us\n"
            f"Network (Iperf3): Avg RTT {np.mean(dataset.iperf3.rtt):.2f} us, Total Retransmits {np.sum(dataset.iperf3.retransmits)}"
        )
        props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
        top_ax = axes[0] if panes > 1 else axes
        top_ax.text(0.38, 0.09, stats_text, transform=top_ax.transAxes, fontsize=11,
                     verticalalignment='bottom', horizontalalignment='right', bbox=props)
                     
    plt.suptitle(title if title else "Network Determinism Correlation", fontsize=16)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    if show: plt.show()
    plt.close(fig)

def generate_dark_correlations(signal_drift_config, phases_dir_map, base_dir):
    print("\nGenerating individual dark mode correlation plots (System and Network)...")
    for phase_name, runs in signal_drift_config.items():
        if phase_name not in phases_dir_map: continue
        for run_name, profiles in runs.items():
            if profiles is None: continue
            if run_name not in phases_dir_map[phase_name]: continue
            
            exp_dir = phases_dir_map[phase_name][run_name]
            for profile in profiles:
                config = ExperimentConfig(
                    input_dir=exp_dir, test_type="extraction", load_type=profile,
                    channels=[0, 1], nominal_period_us=200000, duration_s=60
                )
                processor = ExperimentProcessor(config)
                
                devnull = open(os.devnull, 'w')
                old_stdout = sys.stdout
                sys.stdout = devnull
                try:
                    processor.load_and_process_datas()
                except Exception:
                    pass
                finally:
                    sys.stdout = old_stdout
                    devnull.close()
                
                safe_name = run_name.replace(" ", "_").replace("(", "").replace(")", "")
                
                out_sys = os.path.join(base_dir, f"corr_system_{safe_name}_{profile}.png")
                plot_dark_system_correlation(processor.dataset, out_sys, title=f"System Correlation - {run_name} ({profile})")
                
                if processor.dataset.iperf3 and len(processor.dataset.iperf3.timestamps) > 0:
                    out_net = os.path.join(base_dir, f"corr_network_{safe_name}_{profile}.png")
                    plot_dark_network_correlation(processor.dataset, out_net, title=f"Network Correlation - {run_name} ({profile})")

def main():
    base_dir = "/mnt/nvme0n1p4/Work/Projects/rt-kernel/local-rtk/test_results"
    output_csv = os.path.join(base_dir, "extracted_results.csv")

    # Define the directories for each phase
    phases = {
        "Phase 1: Relative vs Absolute (Baseline Kernel)": {
            "Relative-def": os.path.join(base_dir, "old/default_relative-toggle-time_2026-06-06-00-52-16"),
            "Absolute-def": os.path.join(base_dir, "old/default_absolute-toggle-time_2026-06-09-11-06-38"),
            "Relative-base": os.path.join(base_dir, "baseline_6.18.29-relative-toggle-time_2026-06-12-22-59-55"),
            "Absolute-base": os.path.join(base_dir, "baseline_6.18.29-absolute-toggle-time_2026-06-12-23-14-22")
        },
        "Phase 2: Baseline vs RT (No Isolation vs Isolation)": {
            "Baseline (No Iso)": os.path.join(base_dir, "baseline_6.18.29-absolute-toggle-time_2026-06-12-23-14-22"),
            "Baseline (Iso)": os.path.join(base_dir, "old/baseline_6.18.29-isolation_2026-06-05-23-44-24"),
            "RT (No Iso)": os.path.join(base_dir, "rt_6.18.29-no-isolation_74_disable_2026-06-13-00-15-32"),
            "RT (Iso)": os.path.join(base_dir, "rt_6.18.29-isolation_74_disable_2026-06-13-00-27-53")
        },
        "Phase 3: Upstream vs Downstream Drivers (RT + Iso)": {
            "Upstream (6.18.13)": os.path.join(base_dir, "rt_6.18.13-isolation_2026-06-13-17-11-23"),
            "Downstream (6.18.29)": os.path.join(base_dir, "rt_6.18.29-isolation_74_disable_2026-06-13-00-27-53")
        }
    }

    profiles = ['idle', 'load-cpu', 'load-usb', 'load-net', 'load-net-usb', 'load-full']

    print(f"Extracting testing data to {output_csv}...")
    
    with open(output_csv, mode='w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        # Write CSV Header
        writer.writerow([
            "Phase", "Configuration", "Load Profile", 
            "OS Max Latency (us)", "OS Avg Latency (us)", 
            "HW Max Jitter (us)", "HW Mean Jitter (us)", 
            "HW StdDev Jitter (us)", "HW Peak-to-Peak (us)"
        ])
        
        for phase_name, runs in phases.items():
            print(f"Processing {phase_name}...")
            for run_name, exp_dir in runs.items():
                for profile in profiles:
                    sw_max, sw_avg, hw_max, hw_mean, hw_std, hw_p2p = get_data(exp_dir, profile)
                    
                    # Format strings
                    def fmt(val):
                        return f"{val:.1f}" if val is not None else "N/A"
                    
                    writer.writerow([
                        phase_name, run_name, profile, 
                        fmt(sw_max), fmt(sw_avg), 
                        fmt(hw_max), fmt(hw_mean), 
                        fmt(hw_std), fmt(hw_p2p)
                    ])
                    
    print(f"Data extraction complete. Results saved to {output_csv}.")

    # Configure which profiles to plot in the combined drift graph
    signal_drift = {
        "Phase 1: Relative vs Absolute (Baseline Kernel)": {
            "Relative-def": ["load-full"],
            "Absolute-def": ["idle", "load-full"],
            "Relative-base": ["load-full"],
            "Absolute-base": ["load-full"],
        },
        "Phase 2: Baseline vs RT (No Isolation vs Isolation)": {
            "Baseline (No Iso)": None,
            "Baseline (Iso)": ["load-full"],
            "RT (No Iso)": ["load-full"],
            "RT (Iso)": ["load-full"]
        },
        "Phase 3: Upstream vs Downstream Drivers (RT + Iso)": {
            "Upstream (6.18.13)": ["load-full"],
            "Downstream (6.18.29)": None
        }
    }
    
    plot_symlog_file = os.path.join(base_dir, "combined_signal_drift_symlog.png")
    print("\nGenerating symlog combined plot...")
    plot_multi_signal_drift_symlog(signal_drift, phases, plot_symlog_file)
    
    print("\nGenerating individual per-phase plots...")
    # plot_multi_signal_drift_by_phase(signal_drift, phases, base_dir)
    
    # # Generate the new independent histogram plots!
    # generate_dark_histograms(signal_drift, phases, base_dir)
    
    # Generate the new independent correlation plots!
    generate_dark_correlations(signal_drift, phases, base_dir)

if __name__ == "__main__":
    main()
