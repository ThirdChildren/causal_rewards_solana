"""Outcome generation: the primary outcome is out-of-sample prediction error (held-out RMSE)
at the cohort x time-block level. Lower is better.

This module encodes the SIMULATOR GROUND TRUTH (true effect, interference, confounding). The
causal engine (M3) never sees these knobs; it must recover the effect from the observed
outcomes alone. Keeping the truth here lets us build known-answer tests later and design the
null / low-power scenarios honestly.

True model for cohort i, block t:
    rmse[i,t] = baseline
              - effect_i * treated[i,t] * eligible[i,t]        # direct causal effect
              - interference * effect_i * spill[i,t]           # spillover from treated neighbors
              + confounding * (info_value_i - mean_info)       # confounder (observational)
              + cluster_noise_i                                # cohort-shared noise -> cluster SEs
              + obs_noise[i,t]                                  # residual
Effects are heterogeneous: sparse / high-info cohorts help more (larger RMSE reduction).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from depin_sim.assignment import Assignment
from depin_sim.config import ScenarioConfig
from depin_sim.network import Network, neighbor_cells
from depin_sim.seeds import RngBundle


@dataclass(frozen=True)
class Outcomes:
    rmse: np.ndarray            # float [n_cells, n_time_blocks] observed outcome
    cohort_effect: np.ndarray   # float [n_cells] ground-truth per-cohort effect magnitude
    treated: np.ndarray         # bool [n_cells, n_time_blocks] (echo of assignment)
    eligible: np.ndarray        # bool [n_cells, n_time_blocks]


def _neighbor_matrix(net: Network) -> list[list[int]]:
    return [neighbor_cells(net, i, radius=1) for i in range(net.n_cells)]


def generate_outcomes(
    cfg: ScenarioConfig,
    net: Network,
    assignment: Assignment,
    rng: RngBundle,
) -> Outcomes:
    cfg.validate()
    g = rng.stream("outcome")
    eff = cfg.effect
    n_cells, n_t = net.n_cells, cfg.n_time_blocks

    # Heterogeneous per-cohort effect: scaled by information value, jittered multiplicatively.
    het = g.lognormal(mean=0.0, sigma=eff.effect_heterogeneity, size=n_cells)
    cohort_effect = eff.true_effect * (0.5 + net.cell_info_value) * het  # [n_cells]

    treated = assignment.treated
    eligible = assignment.eligible

    # Spillover: fraction of treated neighbors in the same block contaminates a cohort.
    spill = np.zeros((n_cells, n_t), dtype=np.float64)
    if eff.interference != 0.0:
        nbrs = _neighbor_matrix(net)
        for i in range(n_cells):
            if not nbrs[i]:
                continue
            treated_nbr = treated[nbrs[i], :].astype(np.float64)  # [k, n_t]
            spill[i] = treated_nbr.mean(axis=0)

    # Confounder term (per cohort, constant across blocks).
    conf = eff.confounding * (net.cell_info_value - net.cell_info_value.mean())  # [n_cells]

    # Noise: cohort-shared (cluster) + residual. Cluster noise is why SEs must be
    # cluster-robust — treating blocks within a cohort as independent understates variance.
    cluster_noise = g.normal(0.0, eff.cluster_noise_sd, size=n_cells)          # [n_cells]
    obs_noise = g.normal(0.0, eff.obs_noise_sd, size=(n_cells, n_t))           # [n_cells, n_t]

    direct = cohort_effect[:, None] * (treated & eligible).astype(np.float64)
    spill_term = eff.interference * cohort_effect[:, None] * spill

    rmse = (
        eff.baseline_rmse
        - direct
        - spill_term
        + conf[:, None]
        + cluster_noise[:, None]
        + obs_noise
    )
    rmse = np.maximum(rmse, 0.0)  # RMSE cannot be negative

    return Outcomes(
        rmse=rmse,
        cohort_effect=cohort_effect,
        treated=treated,
        eligible=eligible,
    )
