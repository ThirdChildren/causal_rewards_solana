"""Signed-observation generation and aggregation to the cohort x time-block level.

Per sensor per time block we draw a usable-observation count. Faults zero it out; sybils
inflate it (duplication without information); demand scales it. Counts are then aggregated
to the estimand grid (cell x time_block). Only aggregated counts feed eligibility and the
benchmark baselines — no per-sensor counterfactual is ever formed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from depin_sim.config import ScenarioConfig
from depin_sim.network import Network
from depin_sim.seeds import RngBundle

_BASE_LAMBDA = 6.0  # expected usable observations per (healthy, avg-quality, avg-demand) block


@dataclass(frozen=True)
class Observations:
    # Sensor x time-block signed-observation counts, int64 [n_sensors, n_time_blocks].
    sensor_counts: np.ndarray
    # Cohort (cell) x time-block aggregates.
    cohort_counts: np.ndarray        # int64 total signed observations
    cohort_quality_sum: np.ndarray   # float sum of quality-weighted eligible observations
    cohort_active_sensors: np.ndarray  # int64 sensors emitting > 0 in the block
    demand_factor: np.ndarray        # float [n_time_blocks]


def demand_factor(cfg: ScenarioConfig) -> np.ndarray:
    """Deterministic demand multiplier per time block (no RNG: shape is a fixed function)."""
    t = np.arange(cfg.n_time_blocks, dtype=np.float64)
    amp = cfg.demand.shift_amplitude
    if amp == 0.0 or cfg.n_time_blocks == 1:
        return np.ones(cfg.n_time_blocks, dtype=np.float64)
    if cfg.demand.pattern == "ramp":
        frac = t / max(1, cfg.n_time_blocks - 1)
        return 1.0 + amp * (frac - 0.5)
    if cfg.demand.pattern == "seasonal":
        return 1.0 + amp * 0.5 * np.sin(2.0 * np.pi * t / cfg.n_time_blocks)
    if cfg.demand.pattern == "step":
        half = cfg.n_time_blocks // 2
        return np.where(t < half, 1.0 - amp * 0.5, 1.0 + amp * 0.5)
    raise ValueError(f"unknown demand pattern {cfg.demand.pattern!r}")


def generate_observations(cfg: ScenarioConfig, net: Network, rng: RngBundle) -> Observations:
    cfg.validate()
    fault_rng = rng.stream("faults")
    obs_rng = rng.stream("observations")

    n_sensors = net.n_sensors
    n_t = cfg.n_time_blocks
    dfac = demand_factor(cfg)

    quality = net.sensor_quality  # [n_sensors]
    # Fault probability rises for low-quality sensors.
    fault_p = cfg.faults.base_risk * (1.0 + cfg.faults.quality_sensitivity * (1.0 - quality))
    fault_p = np.clip(fault_p, 0.0, 1.0)

    # Expected count per sensor per block: quality- and demand-scaled.
    quality_mult = 0.5 + quality  # [n_sensors]
    lam = _BASE_LAMBDA * quality_mult[:, None] * dfac[None, :]  # [n_sensors, n_t]

    counts = obs_rng.poisson(lam).astype(np.int64)  # drawn in fixed [sensor, block] order

    faulted = fault_rng.random(size=(n_sensors, n_t)) < fault_p[:, None]
    counts[faulted] = 0

    # Sybil inflation: duplicated observations add activity, not information.
    if cfg.sybil.replication_factor != 1.0:
        rep = np.where(net.sensor_is_sybil, cfg.sybil.replication_factor, 1.0)
        counts = np.round(counts * rep[:, None]).astype(np.int64)

    # Aggregate to cohort (cell) x time-block.
    n_cells = net.n_cells
    cohort_counts = np.zeros((n_cells, n_t), dtype=np.int64)
    cohort_quality_sum = np.zeros((n_cells, n_t), dtype=np.float64)
    cohort_active = np.zeros((n_cells, n_t), dtype=np.int64)

    cell_of = net.sensor_cell
    # Quality-weight sybil-duplicated observations down to reflect zero marginal information.
    info_weight = np.where(net.sensor_is_sybil, 0.0, 1.0) * quality  # [n_sensors]
    for s in range(n_sensors):
        c = cell_of[s]
        row = counts[s]
        cohort_counts[c] += row
        cohort_quality_sum[c] += row * info_weight[s]
        cohort_active[c] += (row > 0).astype(np.int64)

    return Observations(
        sensor_counts=counts,
        cohort_counts=cohort_counts,
        cohort_quality_sum=cohort_quality_sum,
        cohort_active_sensors=cohort_active,
        demand_factor=dfac,
    )
