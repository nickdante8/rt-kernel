import matplotlib.pyplot as plt
import numpy as np
import os

def plot_path(obj, type, name, combined=False):
    # Check how to combine it
    if combined == False:
        if name == None or name == "":
            combined_path = "jitter_" + type + "_" + obj.test_type + "_" + obj.load_type + ".png"
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

def plot_histogram_rise(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='Jitter Distribution (Rise)'
    ax.hist(data.jitter_rise, bins='auto', density=True, alpha=0.75, label=f"{label}")

    # Add a vertical line for the mean
    ax.axvline(data.mean_jitter_rise_us, color='r', linestyle='--', linewidth=2, label=f"Mean: {data.mean_jitter_rise_us:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Rise)"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({data.nominal_period_us} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {data.sample_count}\n"
        f"Std Dev: {data.std_dev_rise_us:.2f} µs\n"
        f"Min Jitter: {data.min_jitter_rise_us:.2f} µs\n"
        f"Max Jitter (WCET): {data.max_jitter_rise_us:.2f} µs\n"
        f"Peak-to-Peak: {data.peak_to_peak_jitter_rise_us:.2f} µs"
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
    else:
        plt.close(fig) # Close the figure to free up memory
        
def plot_histogram_fall(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='Jitter Distribution (Fall)'
    ax.hist(data.jitter_fall, bins='auto', density=True, alpha=0.75, label=f"{label}")

    # Add a vertical line for the mean
    ax.axvline(data.mean_jitter_fall_us, color='r', linestyle='--', linewidth=2, label=f"Mean: {data.mean_jitter_fall_us:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Fall)"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({data.nominal_period_us} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {data.sample_count}\n"
        f"Std Dev: {data.std_dev_fall_us:.2f} µs\n"
        f"Min Jitter: {data.min_jitter_fall_us:.2f} µs\n"
        f"Max Jitter (WCET): {data.max_jitter_fall_us:.2f} µs\n"
        f"Peak-to-Peak: {data.peak_to_peak_jitter_fall_us:.2f} µs"
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
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_histogram_combined(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax2 = ax1.twinx()

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label=[
            'Jitter Distribution Rise',
            'Jitter Distribution Fall'
        ]
    ax1.hist(data.jitter_rise, bins='auto', density=True, color='r', alpha=0.75, label=f"{label[0]}")
    ax2.hist(data.jitter_fall, bins='auto', density=True, color='b', alpha=0.45, label=f"{label[1]}")

    # Add a vertical line for the mean
    ax1.axvline(data.mean_jitter_rise_us, color='r', linestyle='dashed', linewidth=2, label=f"Mean: {data.mean_jitter_fall_us:.2f} µs")
    ax2.axvline(data.mean_jitter_fall_us, color='b', linestyle='dotted', linewidth=2, label=f"Mean: {data.mean_jitter_fall_us:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Rise & Fall)"
    ax1.set_title(title, fontsize=16)
    ax1.set_xlabel(f'Jitter (µs) from Nominal Period ({data.nominal_period_us} µs)', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.grid(True)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    # Add a text box with detailed statistics
    stats_rise_fall_text = (
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
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax1.text(0.02, 0.97, stats_rise_fall_text, transform=ax1.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_histogram_cyclic_test(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves overlaid per-CPU histograms from multi-thread cyclictest data.
    Each thread (CPU) is rendered as a separate semi-transparent bar series.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(14, 8))

    # Color palette for up to 4 CPUs (housekeeping vs isolated distinction)
    colors = ['#2196F3', '#4CAF50', '#FF5722', '#9C27B0']
    
    # Sort threads by thread id for consistent ordering
    sorted_threads = sorted(data.threads.items(), key=lambda x: int(x[0]))

    for idx, (thread_id, thread) in enumerate(sorted_threads):
        color = colors[idx % len(colors)]
        cpu_label = f"CPU{thread.cpu}"
        
        ax.bar(thread.latencies, thread.frequencies, width=1.0, alpha=0.55,
               color=color, label=f"{cpu_label}")
        ax.axvline(thread.avg, color=color, linestyle='--', linewidth=1.5, alpha=0.8,
                   label=f"{cpu_label} Mean: {thread.avg:.2f} µs")

    # --- Formatting the Plot ---
    if title is None:
        title = "CyclicTest Latency Distribution (per CPU)"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Latency (µs)', fontsize=12)
    ax.set_ylabel('Frequency (Number of Occurrences)', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(loc='upper right', fontsize=9)

    # Build a combined stats text box with per-CPU breakdown
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
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=8,
            verticalalignment='top', fontfamily='monospace', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_phase_shift_combined(data, output_file, title=None, label=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    if label == None:
        label = [
            f"Latency channels comparison",
            f"Phase channels difference",
        ]
    ax1.plot(data.time_axis, data.latency, alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(data.time_axis, data.phase, alpha=0.2, color='red', label=f"{label[1]}")

    # --- Formatting the Plot ---
    if title == None:
        title = "Latency and Phase Alignment Over Time"
    plt.title(title, fontsize=16)
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Latency [us]', color='blue')
    ax2.set_ylabel('Phase Difference [Degrees]', color='red')
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_signal_drift(data, output_file, title=None, label=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    if label == None:
        label = [
            f"Channel rise",
            f"Channel fall"
        ]
    ax1.plot(data.time_jitter_rise, data.drifts_rise, alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(data.time_jitter_fall, data.drifts_fall, alpha=0.2, color='red', label=f"{label[1]}")

    # --- Formatting the Plot ---
    if title == None:
        title = "Cumulative Signal Drift (Relative to nominal period)"
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Accumulated Error [us]', color='blue')
    ax2.set_ylabel('Accumulated Error [us]', color='red')
    plt.title(f"{title}")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_signal_drift_combined(data1, data2, output_file, title=None, lable=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()

    # for phase in phase_idle.values():
    if lable == None:
        lable = [
            f"Channel 0",
            f"Channel 1"
        ]
    ax1.plot(data1.time_jitter_rise, data1.drifts_rise, alpha=0.4, color='blue', label=f"{lable[0]}")
    ax2.plot(data2.time_jitter_rise, data2.drifts_rise, alpha=0.2, color='red', label=f"{lable[1]}")

    # --- Formatting the Plot ---
    if title == None:
        title = f'Combined cumulative Signal Drift'
    ax1.set_xlabel('Time [s]')
    ax1.set_ylabel('Accumulated Error [us]', color='blue')
    ax2.set_ylabel('Accumulated Error [us]', color='red')
    plt.title(f"{title}")
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='best')

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Histogram saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory


def plot_duty_cycle_combined(datasets_data, output_file, title=None, labels=None, show=False, y_lim=None):
    """
    Generates and saves a combined duty cycle plot using separate subplots.
    """
    plt.style.use('ggplot')
    num_plots = len(datasets_data)
    # Create subplots, dynamically sizing height based on number of plots
    fig, axes = plt.subplots(num_plots, 1, figsize=(12, 2 * num_plots), sharex=True)
    
    # If there's only 1 dataset, axes is not a list/array, so wrap it
    if num_plots == 1:
        axes = [axes]

    colors = ['r', 'b', 'g', 'purple', 'black', 'cyan']
    
    if labels is None:
        labels = [f"Dataset {i}" for i in range(num_plots)]

    for i, data in enumerate(datasets_data):
        ax = axes[i]
        color = colors[i % len(colors)]
        
        # Use scatter plotting to avoid messy overlapping lines for duty cycle
        ax.plot(data.time_pulse, data.duty_cycles, marker='.', linestyle='dashed', color=color, alpha=0.45, label=f"{labels[i]}")

        # Add a horizontal line for the mean
        ax.axhline(50, color='black', linestyle='dashed', linewidth=1.5, alpha=0.5, label=f"Target (50%)")

        ax.set_ylabel('Duty Cycle (%)', fontsize=12)
        ax.grid(True)
        ax.legend(loc='best')

        if y_lim:
            ax.set_ylim(y_lim)

    # --- Formatting the overall Figure ---
    if title is None:
        title = f'Duty cycle comparison'
    fig.suptitle(title, fontsize=16)
    
    # Set X label only on the bottom subplot
    axes[-1].set_xlabel('Time [s]', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Duty cycle plot saved to '{output_file}'")

    if show:
        plt.show()
    plt.close(fig)

def plot_interrupts_stacked_bar(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a stacked bar plot of interrupt distributions per CPU core.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='Workload Active IRQs'
    data.plot(kind='bar', stacked=True, ax=ax, edgecolor='black', width=0.5, alpha=0.85, colormap='tab20')

    # --- Calculate Statistics for the Summary Box ---
    total_interrupts = data.values.sum()
    busiest_cpu = data.sum(axis=1).idxmax()
    busiest_cpu_val = data.sum(axis=1).max()
    
    top_irq = data.sum(axis=0).idxmax()
    top_irq_val = data.sum(axis=0).max()

    # --- Add IRQ Name and Number Directly On The Bars ---
    # Loop through each stacked layer (container)
    for container in ax.containers:
        # Retrieve the layer identifier (e.g., "IRQ 51 (dwc_otg_sim-fiq)")
        irq_layer_label = container.get_label()
        
        labels = []
        for val in container.datavalues:
            # Smart threshold: Only paint the text if the segment represents > 3% of the busiest core's height
            # This prevents labels from overlapping and clumping on near-zero bars
            if val >= (busiest_cpu_val * 0.03):
                # Format text to show the shortened IRQ string identity and its delta count
                labels.append(f"irq {irq_layer_label.split(' ')[0]}\n({int(val):,})")
            elif val > (busiest_cpu_val * 0.01):
                # Format text to show the shortened IRQ string identity and its delta count
                labels.append(f"({int(val):,})")
            else:
                labels.append("") # Hide text for tiny segments
                
        # Draw the labels directly in the center of each bar block
        ax.bar_label(container, labels=labels, label_type='center', fontsize=8, color='black')

    # --- Formatting the Plot ---
    if title == None:
        title = "Interrupt Load Distribution per Processor Core"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel('Processor Cores', fontsize=12)
    ax.set_ylabel('Interrupt Count (Delta Volume)', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend(title="Interrupt Vector", bbox_to_anchor=(1.01, 1), loc='upper left', fontsize=9)

    # Force horizontal labels on the X-axis (CPU0, CPU1...) instead of angled text
    plt.xticks(rotation=0) 
    ax.grid(True, linestyle='--', alpha=0.5)

    # Add a text box with detailed statistics
    stats_text = (
        f"Total Delta System IRQs: {int(total_interrupts):,}\n"
        f"Busiest Core: {busiest_cpu} ({int(busiest_cpu_val):,} hits)\n"
        f"Top Contributor: {top_irq}\n"
        f"Top Contributor Volume: {int(top_irq_val):,}\n"
        f"Unique Active IRQ Vectors: {len(data.columns)}"
    )
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(1.01, 0.48, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', horizontalalignment='left', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Stacked bar plot saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory

def plot_vmstat_cpu(data, output_file, title=None, label=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    avg_usr = np.mean(data['usr']) if len(data['usr']) > 0 else 0
    avg_sys = np.mean(data['sys']) if len(data['sys']) > 0 else 0
    avg_wa = np.mean(data['wa']) if len(data['wa']) > 0 else 0
    avg_idle = np.mean(data['idle']) if len(data['idle']) > 0 else 0
    labels = [f'User ({avg_usr:.1f}%)', f'System ({avg_sys:.1f}%)', f'IO Wait ({avg_wa:.1f}%)', f'Idle ({avg_idle:.1f}%)']

    ax.stackplot(data['timestamps'], data['usr'], data['sys'], data['wa'], data['idle'],
                 labels=labels,
                 colors=['#2ca02c', '#1f77b4', '#d62728', '#e377c2'], alpha=0.8)

    ax.set_title(title if title else "CPU Breakdown Over Time", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('CPU Usage %', fontsize=12)
    ax.set_ylim(0, 100)
    
    if len(data['timestamps']) > 0:
        xticks_idx = np.linspace(0, len(data['timestamps']) - 1, min(10, len(data['timestamps'])), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data['timestamps'][i].split()[-1] for i in xticks_idx], rotation=45)
    
    ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"vmstat CPU plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_vmstat_system_activity(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax2 = ax1.twinx()

    ax1.plot(data['timestamps'], data['context_switches'], color='blue', alpha=0.7, label='Total System Context Switches', linewidth=2)
    ax2.plot(data['timestamps'], data['interrupts'], color='red', alpha=0.7, label='Total System Interrupts', linewidth=2)

    ax1.set_title(title if title else "Total System Activity (vmstat)", fontsize=16)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.set_ylabel('Context Switches / sec', color='blue', fontsize=12)
    ax2.set_ylabel('Interrupts / sec', color='red', fontsize=12)
    
    if len(data['timestamps']) > 0:
        xticks_idx = np.linspace(0, len(data['timestamps']) - 1, min(10, len(data['timestamps'])), dtype=int)
        ax1.set_xticks(xticks_idx)
        ax1.set_xticklabels([data['timestamps'][i].split()[-1] for i in xticks_idx], rotation=45)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"vmstat system activity plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_vmstat_io(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    ax.plot(data['timestamps'], data['blocks_in'], color='purple', alpha=0.8, label='Blocks In (Read)')
    ax.plot(data['timestamps'], data['blocks_out'], color='orange', alpha=0.8, label='Blocks Out (Write)')

    ax.set_title(title if title else "Disk I/O Activity (vmstat)", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Blocks / sec', fontsize=12)
    
    if len(data['timestamps']) > 0:
        xticks_idx = np.linspace(0, len(data['timestamps']) - 1, min(10, len(data['timestamps'])), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data['timestamps'][i].split()[-1] for i in xticks_idx], rotation=45)

    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"vmstat IO plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_pid_cpu(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    for cmd, cpu_array in data.pid_cpu.items():
        min_len = min(len(data.timestamps), len(cpu_array))
        if min_len > 0:
            avg_cpu = np.mean(cpu_array[:min_len])
            ax.plot(data.timestamps[:min_len], cpu_array[:min_len], marker='.', label=f'{cmd} (Avg: {avg_cpu:.1f}%)')

    ax.set_title(title if title else "Process CPU Usage", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('CPU Usage %', fontsize=12)
    
    if len(data.timestamps) > 0:
        xticks_idx = np.linspace(0, len(data.timestamps) - 1, min(10, len(data.timestamps)), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data.timestamps[i].split()[-1] for i in xticks_idx], rotation=45)

    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"pidstat CPU plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_pid_cswch(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    colors = plt.cm.tab10(np.linspace(0, 1, len(data.pid_cswch)))
    for idx, (cmd, cswch_array) in enumerate(data.pid_cswch.items()):
        min_len = min(len(data.timestamps), len(cswch_array))
        if min_len > 0:
            avg_cswch = np.mean(cswch_array[:min_len])
            ax.plot(data.timestamps[:min_len], cswch_array[:min_len], marker='.', color=colors[idx], label=f'{cmd} Vol (Avg: {avg_cswch:.1f}/s)')
        
        nvcswch_array = data.pid_nvcswch.get(cmd, [])
        if len(nvcswch_array) > 0:
            min_len_nv = min(len(data.timestamps), len(nvcswch_array))
            if min_len_nv > 0:
                avg_nvcswch = np.mean(nvcswch_array[:min_len_nv])
                ax.plot(data.timestamps[:min_len_nv], nvcswch_array[:min_len_nv], marker='x', linestyle='--', color=colors[idx], label=f'{cmd} Non-Vol (Avg: {avg_nvcswch:.1f}/s)')

    ax.set_title(title if title else "Process Context Switches", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Context Switches / sec', fontsize=12)
    
    if len(data.timestamps) > 0:
        xticks_idx = np.linspace(0, len(data.timestamps) - 1, min(10, len(data.timestamps)), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data.timestamps[i].split()[-1] for i in xticks_idx], rotation=45)

    ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1))
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"pidstat CS plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_network_throughput(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(12, 7))
    ax2 = ax1.twinx()

    bps = np.array(data.bits_per_second) / 1_000_000  # Mbps
    ax1.plot(data.timestamps, bps, color='blue', alpha=0.8, marker='o', label='Throughput (Mbps)')
    ax2.plot(data.timestamps, data.retransmits, color='red', alpha=0.8, marker='x', linestyle='--', label='Retransmits')

    ax1.set_title(title if title else "Network Throughput (iperf3)", fontsize=16)
    ax1.set_xlabel('Time (s)', fontsize=12)
    ax1.set_ylabel('Throughput (Mbps)', color='blue', fontsize=12)
    ax2.set_ylabel('Retransmits', color='red', fontsize=12)
    
    # Scale Y axis to keep retransmits below throughput
    max_bps = np.max(bps) if len(bps) > 0 else 100
    ax1.set_ylim(bottom=0, top=max_bps * 1.5)
    max_retransmits = np.max(data.retransmits) if len(data.retransmits) > 0 else 0
    ax2.set_ylim(bottom=0, top=max(10, max_retransmits * 4))
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    if len(bps) > 0:
        stats_text = (
            f"Avg Throughput: {np.mean(bps):.1f} Mbps\n"
            f"Min Throughput: {np.min(bps):.1f} Mbps\n"
            f"Max Throughput: {np.max(bps):.1f} Mbps\n"
            f"Total Retransmits: {np.sum(data.retransmits)}"
        )
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax1.text(0.98, 0.95, stats_text, transform=ax1.transAxes, fontsize=10, verticalalignment='top', horizontalalignment='right', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"iperf3 plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_fio_hist(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Latencies in fio logs are in nanoseconds. Convert to milliseconds.
    if len(data.slat_ns) > 0:
        slat_ms = np.array(data.slat_ns) / 1000000.0
        ax.hist(slat_ms, bins='auto', density=True, color='#2196F3', alpha=0.5, label='FIO Submission Latency (slat)')
        mean_sus = np.mean(slat_ms)
        ax.axvline(mean_sus, color='#2196F3', linestyle='--', linewidth=2, label=f'Mean slat: {mean_sus:.2f} ms')
        
    if len(data.lat_ns) > 0:
        lat_ms = np.array(data.lat_ns) / 1000000.0
        ax.hist(lat_ms, bins='auto', density=True, color='#4CAF50', alpha=0.4, label='FIO Total Latency (lat)')
        mean_lus = np.mean(lat_ms)
        ax.axvline(mean_lus, color='#4CAF50', linestyle='--', linewidth=2, label=f'Mean lat: {mean_lus:.2f} ms')

    if len(data.clat_ns) > 0:
        clat_ms = np.array(data.clat_ns) / 1000000.0
        ax.hist(clat_ms, bins='auto', density=True, color='#FF5722', alpha=0.75, label='FIO Completion Latency (clat)')
        mean_cus = np.mean(clat_ms)
        ax.axvline(mean_cus, color='#FF5722', linestyle='--', linewidth=2, label=f'Mean clat: {mean_cus:.2f} ms')

    ax.set_title(title if title else "FIO Latency Distribution", fontsize=16)
    ax.set_xlabel('Latency (ms)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend(loc='upper right')

    stats_lines = []
    if len(data.clat_ns) > 0:
        clat_ms = np.array(data.clat_ns) / 1000000.0
        stats_lines.append("--- Completion Latency (clat) ---")
        stats_lines.append(f"Samples: {len(clat_ms)}")
        stats_lines.append(f"Mean: {np.mean(clat_ms):.2f} ms")
        stats_lines.append(f"Max: {np.max(clat_ms):.2f} ms")
        stats_lines.append(f"99th: {np.percentile(clat_ms, 99):.2f} ms")
        
    if len(data.slat_ns) > 0:
        slat_ms = np.array(data.slat_ns) / 1000000.0
        stats_lines.append("\n--- Submission Latency (slat) ---")
        stats_lines.append(f"Mean: {np.mean(slat_ms):.2f} ms")
        stats_lines.append(f"Max: {np.max(slat_ms):.2f} ms")
        stats_lines.append(f"99th: {np.percentile(slat_ms, 99):.2f} ms")
    if len(data.lat_ns) > 0:
        lat_ms = np.array(data.lat_ns) / 1000000.0
        stats_lines.append("\n--- Total Latency (lat) ---")
        stats_lines.append(f"Mean: {np.mean(lat_ms):.2f} ms")
        stats_lines.append(f"Max: {np.max(lat_ms):.2f} ms")
        stats_lines.append(f"99th: {np.percentile(lat_ms, 99):.2f} ms")

    stats_text = "\n".join(stats_lines)
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=9, verticalalignment='top', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"FIO histogram saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_fio_bandwidth(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    has_data = False
    if len(data.bw_timestamps_read) > 0 and len(data.bandwidth_read_kbps) > 0:
        sort_idx = np.argsort(data.bw_timestamps_read)
        ax.plot(np.array(data.bw_timestamps_read)[sort_idx], 
                (np.array(data.bandwidth_read_kbps) / 1024.0)[sort_idx], 
                marker='.', linestyle='none', color='blue', label='Read Bandwidth', alpha=0.7)
        has_data = True
        
    if len(data.bw_timestamps_write) > 0 and len(data.bandwidth_write_kbps) > 0:
        sort_idx = np.argsort(data.bw_timestamps_write)
        ax.plot(np.array(data.bw_timestamps_write)[sort_idx], 
                (np.array(data.bandwidth_write_kbps) / 1024.0)[sort_idx], 
                marker='.', linestyle='none', color='red', label='Write Bandwidth', alpha=0.7)
        has_data = True

    if has_data:
        ax.set_title(title if title else "FIO USB Bandwidth (Read/Write)", fontsize=16)
        ax.set_xlabel('Time (s)', fontsize=12)
        ax.set_ylabel('Bandwidth (MB/s)', fontsize=12)
        ax.grid(True)
        ax.legend(loc='best')
        
        stats_lines = []
        if len(data.bandwidth_read_kbps) > 0:
            read_mbps = np.array(data.bandwidth_read_kbps) / 1024.0
            stats_lines.append(f"Avg Read: {np.mean(read_mbps):.2f} MB/s")
            stats_lines.append(f"Max Read: {np.max(read_mbps):.2f} MB/s")
        if len(data.bandwidth_write_kbps) > 0:
            write_mbps = np.array(data.bandwidth_write_kbps) / 1024.0
            stats_lines.append(f"Avg Write: {np.mean(write_mbps):.2f} MB/s")
            stats_lines.append(f"Max Write: {np.max(write_mbps):.2f} MB/s")
            
        if stats_lines:
            stats_text = "\n".join(stats_lines)
            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=10, verticalalignment='top', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"FIO bandwidth plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_fio_iops(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10), sharex=True)

    has_data = False
    if len(data.iops_timestamps_read) > 0 and len(data.iops_read) > 0:
        sort_idx = np.argsort(data.iops_timestamps_read)
        ax1.plot(np.array(data.iops_timestamps_read)[sort_idx], 
                 np.array(data.iops_read)[sort_idx], 
                 marker='.', linestyle='-', color='blue', label='Read IOPS', alpha=0.7)
        ax1.set_ylabel('Read IOPS', fontsize=12)
        ax1.grid(True)
        ax1.legend(loc='upper right')
        
        stats_text = f"Avg Read: {np.mean(data.iops_read):.1f}\nMax Read: {np.max(data.iops_read):.1f}"
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax1.text(0.02, 0.95, stats_text, transform=ax1.transAxes, fontsize=10, verticalalignment='top', bbox=props)
        has_data = True
        
    if len(data.iops_timestamps_write) > 0 and len(data.iops_write) > 0:
        sort_idx = np.argsort(data.iops_timestamps_write)
        ax2.plot(np.array(data.iops_timestamps_write)[sort_idx], 
                 np.array(data.iops_write)[sort_idx], 
                 marker='.', linestyle='-', color='red', label='Write IOPS', alpha=0.7)
        ax2.set_ylabel('Write IOPS', fontsize=12)
        ax2.grid(True)
        ax2.legend(loc='upper right')
        
        stats_text = f"Avg Write: {np.mean(data.iops_write):.1f}\nMax Write: {np.max(data.iops_write):.1f}"
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax2.text(0.02, 0.95, stats_text, transform=ax2.transAxes, fontsize=10, verticalalignment='top', bbox=props)
        has_data = True

    if has_data:
        fig.suptitle(title if title else "FIO USB IOPS", fontsize=16)
        ax2.set_xlabel('Time (s)', fontsize=12)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"FIO IOPS plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_mpstat_interrupts(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    if 'all' in data.cores:
        core_all = data.cores['all']
        interesting_irqs = ['51', '74', '180', 'IPI0', 'IPI1']
        
        irq_mapping = {
            '51': '51 (dwc_otg_sim-fiq)',
            '74': '74 (dwc_otg_hcd:usb1)',
            '180': '180 (arch_timer)',
            'IPI0': 'IPI0 (Rescheduling interrupts)',
            'IPI1': 'IPI1 (Function call interrupts)',
        }
        
        plotted = 0
        for irq_name, values in core_all.individual_interrupts.items():
            if any(interesting.lower() in irq_name.lower() for interesting in interesting_irqs) or np.mean(values) > 100:
                avg_val = np.mean(values)
                if avg_val > 0:
                    # Get formatted name if available
                    label_name = irq_mapping.get(irq_name.upper(), irq_name)
                    ax.plot(core_all.timestamps, values, marker='.', label=f"{label_name} (Avg: {avg_val:.1f}/s)")
                    plotted += 1

        if plotted > 0:
            ax.set_title(title if title else "Selected System Interrupts (mpstat)", fontsize=16)
            ax.set_xlabel('Time', fontsize=12)
            ax.set_ylabel('Interrupts / sec', fontsize=12)
            
            if len(core_all.timestamps) > 0:
                xticks_idx = np.linspace(0, len(core_all.timestamps) - 1, min(10, len(core_all.timestamps)), dtype=int)
                ax.set_xticks(xticks_idx)
                ax.set_xticklabels([core_all.timestamps[i].split()[-1] for i in xticks_idx], rotation=45)

            ax.legend(loc='best')
            plt.tight_layout()
            plt.savefig(output_file, dpi=300, bbox_inches='tight')
            print(f"mpstat interrupts plot saved to '{output_file}'")
    
    if show:
        plt.show()
    plt.close(fig)
