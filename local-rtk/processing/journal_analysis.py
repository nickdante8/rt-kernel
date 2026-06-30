#!/usr/bin/env python3
import os
import sys
import argparse
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path

from models import ExperimentConfig
from experiment import ExperimentProcessor

def compute_cyclictest_percentile(cyclictest_metrics, percentile):
    hist_combined = {}
    for t_id, t_metrics in cyclictest_metrics.threads.items():
        for lat, count in zip(t_metrics.latencies, t_metrics.frequencies):
            hist_combined[lat] = hist_combined.get(lat, 0) + count
            
    sorted_lats = sorted(hist_combined.keys())
    total_samples = sum(hist_combined.values())
    if total_samples == 0:
        return 0.0
        
    target_idx = total_samples * (percentile / 100.0)
    current_count = 0
    for lat in sorted_lats:
        current_count += hist_combined[lat]
        if current_count >= target_idx:
            return lat
    return sorted_lats[-1]

def extract_run_metrics(processor, run_name, load_type):
    sw_max_jitter = np.nan
    sw_p2p_jitter = np.nan
    hw_max_jitter = np.nan
    hw_p2p_jitter = np.nan
    
    if processor.dataset.saleae:
        if 0 in processor.dataset.saleae:
            sw_max_jitter = processor.dataset.saleae[0].max_jitter_rise_us
            sw_p2p_jitter = processor.dataset.saleae[0].peak_to_peak_jitter_rise_us
        if 1 in processor.dataset.saleae:
            hw_max_jitter = processor.dataset.saleae[1].max_jitter_rise_us
            hw_p2p_jitter = processor.dataset.saleae[1].peak_to_peak_jitter_rise_us

    cyc_max = np.nan
    cyc_avg = np.nan
    cyc_p99 = np.nan
    if processor.dataset.cyclictest:
        all_maxes = [t.max for t in processor.dataset.cyclictest.threads.values()]
        all_avgs = [t.avg for t in processor.dataset.cyclictest.threads.values()]
        if all_maxes:
            cyc_max = max(all_maxes)
            cyc_avg = np.mean(all_avgs)
            cyc_p99 = compute_cyclictest_percentile(processor.dataset.cyclictest, 99.0)

    vmstat_cs_avg = np.nan
    vmstat_cpu_avg = np.nan
    if processor.dataset.vmstat and len(processor.dataset.vmstat.timestamps) > 0:
        vmstat_cs_avg = np.mean(processor.dataset.vmstat.context_switches)
        vmstat_cpu_avg = np.mean(processor.dataset.vmstat.usr + processor.dataset.vmstat.sys)

    return {
        'Run': run_name,
        'Load_Type': load_type,
        'SW_Jitter_Max_us': sw_max_jitter,
        'SW_Jitter_P2P_us': sw_p2p_jitter,
        'HW_Jitter_Max_us': hw_max_jitter,
        'HW_Jitter_P2P_us': hw_p2p_jitter,
        'Cyclictest_Max_us': cyc_max,
        'Cyclictest_Avg_us': cyc_avg,
        'Cyclictest_P99_us': cyc_p99,
        'Context_Switches_Avg': vmstat_cs_avg,
        'CPU_Usage_Avg': vmstat_cpu_avg
    }

