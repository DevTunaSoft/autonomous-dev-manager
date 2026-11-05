"""Resource-aware admission decisions; never changes verification requirements.

All figures are snapshots, not reservations. The caller must re-check immediately
before launching a job. This module does not claim GPU/model capability.
"""
from dataclasses import dataclass
from typing import Mapping
import math

GIB = 1024 ** 3

@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    max_parallel_builds: int
    unload_model_first: bool
    resource_mode: str


def decide(snapshot: Mapping, *, job_ram_gib: float, job_disk_gib: float = 1,
           model_loaded_gib: float = 0, active_builds: int = 0) -> Decision:
    """Conservative admission policy; fail closed when memory/disk unknown or malformed."""
    def _num(v):
        return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None

    params = (job_ram_gib, job_disk_gib, model_loaded_gib)
    if (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in params)
            or not isinstance(active_builds, int) or isinstance(active_builds, bool)
            or job_ram_gib <= 0 or job_disk_gib < 0 or model_loaded_gib < 0 or active_builds < 0):
        raise ValueError('Invalid resource request')
    available = _num(snapshot.get('ram_available_bytes') if isinstance(snapshot, Mapping) else None)
    disk = _num(snapshot.get('disk_free_bytes') if isinstance(snapshot, Mapping) else None)
    cpus_raw = _num(snapshot.get('cpu_count') if isinstance(snapshot, Mapping) else None)
    cpus = int(cpus_raw) if cpus_raw and cpus_raw >= 1 else 1
    if available is None or disk is None or available < 0 or disk < 0:
        return Decision(False, 'Resource information unavailable or malformed', 0, False, 'constrained')
    ram_gib, disk_gib = available / GIB, disk / GIB
    if disk_gib < job_disk_gib + 2:
        return Decision(False, 'Insufficient disk safety reserve', 0, False, 'constrained')
    mode = ('constrained' if ram_gib < 8 or disk_gib < 10 else
            'balanced' if ram_gib < 20 else 'performance')
    max_parallel = 1 if mode == 'constrained' else min(2 if mode == 'balanced' else 4, max(1, cpus // 2))
    unload = ram_gib < job_ram_gib + 2 and model_loaded_gib > 0
    effective_ram = ram_gib + (model_loaded_gib if unload else 0)
    if effective_ram < job_ram_gib + 2:
        return Decision(False, 'Insufficient memory even after model unload', max_parallel, unload, mode)
    if active_builds >= max_parallel:
        return Decision(False, 'Build concurrency limit reached', max_parallel, unload, mode)
    if unload:
        return Decision(False, 'Unload local AI model and remeasure before starting', max_parallel, True, mode)
    return Decision(True, 'Resource admission approved; recheck before spawn', max_parallel, False, mode)


def admission_for_build(*, probe, job_ram_gib: float, job_disk_gib: float = 1,
                        model_loaded_gib: float = 0, active_builds: int = 0):
    """Fresh resource admission, not a hard OS resource limit or sandbox."""
    return decide(probe(), job_ram_gib=job_ram_gib,
                  job_disk_gib=job_disk_gib,
                  model_loaded_gib=model_loaded_gib, active_builds=active_builds)
