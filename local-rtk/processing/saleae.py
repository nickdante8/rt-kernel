import pandas as pd
import numpy as np
from models import SaleaeSignalMetrics, SaleaeCrossMetrics

def timing_analysis(obj, df, time_col, channel_col):
    """
    Calculates Jitter, Drift, Latency, and Phase based on a nominal period.
    """
    expected_edges = (obj.duration_s * 1_000_000) / obj.nominal_period_us
    
    # Using .fillna to ensure we don't miss an edge on row 0 if signal starts High
    prev_val = df[channel_col].shift(1).fillna(df[channel_col].iloc[0])
    
    # Detect Edges (1 -> 0 transition) - falling
    # Detect Edges (0 -> 1 transition) - rising
    falling_dt = df[(df[channel_col] == 0) & (prev_val == 1)][time_col].values
    rising_dt = df[(df[channel_col] == 1) & (prev_val == 0)][time_col].values

    # -------- NORMAL TIMING CONVERSION --------
    # Doesn't use iso8601_timestamp for time capture
    # ------------------------------------------
    # Establish T0 (the first timestamp in the dataset) to keep X-axis relative to the front
    # t0 = pd.to_datetime(falling_dt[0]).tz_localize(None)
    # Convert to microseconds and get values
    # falling_us = np.round(falling_dt * 1_000_000).astype(np.float64)
    # rising_us = np.round(rising_dt * 1_000_000).astype(np.float64)
    # ------------------------------------------

    # --- TIMESTAMP CONVERSION & NORMALIZATION ---
    # Usage of iso8601_timestamp
    # --------------------------------------------
    # Establish T0 (the first timestamp in the dataset) to keep X-axis relative to the front
    t0 = pd.to_datetime(falling_dt[0]).tz_localize(None)

    # Convert edge timestamps to datetime objects, strip timezone
    falling_pts = pd.to_datetime(falling_dt).tz_localize(None)
    rising_pts = pd.to_datetime(rising_dt).tz_localize(None)

    # Subtract T0, convert the delta to total nanoseconds (float64)
    falling_us = np.round((falling_pts - t0).total_seconds().values * 1_000_000).astype(np.float64)
    rising_us = np.round((rising_pts - t0).total_seconds().values * 1_000_000).astype(np.float64)
    # --------------------------------------------

    # Ensure alignment: Start with Falling, End with Rising
    if len(falling_us) > 0 and len(rising_us) > 0 and falling_us[0] > rising_us[0]: 
        rising_us = rising_us[1:]
        
    min_len = min(len(rising_us), len(falling_us))
    if min_len < 2:
        return {'error': "Not enough pulses detected for analysis"}
    
    # Filter out end jitter for PWM signal
    if min_len > expected_edges:
        print(f"Number of edges exceeded. Expected {expected_edges}, got {min_len}.")
        return {'error': f"Expected {expected_edges}, got {min_len}."}
    
    # Construct data
    falling_us = falling_us[:min_len]
    rising_us = rising_us[:min_len]

    # Falling Edge Metrics (N-1 samples)
    periods_fall = np.diff(falling_us)
    time_jitter_fall = falling_us[1:]
    jitter_fall = (periods_fall - obj.nominal_period_us)
    drift_fall = np.cumsum(jitter_fall)

    # Rising Edge Metrics (N-1 samples)
    # Time axis for jitter is the time of the edge that "arrived" (rising_us[1:])
    periods_rise = np.diff(rising_us)
    time_jitter_rise = rising_us[1:] 
    jitter_rise = (periods_rise - obj.nominal_period_us)
    drift_rise = np.cumsum(jitter_rise)

    # Pulse Metrics (N samples)
    # Time axis is the start of each pulse
    time_pulse = falling_us 
    pulse_widths = rising_us - falling_us
    duty_cycles = (pulse_widths.astype(float) / obj.nominal_period_us) * 100

    return SaleaeSignalMetrics(
        reference_time=t0,
        time_jitter_rise=time_jitter_rise,
        time_jitter_fall=time_jitter_fall,
        time_pulse=time_pulse,
        nominal_period_us=obj.nominal_period_us,
        edges_rise=rising_us,
        edges_fall=falling_us,
        jitter_rise=jitter_rise,
        jitter_fall=jitter_fall,
        drifts_rise=drift_rise,
        drifts_fall=drift_fall,
        duty_cycles=duty_cycles,
        pulse_widths=pulse_widths,
        channel_name=channel_col,
        mean_jitter_rise_us=jitter_rise.mean() if len(jitter_rise) > 0 else 0,
        std_dev_rise_us=jitter_rise.std() if len(jitter_rise) > 0 else 0,
        max_jitter_rise_us=jitter_rise.max() if len(jitter_rise) > 0 else 0,
        min_jitter_rise_us=jitter_rise.min() if len(jitter_rise) > 0 else 0,
        peak_to_peak_jitter_rise_us=(jitter_rise.max() - jitter_rise.min()) if len(jitter_rise) > 0 else 0,
        mean_jitter_fall_us=jitter_fall.mean() if len(jitter_fall) > 0 else 0,
        std_dev_fall_us=jitter_fall.std() if len(jitter_fall) > 0 else 0,
        max_jitter_fall_us=jitter_fall.max() if len(jitter_fall) > 0 else 0,
        min_jitter_fall_us=jitter_fall.min() if len(jitter_fall) > 0 else 0,
        peak_to_peak_jitter_fall_us=(jitter_fall.max() - jitter_fall.min()) if len(jitter_fall) > 0 else 0,
        sample_count=len(df)
    )

def phase_shift_analysis(edges0, edges1, nominal_period_us):
    # Cross-Channel Calculations (Latency & Phase)
    # Ensure we compare the same number of pulses
    min_len = min(len(edges0), len(edges1))
    latency = edges1[:min_len] - edges0[:min_len]
    phase_diff = (latency / nominal_period_us) * 360

    return SaleaeCrossMetrics(
        latency=latency,
        phase=phase_diff,
        time_axis=edges0[:min_len]
    )
