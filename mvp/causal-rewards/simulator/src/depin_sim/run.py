"""Orchestrate one deterministic scenario run and assemble its artifact + content hash.

Pipeline (fixed order — determinism contract):
    seed -> RngBundle -> network -> assignment -> observations -> outcomes -> artifact -> hash

The content hash covers the SCIENTIFIC CONTENT only: the resolved config plus every generated
table. It deliberately EXCLUDES environment provenance (package versions, wall-clock, host) so
that same-seed reruns on the pinned container reproduce an identical hash. Cross-environment
reproducibility is guaranteed instead by pinning the container digest (see requirements.txt).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from depin_sim import __version__
from depin_sim.assignment import Assignment, assign
from depin_sim.canonical import FLOAT_SCALE, content_hash
from depin_sim.config import ScenarioConfig
from depin_sim.network import Network, build_network
from depin_sim.observations import Observations, generate_observations
from depin_sim.outcomes import Outcomes, generate_outcomes
from depin_sim.seeds import build_rng_bundle

# Bumped when the data-generating process changes in a way that alters output bytes.
DGP_VERSION = "dgp-v0.1.0"


@dataclass(frozen=True)
class RunResult:
    config: ScenarioConfig
    network: Network
    assignment: Assignment
    observations: Observations
    outcomes: Outcomes
    artifact: dict
    content_hash: str


def _sensor_table(net: Network) -> dict:
    return {
        "sensor_id": net.sensor_id,
        "cell_id": net.sensor_cell,
        "quality": net.sensor_quality,
        "is_sybil": net.sensor_is_sybil,
        "sybil_group": net.sensor_sybil_group,
    }


def _cell_table(net: Network) -> dict:
    return {
        "cell_id": net.cell_id,
        "row": net.cell_row,
        "col": net.cell_col,
        "is_sparse": net.cell_is_sparse,
        "info_value": net.cell_info_value,
        "sensor_count": net.cell_sensor_count,
    }


def _cohort_block_table(
    net: Network, obs: Observations, asg: Assignment, out: Outcomes, cfg: ScenarioConfig
) -> dict:
    """Long-form (cell, time_block) grid: the estimand table the causal engine will consume."""
    n_cells, n_t = net.n_cells, cfg.n_time_blocks
    cell_idx = np.repeat(np.arange(n_cells, dtype=np.int64), n_t)
    block_idx = np.tile(np.arange(n_t, dtype=np.int64), n_cells)
    eligible_min_sample = obs.cohort_counts >= cfg.minimum_sample
    return {
        "cell_id": cell_idx,
        "time_block": block_idx,
        "treated": asg.treated.reshape(-1),
        "eligible": asg.eligible.reshape(-1),
        "meets_min_sample": eligible_min_sample.reshape(-1),
        "signed_obs_count": obs.cohort_counts.reshape(-1),
        "quality_weighted_obs": obs.cohort_quality_sum.reshape(-1),
        "active_sensors": obs.cohort_active_sensors.reshape(-1),
        "held_out_rmse": out.rmse.reshape(-1),
    }


def run_scenario(cfg: ScenarioConfig) -> RunResult:
    cfg.validate()
    rng = build_rng_bundle(cfg.seed)

    net = build_network(cfg, rng)
    asg = assign(cfg, net, rng)
    obs = generate_observations(cfg, net, rng)
    out = generate_outcomes(cfg, net, asg, rng)

    # Content payload (hashed): config + all generated tables + DGP version.
    content = {
        "dgp_version": DGP_VERSION,
        "float_scale": FLOAT_SCALE,
        "config": cfg.to_dict(),
        "sensors": _sensor_table(net),
        "cells": _cell_table(net),
        "cohort_blocks": _cohort_block_table(net, obs, asg, out, cfg),
        "demand_factor": obs.demand_factor,
        "assignment_derivation": asg.derivation,
    }
    chash = content_hash(content)

    # Full artifact adds non-hashed metadata for humans / downstream tooling.
    artifact = {
        "schema": "depin_sim.run/v0",
        "simulator_version": __version__,
        "content_hash": chash,
        "summary": _summary(cfg, net, obs, out, asg),
        "content": content,
    }

    return RunResult(
        config=cfg,
        network=net,
        assignment=asg,
        observations=obs,
        outcomes=out,
        artifact=artifact,
        content_hash=chash,
    )


def _summary(
    cfg: ScenarioConfig, net: Network, obs: Observations, out: Outcomes, asg: Assignment
) -> dict:
    total_obs = int(obs.cohort_counts.sum())
    n_units = net.n_cells * cfg.n_time_blocks
    treated_units = int(asg.treated.sum())
    eligible_units = int(asg.eligible.sum())
    meets_min = int((obs.cohort_counts >= cfg.minimum_sample).sum())
    return {
        "name": cfg.name,
        "design": cfg.design,
        "n_cells": net.n_cells,
        "n_sensors": net.n_sensors,
        "n_time_blocks": cfg.n_time_blocks,
        "n_cohort_blocks": n_units,
        "total_signed_observations": total_obs,
        "treated_cohort_blocks": treated_units,
        "eligible_cohort_blocks": eligible_units,
        "cohort_blocks_meeting_min_sample": meets_min,
        "true_effect": cfg.effect.true_effect,
        "mean_cohort_effect": float(out.cohort_effect.mean()),
        "sybil_sensor_fraction": float(net.sensor_is_sybil.mean()),
    }
