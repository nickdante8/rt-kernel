#!/usr/bin/env python3
import os
import sys
import csv

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

if __name__ == "__main__":
    main()