def main():
    parser = argparse.ArgumentParser(description="Journal analysis across N repeated runs.")
    parser.add_argument('--input-dir', type=str, required=True, help='Directory containing the run_NNN folders.')
    parser.add_argument('--load-types', type=str, required=True, help='Comma-separated load types to process (e.g. idle,load-full)')
    parser.add_argument('--nominal-period-us', type=int, default=200000, help='Nominal period in microseconds (default 200000).')
    parser.add_argument('--duration-s', type=int, default=60, help='Run duration in seconds (default 60).')
    parser.add_argument('--output-dir', type=str, default='../test_results/journal_analysis', help='Output directory for plots and CSV.')
    
    args = parser.parse_args()
    
    input_dir = Path(args.input_dir)
    load_types = [lt.strip() for lt in args.load_types.split(',')]
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    all_metrics = []
    
    run_dirs = sorted([d for d in input_dir.iterdir() if d.is_dir() and d.name.startswith('run_')])
    if not run_dirs:
        print(f"No directories matching 'run_*' found in {input_dir}")
        sys.exit(1)
        
    print(f"Found {len(run_dirs)} runs to process.")
    
    for run_dir in run_dirs:
        run_name = run_dir.name
        for lt in load_types:
            lt_dir = run_dir / lt
            if not lt_dir.exists():
                print(f"  Skipping {run_name} / {lt} (not found)")
                continue
            
            print(f"Processing {run_name} / {lt}...")
            config = ExperimentConfig(
                input_dir=str(run_dir),
                test_type="journal",
                load_type=lt,
                channels=[0, 1],
                nominal_period_us=args.nominal_period_us,
                duration_s=args.duration_s
            )
            
            processor = ExperimentProcessor(config)
            devnull = open(os.devnull, 'w')
            old_stdout = sys.stdout
            sys.stdout = devnull
            try:
                processor.load_and_process_datas()
            except Exception as e:
                pass
            finally:
                sys.stdout = old_stdout
                devnull.close()
                
            metrics = extract_run_metrics(processor, run_name, lt)
            all_metrics.append(metrics)
            
    if not all_metrics:
        print("No valid metrics extracted.")
        sys.exit(1)
        
    df = pd.DataFrame(all_metrics)
    raw_csv = output_dir / "journal_raw_metrics.csv"
    df.to_csv(raw_csv, index=False)
    print(f"\nSaved raw metrics to {raw_csv}")
    
    stats_df = []
    metrics_cols = ['SW_Jitter_Max_us', 'SW_Jitter_P2P_us', 'HW_Jitter_Max_us', 'HW_Jitter_P2P_us', 'Cyclictest_Max_us', 'Cyclictest_P99_us']
    
    for lt in load_types:
        lt_df = df[df['Load_Type'] == lt]
        if lt_df.empty: continue
        
        for col in metrics_cols:
            series = lt_df[col].dropna()
            if series.empty: continue
            
            n = len(series)
            mean = series.mean()
            std = series.std()
            median = series.median()
            minimum = series.min()
            maximum = series.max()
            p99 = series.quantile(0.99)
            ci95 = 1.96 * (std / np.sqrt(n)) if n > 1 else 0
            cv = (std / mean) * 100 if mean > 0 else 0
            
            stats_df.append({
                'Load_Type': lt,
                'Metric': col,
                'N': n,
                'Mean': mean,
                'Std_Dev': std,
                'CI_95': ci95,
                'Median': median,
                'Min': minimum,
                'Max': maximum,
                'P99': p99,
                'CV_%': cv
            })
            
    stats_df = pd.DataFrame(stats_df)
    stats_csv = output_dir / "journal_agg_stats.csv"
    stats_df.to_csv(stats_csv, index=False)
    print(f"Saved aggregated stats to {stats_csv}\n")
    print(stats_df.to_string(index=False))
    
    plt.style.use('dark_background')
    
    n_runs = len(df['Run'].unique())
    
    plot_jitter_box(df, load_types, n_runs, stats_df, output_dir)
    plot_jitter_violin(df, load_types, n_runs, stats_df, output_dir)
    plot_jitter_bar(stats_df, n_runs, output_dir)
    plot_jitter_cdf(df, load_types, n_runs, stats_df, output_dir)
    
    print("\nAll journal artifacts generated successfully!")

