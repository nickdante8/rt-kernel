"""
Parsers for raw Linux profiling artifacts used by the processing pipeline.
"""
import pandas as pd
import numpy as np
import os
import json
import math

from models import (
    CyclictestMetrics,
    CyclictestThreadMetrics,
    MpstatMetrics,
    CpuTimelineMetrics,
    Iperf3Metrics,
    FioMetrics,
    PidstatMetrics,
    VmstatMetrics,
)

def _parse_cyclictest_thread(thread_id, thread_data):
    """Parse a single cyclictest thread into CyclictestThreadMetrics."""
    hist_data = thread_data['histogram']
    
    # Convert histogram to latency arrays
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

    return CyclictestThreadMetrics(
        cpu=thread_data.get('cpu', int(thread_id)),
        histogram=hist_data,
        latencies=latencies,
        frequencies=frequencies,
        cycles=total_cycles,
        min=thread_data['min'],
        max=thread_data['max'],
        avg=avg_lat,
        std_dev=std_dev,
        peak_to_peak=(thread_data['max'] - thread_data['min']) if len(latencies) > 0 else 0,
        overflow=thread_data.get('overflow', 0),
    )

def cyclictest(data):
    """Parse cyclictest JSON output into CyclictestMetrics with per-thread data."""
    threads = {}
    for thread_id, thread_data in data['thread'].items():
        threads[thread_id] = _parse_cyclictest_thread(thread_id, thread_data)

    return CyclictestMetrics(
        t0=data['start_time'],
        t1=data['end_time'],
        threads=threads,
    )

def proc_interrupts(start_snap, end_snap, num_cpus):
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

def mpstat(data):
    if not data or 'sysstat' not in data:
        return None
        
    hosts = data['sysstat'].get('hosts', [])
    if not hosts:
        return None
        
    statistics = hosts[0].get('statistics', [])
    if not statistics:
        return None

    cores_dict = {}

    # We need a helper to ensure a core dict is initialized
    def init_core(core_id):
        if core_id not in cores_dict:
            cores_dict[core_id] = CpuTimelineMetrics(
                timestamps=[],
                usr=[],
                sys=[],
                iowait=[],
                soft=[],
                idle=[],
                intr=[],
                individual_interrupts={},
                soft_interrupts={}
            )

    # Iterate through each timestamp
    for stat in statistics:
        timestamp = stat.get('timestamp', '')
        
        # 1. Process CPU load
        cpu_load = stat.get('cpu-load', [])
        for load in cpu_load:
            core_id = str(load['cpu'])
            init_core(core_id)
            core_metrics = cores_dict[core_id]
            
            # Use the length of 'timestamps' to determine if we've already appended the timestamp for this core
            if len(core_metrics.timestamps) == 0 or core_metrics.timestamps[-1] != timestamp:
                core_metrics.timestamps.append(timestamp)
                
            core_metrics.usr.append(load.get('usr', 0.0))
            core_metrics.sys.append(load.get('sys', 0.0))
            core_metrics.iowait.append(load.get('iowait', 0.0))
            core_metrics.soft.append(load.get('soft', 0.0))
            core_metrics.idle.append(load.get('idle', 0.0))

        # 2. Process sum-interrupts
        sum_intr = stat.get('sum-interrupts', [])
        for intr in sum_intr:
            core_id = str(intr['cpu'])
            init_core(core_id)
            cores_dict[core_id].intr.append(intr.get('intr', 0.0))
            
        # 3. Process individual-interrupts
        indiv_intr = stat.get('individual-interrupts', [])
        for intr_group in indiv_intr:
            core_id = str(intr_group['cpu'])
            init_core(core_id)
            indiv_dict = cores_dict[core_id].individual_interrupts
            
            for intr_item in intr_group.get('intr', []):
                name = intr_item['name']
                value = intr_item['value']
                if name not in indiv_dict:
                    indiv_dict[name] = []
                indiv_dict[name].append(value)
                
        # 4. Process soft-interrupts
        soft_intr = stat.get('soft-interrupts', [])
        for intr_group in soft_intr:
            core_id = str(intr_group['cpu'])
            init_core(core_id)
            soft_dict = cores_dict[core_id].soft_interrupts
            
            for intr_item in intr_group.get('intr', []):
                name = intr_item['name']
                value = intr_item['value']
                if name not in soft_dict:
                    soft_dict[name] = []
                soft_dict[name].append(value)

    output = MpstatMetrics(cores=cores_dict)

    # 5. Compute global averages for "all" core over the entire run
    all_core = cores_dict.get('all')
    if all_core and len(all_core.usr) > 0:
        output.avg_user = sum(all_core.usr) / len(all_core.usr)
        output.avg_system = sum(all_core.sys) / len(all_core.sys)
        output.avg_softirq = sum(all_core.soft) / len(all_core.soft)
        output.avg_idle = sum(all_core.idle) / len(all_core.idle)
    
    return output

def parse_pid_chrt(filepath: str) -> dict:
    """Parses pid_chrt.log to extract scheduling policies."""
    policies = {}
    try:
        with open(filepath, 'r') as f:
            for line in f:
                if 'current scheduling policy:' in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        pid = parts[1].strip("'s")
                        policy = parts[-1]
                        policies[pid] = policy
    except FileNotFoundError:
        pass
    return policies

def parse_led_toggle_edges(filepath: str) -> float:
    """Parses led_toggle_edges.csv and returns the very first toggle timestamp (CLOCK_MONOTONIC)."""
    try:
        df = pd.read_csv(filepath)
        if not df.empty:
            return float(df['Time'].iloc[0])
    except (FileNotFoundError, pd.errors.EmptyDataError):
        pass
    return 0.0

