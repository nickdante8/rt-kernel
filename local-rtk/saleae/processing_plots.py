import matplotlib.pyplot as plt

def _plot_histogram_rise(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='Jitter Distribution (Rise)'
    ax.hist(data['jitter_rise'], bins='auto', density=True, alpha=0.75, label=f"{label}")

    # Add a vertical line for the mean
    ax.axvline(data['mean_jitter_rise_us'], color='r', linestyle='--', linewidth=2, label=f"Mean: {data['mean_jitter_rise_us']:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Rise)"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({data['nominal_period_us']} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {data['sample_count']}\n"
        f"Std Dev: {data['std_dev_rise_us']:.2f} µs\n"
        f"Min Jitter: {data['min_jitter_rise_us']:.2f} µs\n"
        f"Max Jitter (WCET): {data['max_jitter_rise_us']:.2f} µs\n"
        f"Peak-to-Peak: {data['peak_to_peak_jitter_rise_us']:.2f} µs"
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
        
def _plot_histogram_fall(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='Jitter Distribution (Fall)'
    ax.hist(data['jitter_fall'], bins='auto', density=True, alpha=0.75, label=f"{label}")

    # Add a vertical line for the mean
    ax.axvline(data['mean_jitter_fall_us'], color='r', linestyle='--', linewidth=2, label=f"Mean: {data['mean_jitter_fall_us']:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Fall)"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Jitter (µs) from Nominal Period ({data['nominal_period_us']} µs)', fontsize=12)
    ax.set_ylabel('Probability Density', fontsize=12)
    ax.grid(True)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Samples: {data['sample_count']}\n"
        f"Std Dev: {data['std_dev_fall_us']:.2f} µs\n"
        f"Min Jitter: {data['min_jitter_fall_us']:.2f} µs\n"
        f"Max Jitter (WCET): {data['max_jitter_fall_us']:.2f} µs\n"
        f"Peak-to-Peak: {data['peak_to_peak_jitter_fall_us']:.2f} µs"
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

def _plot_histogram_combined(data, output_file, title=None, label=None, show=False):
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
    ax1.hist(data['jitter_rise'], bins='auto', density=True, color='r', alpha=0.75, label=f"{label[0]}")
    ax2.hist(data['jitter_fall'], bins='auto', density=True, color='b', alpha=0.45, label=f"{label[1]}")

    # Add a vertical line for the mean
    ax1.axvline(data['mean_jitter_rise_us'], color='r', linestyle='dashed', linewidth=2, label=f"Mean: {data['mean_jitter_fall_us']:.2f} µs")
    ax2.axvline(data['mean_jitter_fall_us'], color='b', linestyle='dotted', linewidth=2, label=f"Mean: {data['mean_jitter_fall_us']:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "Jitter Distribution (Rise & Fall)"
    ax1.set_title(title, fontsize=16)
    ax1.set_xlabel(f'Jitter (µs) from Nominal Period ({data['nominal_period_us']} µs)', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.grid(True)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2)

    # Add a text box with detailed statistics
    stats_rise_fall_text = (
        f"Samples: {data['sample_count']}\n"
        f"Std Dev Rise: {data['std_dev_rise_us']:.2f} µs\n"
        f"Std Dev Fall: {data['std_dev_fall_us']:.2f} µs\n"
        f"Min Jitter Rise: {data['min_jitter_rise_us']:.2f} µs\n"
        f"Min Jitter Fall: {data['min_jitter_fall_us']:.2f} µs\n"
        f"Max Jitter Rise (WCET): {data['max_jitter_rise_us']:.2f} µs\n"
        f"Max Jitter Fall (WCET): {data['max_jitter_fall_us']:.2f} µs\n"
        f"Peak-to-Peak Rise: {data['peak_to_peak_jitter_rise_us']:.2f} µs\n"
        f"Peak-to-Peak Fall: {data['peak_to_peak_jitter_fall_us']:.2f} µs"
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

def _plot_histogram_cyclic_test(data, output_file, title=None, label=None, show=False):
    """
    Generates and saves a histogram of the jitter data.
    """
    plt.style.use('ggplot')
    fig, ax = plt.subplots(figsize=(12, 7))

    # Create the histogram
    # The number of bins can be adjusted. 'auto' is a good starting point.
    if label == None:
        label='For both channels'
    ax.bar(data['latencies'], data['frequencies'], width=1.0, alpha=0.75, label=f"{label}")

    # Add a vertical line for the mean
    ax.axvline(data['avg'], color='r', linestyle='--', linewidth=2, label=f"Mean: {data['avg']:.2f} µs")

    # --- Formatting the Plot ---
    if title == None:
        title = "CyclicTest Latency for Channel 0 and 1"
    ax.set_title(title, fontsize=16)
    ax.set_xlabel(f'Latency (µs)', fontsize=12)
    ax.set_ylabel('Freqcuency (Number of Occurences)', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.5)
    ax.legend()

    # Add a text box with detailed statistics
    stats_text = (
        f"Total Cycles: {data['cycles']}\n"
        f"Std Dev: {data['std_dev']:.2f} µs\n"
        f"Min Latency: {data['min']:.2f} µs\n"
        f"Max Latency (WCET): {data['max']:.2f} µs\n"
        f"Peak-to-Peak: {data['peak_to_peak']:.2f} µs"
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

def _plot_phase_shift_combined(data, output_file, title=None, label=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    if label == None:
        label = [
            f"Latency channels comparison",
            f"Phase channels difference",
        ]
    ax1.plot(data['time_axis'], data['latency'], alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(data['time_axis'], data['phase'], alpha=0.2, color='red', label=f"{label[1]}")

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

def _plot_signal_drift(data, output_file, title=None, label=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()
    
    # for phase in phase_idle.values():
    if label == None:
        label = [
            f"Channel rise",
            f"Channel fall"
        ]
    ax1.plot(data['time_jitter_rise'], data['drifts_rise'], alpha=0.4, color='blue', label=f"{label[0]}")
    ax2.plot(data['time_jitter_fall'], data['drifts_fall'], alpha=0.2, color='red', label=f"{label[1]}")

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

def _plot_signal_drift_combined(data1, data2, output_file, title=None, lable=None, show=False):
    plt.style.use('ggplot')
    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax2 = ax1.twinx()

    # for phase in phase_idle.values():
    if lable == None:
        lable = [
            f"Channel 0",
            f"Channel 1"
        ]
    ax1.plot(data1['time_jitter_rise'], data1['drifts_rise'], alpha=0.4, color='blue', label=f"{lable[0]}")
    ax2.plot(data2['time_jitter_rise'], data2['drifts_rise'], alpha=0.2, color='red', label=f"{lable[1]}")

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


def _plot_duty_cycle_combined(data1, data2, output_file, title=None, label=None, show=False, y_lim=None):
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
    ax.plot(data1['time_pulse'], data1['duty_cycles'], marker='.', linestyle='dashed', color='r', alpha=0.75, label=f"{label[0]}")
    ax.plot(data2['time_pulse'], data2['duty_cycles'], marker='.', linestyle='dotted', color='b', alpha=0.45, label=f"{label[1]}")

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

def _plot_interrupts_stacked_bar(data, output_file, title=None, label=None, show=False):
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
    ax.text(0.05, 0.95, stats_text, transform=ax.transAxes, fontsize=10,
            verticalalignment='top', bbox=props)

    # Save the figure to a file
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Stacked bar plot saved to '{output_file}'")

    if show == True:
        plt.show()
        plt.close(fig) # Close the figure to free up memory
    else:
        plt.close(fig) # Close the figure to free up memory
