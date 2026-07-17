"""Network topology: geographic cells (cohorts) and the sensors placed in them.

A cohort == one geographic cell. The experimental unit is (cell, time_block). Sensors are
below the estimand line: we generate them to produce activity/observation counts and to let
activity/quality/scarcity baselines have something to score, but no per-sensor counterfactual
is ever estimated.

Determinism: cells are laid out on a fixed row-major grid (no randomness in indexing); only
attribute *draws* use RNG streams, consumed in a fixed cell/sensor order.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from depin_sim.config import ScenarioConfig
from depin_sim.seeds import RngBundle


@dataclass(frozen=True)
class Network:
    # Cell (cohort) level, indexed 0..n_cells-1.
    cell_id: np.ndarray            # int64
    cell_row: np.ndarray           # int64 grid coordinate
    cell_col: np.ndarray           # int64 grid coordinate
    cell_is_sparse: np.ndarray     # bool; sparse => high marginal information value
    cell_info_value: np.ndarray    # float in ~[0,1]; drives heterogeneous causal effect
    cell_sensor_count: np.ndarray  # int64

    # Sensor level, indexed 0..n_sensors-1.
    sensor_id: np.ndarray          # int64
    sensor_cell: np.ndarray        # int64 -> cell_id
    sensor_quality: np.ndarray     # float in [0,1]
    sensor_is_sybil: np.ndarray    # bool
    sensor_sybil_group: np.ndarray # int64; -1 if not a sybil

    @property
    def n_cells(self) -> int:
        return int(self.cell_id.shape[0])

    @property
    def n_sensors(self) -> int:
        return int(self.sensor_id.shape[0])


def _grid_shape(n_cells: int) -> tuple[int, int]:
    """Deterministic near-square row-major grid covering n_cells cells."""
    cols = int(np.ceil(np.sqrt(n_cells)))
    rows = int(np.ceil(n_cells / cols))
    return rows, cols


def neighbor_cells(net: Network, cell_index: int, radius: int = 1) -> list[int]:
    """4/8-neighborhood cell indices within Chebyshev ``radius`` on the grid (for spillover)."""
    r0, c0 = int(net.cell_row[cell_index]), int(net.cell_col[cell_index])
    coord_to_idx = {
        (int(net.cell_row[i]), int(net.cell_col[i])): i for i in range(net.n_cells)
    }
    out: list[int] = []
    for dr in range(-radius, radius + 1):
        for dc in range(-radius, radius + 1):
            if dr == 0 and dc == 0:
                continue
            idx = coord_to_idx.get((r0 + dr, c0 + dc))
            if idx is not None:
                out.append(idx)
    return sorted(out)


def build_network(cfg: ScenarioConfig, rng: RngBundle) -> Network:
    cfg.validate()
    net_rng = rng.stream("network")
    qual_rng = rng.stream("quality")
    sybil_rng = rng.stream("sybil")

    n_cells = cfg.n_cells
    rows, cols = _grid_shape(n_cells)
    cell_row = np.array([i // cols for i in range(n_cells)], dtype=np.int64)
    cell_col = np.array([i % cols for i in range(n_cells)], dtype=np.int64)

    # Sparse cells: choose a deterministic count, sampled without replacement.
    n_sparse = int(round(cfg.coverage.sparse_cell_fraction * n_cells))
    cell_is_sparse = np.zeros(n_cells, dtype=bool)
    if n_sparse > 0:
        sparse_idx = net_rng.choice(n_cells, size=n_sparse, replace=False)
        cell_is_sparse[np.sort(sparse_idx)] = True

    # Information value: sparse cells carry more marginal value; dense cells less.
    # Bounded to [0,1]. Drawn per cell in fixed order.
    base_info = net_rng.beta(2.0, 3.0, size=n_cells)
    cell_info_value = np.where(cell_is_sparse, 0.6 + 0.4 * base_info, 0.2 * base_info)
    cell_info_value = np.clip(cell_info_value, 0.0, 1.0)

    # Expected sensors per cell: gamma-distributed, forced low for sparse cells.
    shape = cfg.coverage.dispersion
    scale_dense = cfg.coverage.mean_sensors_per_cell / shape
    scale_sparse = cfg.coverage.sparse_sensors_per_cell / shape
    scale = np.where(cell_is_sparse, scale_sparse, scale_dense)
    expected = net_rng.gamma(shape, scale, size=n_cells)
    cell_sensor_count = np.maximum(1, np.round(expected)).astype(np.int64)

    # Materialize sensors, cell-by-cell in fixed order.
    sensor_cell = np.repeat(np.arange(n_cells, dtype=np.int64), cell_sensor_count)
    n_sensors = int(sensor_cell.shape[0])
    sensor_id = np.arange(n_sensors, dtype=np.int64)
    sensor_quality = qual_rng.beta(cfg.quality.alpha, cfg.quality.beta, size=n_sensors)

    # Sybils: select a fraction of sensors, cluster them into replication groups.
    sensor_is_sybil = np.zeros(n_sensors, dtype=bool)
    sensor_sybil_group = np.full(n_sensors, -1, dtype=np.int64)
    frac = cfg.sybil.sensor_fraction
    if frac > 0.0 and n_sensors > 0:
        n_sybil = int(round(frac * n_sensors))
        if n_sybil > 0:
            chosen = np.sort(sybil_rng.choice(n_sensors, size=n_sybil, replace=False))
            sensor_is_sybil[chosen] = True
            gsize = max(1, cfg.sybil.group_size)
            for g, start in enumerate(range(0, chosen.shape[0], gsize)):
                sensor_sybil_group[chosen[start:start + gsize]] = g

    return Network(
        cell_id=np.arange(n_cells, dtype=np.int64),
        cell_row=cell_row,
        cell_col=cell_col,
        cell_is_sparse=cell_is_sparse,
        cell_info_value=cell_info_value,
        cell_sensor_count=cell_sensor_count,
        sensor_id=sensor_id,
        sensor_cell=sensor_cell,
        sensor_quality=sensor_quality,
        sensor_is_sybil=sensor_is_sybil,
        sensor_sybil_group=sensor_sybil_group,
    )