def vmstat(filepath: str):
    """Parses vmstat.log."""    
    timestamps = []
    cs = []
    _in = []
    usr = []
    sys_cpu = []
    idle = []
    wa = []
    mem_free = []
    mem_buff = []
    mem_cache = []
    bi = []
    bo = []
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        for line in lines[2:]:  # skip headers
            parts = line.strip().split()
            if len(parts) >= 20:
                mem_free.append(int(parts[3]))
                mem_buff.append(int(parts[4]))
                mem_cache.append(int(parts[5]))
                bi.append(int(parts[8]))
                bo.append(int(parts[9]))
                _in.append(int(parts[10]))
                cs.append(int(parts[11]))
                usr.append(int(parts[12]))
                sys_cpu.append(int(parts[13]))
                idle.append(int(parts[14]))
                wa.append(int(parts[15]))
                timestamps.append(parts[18] + ' ' + parts[19])
    except FileNotFoundError:
        return None
        
    if not timestamps:
        return None
        
    return VmstatMetrics(
        timestamps=np.array(timestamps),
        context_switches=np.array(cs),
        interrupts=np.array(_in),
        usr=np.array(usr),
        sys=np.array(sys_cpu),
        idle=np.array(idle),
        wa=np.array(wa),
        memory_free=np.array(mem_free),
        memory_buff=np.array(mem_buff),
        memory_cache=np.array(mem_cache),
        blocks_in=np.array(bi),
        blocks_out=np.array(bo)
    )

def pidstat(filepath: str):
    timestamps = []
    pid_cpu = {}
    pid_cswch = {}
    pid_nvcswch = {}
    
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        current_time = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith('Linux') or line.startswith('Average:'):
                continue
                
            parts = line.split()
            if len(parts) < 3:
                continue
                
            if 'UID' in parts and 'PID' in parts:
                continue
                
            time_str = parts[0]
            cmd = parts[-1]
            
            if len(parts) == 10:
                cpu_usage = float(parts[7])
                if cmd not in pid_cpu:
                    pid_cpu[cmd] = []
                pid_cpu[cmd].append(cpu_usage)
                if time_str not in timestamps:
                    timestamps.append(time_str)
            elif len(parts) == 6:
                cswch = float(parts[3])
                nvcswch = float(parts[4])
                if cmd not in pid_cswch:
                    pid_cswch[cmd] = []
                    pid_nvcswch[cmd] = []
                pid_cswch[cmd].append(cswch)
                pid_nvcswch[cmd].append(nvcswch)
                
    except FileNotFoundError:
        return None

    if not timestamps:
        return None
        
    for k in pid_cpu:
        pid_cpu[k] = np.array(pid_cpu[k])
    for k in pid_cswch:
        pid_cswch[k] = np.array(pid_cswch[k])
        pid_nvcswch[k] = np.array(pid_nvcswch[k])
        
    return PidstatMetrics(
        timestamps=np.array(timestamps),
        pid_cpu=pid_cpu,
        pid_cswch=pid_cswch,
        pid_nvcswch=pid_nvcswch
    )

def iperf3(filepath: str):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
            
        intervals = data.get('intervals', [])
        timestamps = []
        bits_per_second = []
        retransmits = []
        rtt = []
        
        for interval in intervals:
            sum_data = interval.get('sum', {})
            timestamps.append(sum_data.get('end', 0.0))
            bits_per_second.append(sum_data.get('bits_per_second', 0.0))
            retransmits.append(sum_data.get('retransmits', 0))
            
            streams = interval.get('streams', [])
            if streams:
                rtt.append(streams[0].get('rtt', 0.0))
            else:
                rtt.append(0.0)
                
        return Iperf3Metrics(
            timestamps=timestamps,
            bits_per_second=bits_per_second,
            retransmits=retransmits,
            rtt=rtt,
            cpu_util_host=data.get('end', {}).get('cpu_utilization_percent', {}).get('host_total', None),
            cpu_util_remote=data.get('end', {}).get('cpu_utilization_percent', {}).get('remote_total', None),
            start_time=data.get('start', {}).get('timestamp', {}).get('time', None),
            end_time=data.get('end', {}).get('timestamp', {}).get('time', None)
        )
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def fio(load_dir: str):
    metrics = FioMetrics()
    
    summary_file = os.path.join(load_dir, 'fio_summary.json')
    try:
        with open(summary_file, 'r') as f:
            metrics.summary = json.load(f)
    except:
        pass
            
    for i in range(1, 5):
        clat_file = os.path.join(load_dir, f'fio_latency_clat.{i}.log')
        slat_file = os.path.join(load_dir, f'fio_latency_slat.{i}.log')
        bw_file = os.path.join(load_dir, f'fio_bw_bw.{i}.log')
        iops_file = os.path.join(load_dir, f'oufio_iops_iops.{i}.log')
        
        try:
            with open(clat_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        metrics.clat_ns.append(int(parts[1].strip()))
        except:
            pass
            
        try:
            with open(slat_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        metrics.slat_ns.append(int(parts[1].strip()))
        except:
            pass
            
        try:
            with open(bw_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        metrics.bandwidth_kbps.append(float(parts[1].strip()))
        except:
            pass

        try:
            with open(iops_file, 'r') as f:
                for line in f:
                    parts = line.strip().split(',')
                    if len(parts) >= 2:
                        metrics.iops.append(float(parts[1].strip()))
        except:
            pass
            
    return metrics
