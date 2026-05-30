import math
import numpy as np
from models import CyclictestMetrics, CyclictestThreadMetrics, MpstatMetrics, CpuTimelineMetrics

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