def plot_jitter_box(df, load_types, n_runs, stats_df, output_dir):
    fig, axes = plt.subplots(1, len(load_types), figsize=(7 * len(load_types), 7), sharey=True)
    if len(load_types) == 1: axes = [axes]
    
    metrics = ['SW_Jitter_Max_us', 'HW_Jitter_Max_us', 'Cyclictest_Max_us']
    labels = ['SW Jitter', 'HW Jitter', 'Cyclictest']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for i, lt in enumerate(load_types):
        ax = axes[i]
        lt_df = df[df['Load_Type'] == lt]
        data_to_plot = [lt_df[m].dropna().values for m in metrics]
        
        # Only plot if we actually have data
        valid_data = [d for d in data_to_plot if len(d) > 0]
        valid_labels = [l for d, l in zip(data_to_plot, labels) if len(d) > 0]
        valid_colors = [c for d, c in zip(data_to_plot, colors) if len(d) > 0]
        
        if valid_data:
            # We use set_xticklabels below to ensure compatibility across matplotlib versions
            bplot = ax.boxplot(valid_data, patch_artist=True)
            for patch, color in zip(bplot['boxes'], valid_colors):
                patch.set_facecolor(color)
                patch.set_alpha(0.7)
            ax.set_xticks(np.arange(1, len(valid_labels) + 1))
            ax.set_xticklabels(valid_labels)
            
        ax.set_title(f"Load: {lt}")
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # Add statistics text box
        lt_stats = stats_df[stats_df['Load_Type'] == lt]
        if not lt_stats.empty:
            stats_text = "Statistics:\n"
            for m_key, m_label in zip(metrics, labels):
                row = lt_stats[lt_stats['Metric'] == m_key]
                if not row.empty:
                    stats_text += f"{m_label} - Mean: {row['Mean'].values[0]:.1f}µs, Max: {row['Max'].values[0]:.0f}µs, CV: {row['CV_%'].values[0]:.1f}%\n"
            
            props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
            ax.text(0.5, 0.05, stats_text.strip(), transform=ax.transAxes, fontsize=9,
                    verticalalignment='bottom', horizontalalignment='center', bbox=props)
        
    axes[0].set_ylabel("Max Latency (µs)")
    plt.suptitle(f"Worst-Case Jitter Distribution across {n_runs} runs", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "journal_boxplot.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_jitter_violin(df, load_types, n_runs, stats_df, output_dir):
    fig, axes = plt.subplots(1, len(load_types), figsize=(7 * len(load_types), 7), sharey=True)
    if len(load_types) == 1: axes = [axes]
    
    metrics = ['SW_Jitter_Max_us', 'HW_Jitter_Max_us', 'Cyclictest_Max_us']
    labels = ['SW Jitter', 'HW Jitter', 'Cyclictest']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for i, lt in enumerate(load_types):
        ax = axes[i]
        lt_df = df[df['Load_Type'] == lt]
        data_to_plot = [lt_df[m].dropna().values for m in metrics]
        
        valid_data = [d for d in data_to_plot if len(d) > 0]
        valid_labels = [l for d, l in zip(data_to_plot, labels) if len(d) > 0]
        valid_colors = [c for d, c in zip(data_to_plot, colors) if len(d) > 0]
        
        if valid_data:
            vplot = ax.violinplot(valid_data, showmeans=True, showmedians=True)
            for pc, color in zip(vplot['bodies'], valid_colors):
                pc.set_facecolor(color)
                pc.set_edgecolor('white')
                pc.set_alpha(0.7)
                
            ax.set_xticks(np.arange(1, len(valid_labels) + 1))
            ax.set_xticklabels(valid_labels)
        
        ax.set_title(f"Load: {lt}")
        ax.grid(True, linestyle='--', alpha=0.3)
        
        # Add statistics text box
        lt_stats = stats_df[stats_df['Load_Type'] == lt]
        if not lt_stats.empty:
            stats_text = "Statistics:\n"
            for m_key, m_label in zip(metrics, labels):
                row = lt_stats[lt_stats['Metric'] == m_key]
                if not row.empty:
                    stats_text += f"{m_label} - Mean: {row['Mean'].values[0]:.1f}µs, Max: {row['Max'].values[0]:.0f}µs, CV: {row['CV_%'].values[0]:.1f}%\n"
            
            props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
            ax.text(0.5, 0.05, stats_text.strip(), transform=ax.transAxes, fontsize=9,
                    verticalalignment='bottom', horizontalalignment='center', bbox=props)
        
    axes[0].set_ylabel("Max Latency (µs)")
    plt.suptitle(f"Worst-Case Jitter Density across {n_runs} runs", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "journal_violinplot.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_jitter_bar(stats_df, n_runs, output_dir):
    bar_df = stats_df[stats_df['Metric'].isin(['SW_Jitter_Max_us', 'HW_Jitter_Max_us', 'Cyclictest_Max_us'])]
    if bar_df.empty: return
    
    fig, ax = plt.subplots(figsize=(10, 6))
    load_types = bar_df['Load_Type'].unique()
    metrics = ['SW_Jitter_Max_us', 'HW_Jitter_Max_us', 'Cyclictest_Max_us']
    labels = ['SW Jitter Max', 'HW Jitter Max', 'Cyclictest Max']
    
    x = np.arange(len(load_types))
    width = 0.25
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    for i, metric in enumerate(metrics):
        means = []
        cis = []
        for lt in load_types:
            row = bar_df[(bar_df['Load_Type'] == lt) & (bar_df['Metric'] == metric)]
            if not row.empty:
                means.append(row['Mean'].values[0])
                cis.append(row['CI_95'].values[0])
            else:
                means.append(0)
                cis.append(0)
                
        bars = ax.bar(x + i*width - width, means, width, yerr=cis, label=labels[i], color=colors[i], capsize=5, alpha=0.8)
        
        # Add value text on top of bars
        for bar in bars:
            yval = bar.get_height()
            if yval > 0:
                ax.text(bar.get_x() + bar.get_width()/2, yval + 2, f'{yval:.1f}µs', ha='center', va='bottom', fontsize=9)

    ax.set_xticks(x)
    ax.set_xticklabels(load_types)
    ax.set_ylabel('Mean WCET (µs) ± 95% CI')
    ax.set_title(f'Mean Worst-Case Execution Time across {n_runs} runs\nwith 95% Confidence Intervals', pad=20)
    
    # Place legend outside
    ax.legend(loc='upper left')
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_dir / "journal_barchart_ci.png", dpi=300, bbox_inches='tight')
    plt.close()

def plot_jitter_cdf(df, load_types, n_runs, stats_df, output_dir):
    fig, axes = plt.subplots(1, len(load_types), figsize=(7 * len(load_types), 7), sharey=True)
    if len(load_types) == 1: axes = [axes]
    
    metrics = ['SW_Jitter_Max_us', 'HW_Jitter_Max_us', 'Cyclictest_Max_us']
    labels = ['SW Jitter Max', 'HW Jitter Max', 'Cyclictest Max']
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c']
    
    for i, lt in enumerate(load_types):
        ax = axes[i]
        lt_df = df[df['Load_Type'] == lt]
        
        for metric, label, color in zip(metrics, labels, colors):
            series = lt_df[metric].dropna()
            if len(series) > 0:
                # Sort the data
                x = np.sort(series)
                # Calculate the proportional values of samples
                y = np.arange(1, len(x) + 1) / len(x)
                ax.plot(x, y, marker='.', linestyle='none', color=color, label=label, alpha=0.7)
                # Plot step line
                ax.step(x, y, where='post', color=color, alpha=0.5)
                
        ax.set_title(f"Load: {lt}")
        ax.set_xlabel("Worst-Case Latency (µs)")
        ax.grid(True, linestyle='--', alpha=0.3)
        if i == 0:
            ax.set_ylabel("CDF (Probability)")
            ax.legend(loc='lower right')
            
        # Add statistics text box for P99
        lt_stats = stats_df[stats_df['Load_Type'] == lt]
        if not lt_stats.empty:
            stats_text = "Tail Latencies (P99):\n"
            for m_key, m_label in zip(metrics, labels):
                row = lt_stats[lt_stats['Metric'] == m_key]
                if not row.empty:
                    stats_text += f"{m_label}: {row['P99'].values[0]:.1f}µs\n"
            
            props = dict(boxstyle='round', facecolor='#222222', alpha=0.8, edgecolor='white')
            # Position at top left for CDF since curve goes bottom-left to top-right
            ax.text(0.05, 0.95, stats_text.strip(), transform=ax.transAxes, fontsize=9,
                    verticalalignment='top', horizontalalignment='left', bbox=props)
            
    plt.suptitle(f"Empirical Cumulative Distribution of Max Jitter ({n_runs} runs)", y=1.02)
    plt.tight_layout()
    plt.savefig(output_dir / "journal_cdf.png", dpi=300, bbox_inches='tight')
    plt.close()

if __name__ == "__main__":
    main()
