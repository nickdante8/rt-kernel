from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
import numpy as np

@dataclass
class SyncMetadata:
    """Contains synchronization and validation metadata for the experiment."""
    t_0_wall: float = 0.0
    t_0_hw: float = 0.0
    t_0_mono: float = 0.0
    pid_policies: Dict[str, str] = field(default_factory=dict)

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
class PidstatMetrics:
    timestamps: np.ndarray
    pid_cpu: Dict[str, np.ndarray]
    pid_cswch: Dict[str, np.ndarray]
    pid_nvcswch: Dict[str, np.ndarray]

@dataclass
class ProcInterruptRecord:
    irq: str
    description: str
    delta_cpu: List[float]
    delta_total: float

@dataclass
class ProcInterruptsMetrics:
    records: List[ProcInterruptRecord] = field(default_factory=list)
    delta_cpus_total: List[float] = field(default_factory=list)

@dataclass
class CpuTimelineMetrics:
    timestamps: List[float]
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
class VmstatMetrics:
    timestamps: np.ndarray
    context_switches: np.ndarray
    interrupts: np.ndarray
    usr: np.ndarray
    sys: np.ndarray
    idle: np.ndarray
    wa: np.ndarray
    memory_free: np.ndarray
    memory_buff: np.ndarray
    memory_cache: np.ndarray
    blocks_in: np.ndarray
    blocks_out: np.ndarray
    
@dataclass
class Iperf3Metrics:
    timestamps: List[float] = field(default_factory=list)
    bits_per_second: List[float] = field(default_factory=list)
    retransmits: List[int] = field(default_factory=list)
    rtt: List[float] = field(default_factory=list)
    cpu_util_host: Optional[float] = None
    cpu_util_remote: Optional[float] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

@dataclass
class FioLatencyStats:
    min: float = 0.0
    max: float = 0.0
    mean: float = 0.0
    stddev: float = 0.0

@dataclass
class FioJobMetrics:
    io_kbytes: int = 0
    bw: float = 0.0
    iops: float = 0.0
    total_ios: int = 0
    drop_ios: int = 0
    
    slat_ns: FioLatencyStats = field(default_factory=FioLatencyStats)
    clat_ns: FioLatencyStats = field(default_factory=FioLatencyStats)
    lat_ns: FioLatencyStats = field(default_factory=FioLatencyStats)
    
    bw_dev: float = 0.0
    iops_stddev: float = 0.0
    
    clat_ms: List[float] = field(default_factory=list)
    cfreq: List[int] = field(default_factory=list)

@dataclass
class FioMetrics:
    read_metrics: FioJobMetrics = field(default_factory=FioJobMetrics)
    write_metrics: FioJobMetrics = field(default_factory=FioJobMetrics)
    bw_sec_read: List[int] = field(default_factory=list)
    bw_kbps_read: List[float] = field(default_factory=list)
    bw_sec_write: List[int] = field(default_factory=list)
    bw_kbps_write: List[float] = field(default_factory=list)
    
    iops_sec_read: List[int] = field(default_factory=list)
    iops_count_read: List[float] = field(default_factory=list)
    iops_sec_write: List[int] = field(default_factory=list)
    iops_count_write: List[float] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExperimentDataset:
    """Unified container representing a complete processed test run."""
    config: ExperimentConfig
    saleae: Dict[int, SaleaeSignalMetrics] = field(default_factory=dict)
    saleae_common: Optional[SaleaeCrossMetrics] = None
    cyclictest: Optional[CyclictestMetrics] = None
    proc_interrupts: Optional[ProcInterruptsMetrics] = None
    mpstat: Optional[MpstatMetrics] = None
    vmstat: Optional[VmstatMetrics] = None
    pidstat: Optional[PidstatMetrics] = None
    sync_metadata: Optional[SyncMetadata] = None

    # Future expansions
    iperf3: Optional[Iperf3Metrics] = None
    fio: Optional[FioMetrics] = None

    # Catch-all for dynamic/unknown future metrics
    extra_metrics: Dict[str, Any] = field(default_factory=dict)
