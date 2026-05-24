import math
import numpy as np

def cyclictest(data):
    # Extract thread 0 statistics
    thread_data = data['thread']['0']
    hist_data = thread_data['histogram']
    
    # Convert histogram to latency
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

    return {
        # Extract start/end dates
        't0': data['start_time'],
        't1': data['end_time'],
        
        # histogram and latency
        'histogram': hist_data,
        'latencies': latencies,
        'frequencies': frequencies,

        # Summary metrics
        'cycles': total_cycles,
        'min': thread_data['min'],
        'max': thread_data['max'],
        'avg': avg_lat,
        'std_dev': std_dev,
        'peak_to_peak': (thread_data['max'] - thread_data['min']) if len(latencies) > 0 else 0,
    }

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
    # Initialize the output structure
    output = {
        'cores': {},
        'avg_user': 0.0,
        'avg_system': 0.0,
        'avg_irq': 0.0,
        'avg_softirq': 0.0,
        'avg_idle': 0.0
    }
    
    if not data or 'sysstat' not in data:
        return None
        
    hosts = data['sysstat'].get('hosts', [])
    if not hosts:
        return None
        
    statistics = hosts[0].get('statistics', [])
    if not statistics:
        return None

    # We need a helper to ensure a core dict is initialized
    def init_core(core_id):
        if core_id not in output['cores']:
            output['cores'][core_id] = {
                'timestamps': [],
                'usr': [],
                'sys': [],
                'iowait': [],
                'soft': [],
                'idle': [],
                'intr': [],
                'individual_interrupts': {},
                'soft_interrupts': {}
            }

    # Iterate through each timestamp
    for stat in statistics:
        timestamp = stat.get('timestamp', '')
        
        # 1. Process CPU load
        cpu_load = stat.get('cpu-load', [])
        for load in cpu_load:
            core_id = str(load['cpu'])
            init_core(core_id)
            core_dict = output['cores'][core_id]
            
            # Use the length of 'timestamps' to determine if we've already appended the timestamp for this core
            if len(core_dict['timestamps']) == 0 or core_dict['timestamps'][-1] != timestamp:
                core_dict['timestamps'].append(timestamp)
                
            core_dict['usr'].append(load.get('usr', 0.0))
            core_dict['sys'].append(load.get('sys', 0.0))
            core_dict['iowait'].append(load.get('iowait', 0.0))
            core_dict['soft'].append(load.get('soft', 0.0))
            core_dict['idle'].append(load.get('idle', 0.0))

        # 2. Process sum-interrupts
        sum_intr = stat.get('sum-interrupts', [])
        for intr in sum_intr:
            core_id = str(intr['cpu'])
            init_core(core_id)
            output['cores'][core_id]['intr'].append(intr.get('intr', 0.0))
            
        # 3. Process individual-interrupts
        indiv_intr = stat.get('individual-interrupts', [])
        for intr_group in indiv_intr:
            core_id = str(intr_group['cpu'])
            init_core(core_id)
            indiv_dict = output['cores'][core_id]['individual_interrupts']
            
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
            soft_dict = output['cores'][core_id]['soft_interrupts']
            
            for intr_item in intr_group.get('intr', []):
                name = intr_item['name']
                value = intr_item['value']
                if name not in soft_dict:
                    soft_dict[name] = []
                soft_dict[name].append(value)

    # 5. Compute global averages for "all" core over the entire run
    all_core = output['cores'].get('all')
    if all_core and len(all_core['usr']) > 0:
        output['avg_user'] = sum(all_core['usr']) / len(all_core['usr'])
        output['avg_system'] = sum(all_core['sys']) / len(all_core['sys'])
        output['avg_softirq'] = sum(all_core['soft']) / len(all_core['soft'])
        output['avg_idle'] = sum(all_core['idle']) / len(all_core['idle'])
    
    return output