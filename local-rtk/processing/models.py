from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np

@dataclass(frozen=True)
class ExperimentConfig:
    """Immutable configuration tracking execution parameters."""
    input_dir: str
    test_type: str        # e.g., "PREEMPT_RT_validation"
    load_type: str        # e.g., "load-net", "idle"
    channels: List[int]
    nominal_period_us: int
    duration_s: int

@dataclass
class SaleaeSignalMetrics:
    """Holds calculated timing metrics for an individual physical GPIO channel."""
    channel_name: str
    reference_time: Any
    nominal_period_us: int
    edges_rise: np.ndarray
    edges_fall: np.ndarray
    time_jitter_rise: np.ndarray
    time_jitter_fall: np.ndarray
    time_pulse: np.ndarray
    jitter_rise: np.ndarray
    jitter_fall: np.ndarray
    drifts_rise: np.ndarray
    drifts_fall: np.ndarray
    duty_cycles: np.ndarray
    pulse_widths: np.ndarray
    mean_jitter_rise_us: float
    std_dev_rise_us: float
    max_jitter_rise_us: float
    min_jitter_rise_us: float
    peak_to_peak_jitter_rise_us: float
    mean_jitter_fall_us: float
    std_dev_fall_us: float
    max_jitter_fall_us: float
    min_jitter_fall_us: float
    peak_to_peak_jitter_fall_us: float
    sample_count: int

@dataclass
class SaleaeCrossMetrics:
    """Tracks phase and latency alignment across physical pins."""
    latency: np.ndarray
    phase: np.ndarray
    time_axis: np.ndarray

@dataclass
class CyclictestThreadMetrics:
    """Scheduling jitter metrics for a single cyclictest thread (one CPU)."""
    cpu: int
    histogram: Dict[str, int]
    latencies: List[int]
    frequencies: List[int]
    cycles: int
    min: float
    max: float
    avg: float
    std_dev: float
    peak_to_peak: float
    overflow: int

@dataclass
class CyclictestMetrics:
    """Container for all cyclictest threads across CPUs."""
    t0: str
    t1: str
    threads: Dict[str, CyclictestThreadMetrics]  # keyed by thread id ("0", "1", ...)

@dataclass
class CpuTimelineMetrics:
    timestamps: List[str]
    usr: List[float]
    sys: List[float]
    iowait: List[float]
    soft: List[float]
    idle: List[float]
    intr: List[float]
    individual_interrupts: Dict[str, List[float]]
    soft_interrupts: Dict[str, List[float]]

@dataclass
class MpstatMetrics:
    """Unified profile representing system CPU utilization during the testing window."""
    cores: Dict[str, CpuTimelineMetrics] = field(default_factory=dict)
    avg_user: float = 0.0
    avg_system: float = 0.0
    avg_irq: float = 0.0
    avg_softirq: float = 0.0
    avg_idle: float = 0.0

@dataclass
class Iperf3Metrics:
    pass

@dataclass
class FioMetrics:
    pass

@dataclass
class PidstatMetrics:
    pass

@dataclass
class VmstatMetrics:
    pass

@dataclass
class ExperimentDataset:
    """Unified container representing a complete processed test run."""
    config: ExperimentConfig
    saleae: Dict[int, SaleaeSignalMetrics] = field(default_factory=dict)
    saleae_common: Optional[SaleaeCrossMetrics] = None
    cyclictest: Optional[CyclictestMetrics] = None
    proc_interrupts: Optional[List[Dict[str, Any]]] = None
    mpstat: Optional[MpstatMetrics] = None
    
    # Future expansions
    iperf3: Optional[Iperf3Metrics] = None
    fio: Optional[FioMetrics] = None
    pidstat: Optional[PidstatMetrics] = None
    vmstat: Optional[VmstatMetrics] = None
    
    # Catch-all for dynamic/unknown future metrics
    extra_metrics: Dict[str, Any] = field(default_factory=dict)