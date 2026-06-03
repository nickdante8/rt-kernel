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


def plot_duty_cycle_combined(data1, data2, output_file, title=None, label=None, show=False, y_lim=None):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the plot
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label = [
            f"Duty cycle idle",
            f"Duty cycle load"
        ]
    ax.plot(data1.time_pulse, data1.duty_cycles, marker='.', linestyle='dashed', color='r', alpha=0.75, label=f"{label[0]}")
    ax.plot(data2.time_pulse, data2.duty_cycles, marker='.', linestyle='dotted', color='b', alpha=0.45, label=f"{label[1]}")

    # Add a vertical line for the mean
    ax.axhline(50, color='black', linestyle='dashed', linewidth=1, alpha=0.3, label=f"Target (50%)")

    # --- Formatting the Plot ---
    if title == None:
        title = f'Duty cycle comparison.'
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
    else:
        plt.close(fig) # Close the figure to free up

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
    data.plot(kind='bar', stacked=True, ax=ax, edgecolor='black', width=0.5, alpha=0.85)

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
    ax.legend(title="Interrupt Vector", bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)

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
    ax.text(0.02, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

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

    ax.stackplot(data['timestamps'], data['usr'], data['sys'], data['wa'], data['idle'],
                 labels=['User', 'System', 'IO Wait', 'Idle'],
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

    ax1.plot(data['timestamps'], data['context_switches'], color='blue', alpha=0.8, label='Context Switches')
    ax2.plot(data['timestamps'], data['interrupts'], color='red', alpha=0.8, label='System Interrupts')

    ax1.set_title(title if title else "System Activity (vmstat)", fontsize=16)
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
        ax.plot(data.timestamps[:min_len], cpu_array[:min_len], marker='.', label=f'{cmd} CPU%')

    ax.set_title(title if title else "Process CPU Usage", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('CPU Usage %', fontsize=12)
    
    if len(data.timestamps) > 0:
        xticks_idx = np.linspace(0, len(data.timestamps) - 1, min(10, len(data.timestamps)), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data.timestamps[i].split()[-1] for i in xticks_idx], rotation=45)

    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))
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
        ax.plot(data.timestamps[:min_len], cswch_array[:min_len], marker='.', color=colors[idx], label=f'{cmd} (Voluntary)')
        
        nvcswch_array = data.pid_nvcswch.get(cmd, [])
        if len(nvcswch_array) > 0:
            min_len_nv = min(len(data.timestamps), len(nvcswch_array))
            ax.plot(data.timestamps[:min_len_nv], nvcswch_array[:min_len_nv], marker='x', linestyle='--', color=colors[idx], label=f'{cmd} (Non-Voluntary)')

    ax.set_title(title if title else "Process Context Switches", fontsize=16)
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Context Switches / sec', fontsize=12)
    
    if len(data.timestamps) > 0:
        xticks_idx = np.linspace(0, len(data.timestamps) - 1, min(10, len(data.timestamps)), dtype=int)
        ax.set_xticks(xticks_idx)
        ax.set_xticklabels([data.timestamps[i].split()[-1] for i in xticks_idx], rotation=45)

    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1))
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
    
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"iperf3 plot saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)

def plot_fio_hist(data, output_file, title=None, show=False):
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Latencies in fio logs are in nanoseconds. Convert to microseconds.
    clat_us = np.array(data.clat_ns) / 1000.0

    ax.hist(clat_us, bins='auto', density=True, color='purple', alpha=0.75, label='FIO Completion Latency')
    
    if len(data.slat_ns) > 0:
        slat_us = np.array(data.slat_ns) / 1000.0
        ax.hist(slat_us, bins='auto', density=True, color='cyan', alpha=0.5, label='FIO Submission Latency')

    if len(clat_us) > 0:
        mean_us = np.mean(clat_us)
        ax.axvline(mean_us, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_us:.2f} µs')

    ax.set_title(title if title else "FIO Latency Distribution", fontsize=16)
    ax.set_xlabel('Latency (µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend(loc='upper right')

    if len(clat_us) > 0:
        stats_text = (
            f"Samples: {len(clat_us)}\n"
            f"Min Latency: {np.min(clat_us):.2f} µs\n"
            f"Max Latency: {np.max(clat_us):.2f} µs\n"
            f"99th Percentile: {np.percentile(clat_us, 99):.2f} µs"
        )
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10, verticalalignment='top', bbox=props)

    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"FIO histogram saved to '{output_file}'")
    if show:
        plt.show()
    plt.close(fig)
