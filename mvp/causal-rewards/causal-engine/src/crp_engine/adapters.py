"""Adapters from upstream table shapes into the engine's analysis panel.

Read-only: this module never modifies the simulator or the audit bundle. ``simulator/`` owns its
scenario definitions and its committed baseline content hash; the engine adapts to it, not the
other way round.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["panel_from_simulator", "participants_from_simulator"]

#: ``simulator``'s ``cohort_blocks`` table (see ``simulator/src/depin_sim/run.py``).
_SIM_COLUMNS = (
    "cell_id",
    "time_block",
    "treated",
    "eligible",
    "signed_obs_count",
    "quality_weighted_obs",
    "active_sensors",
    "held_out_rmse",
)


def panel_from_simulator(cohort_blocks: pd.DataFrame) -> pd.DataFrame:
    """Map a simulator ``cohort_blocks`` table onto the engine's panel contract.

    ``cell_id`` (the simulator's geographic cell) IS the geo-cohort; a row is a cohort x
    time-block unit, which is exactly the frozen estimand (Invariant 4). ``eligible`` carries the
    simulator's guard-band / carryover exclusions through as an upstream eligibility flag, so the
    engine counts them in ``excluded_records`` rather than silently inheriting them.
    """
    missing = [c for c in _SIM_COLUMNS if c not in cohort_blocks.columns]
    if missing:
        raise ValueError("simulator cohort_blocks table is missing columns: %s" % missing)
    treated = cohort_blocks["treated"].to_numpy().astype(bool)
    return pd.DataFrame(
        {
            "cohort_id": ["cell%04d" % int(v) for v in cohort_blocks["cell_id"]],
            "time_block": cohort_blocks["time_block"].astype("int64"),
            "arm": np.where(treated, "treatment", "control"),
            "outcome": cohort_blocks["held_out_rmse"].astype("float64"),
            "n_units": cohort_blocks["active_sensors"].astype("int64"),
            "n_observations": cohort_blocks["signed_obs_count"].astype("int64"),
            "eligible": cohort_blocks["eligible"].astype(bool),
        }
    )


def participants_from_simulator(
    sensors: pd.DataFrame, cohort_blocks: pd.DataFrame, *, quality_scale: int = 1_000_000
) -> pd.DataFrame:
    """Build a Stage-2 participant table from the simulator's sensor + cohort tables.

    The simulator has no signer keys, so a device's ``recipient_hex`` is a deterministic stand-in
    derived from its ``sensor_id`` (``sha256("crp-sim-signer:" || sensor_id)``). In a real run the
    recipient is the ed25519 pubkey that signed the observations — never a synthesized value.
    """
    import hashlib

    totals = (
        cohort_blocks.groupby("cell_id", sort=True)[["signed_obs_count", "quality_weighted_obs"]]
        .sum()
        .reset_index()
    )
    counts = sensors.groupby("cell_id", sort=True)["sensor_id"].count().to_dict()
    obs_by_cell = dict(zip(totals["cell_id"], totals["signed_obs_count"]))
    qual_by_cell = dict(zip(totals["cell_id"], totals["quality_weighted_obs"]))

    rows = []
    for r in sensors.sort_values("sensor_id", kind="mergesort").itertuples(index=False):
        cell = int(getattr(r, "cell_id"))
        n = max(1, int(counts.get(cell, 1)))
        quality_micro = int(round(float(getattr(r, "quality")) * quality_scale))
        share_obs = int(obs_by_cell.get(cell, 0)) // n
        rows.append(
            {
                "cohort_id": "cell%04d" % cell,
                "recipient_hex": hashlib.sha256(
                    b"crp-sim-signer:" + str(getattr(r, "sensor_id")).encode("utf-8")
                ).hexdigest(),
                "accepted_observations": share_obs,
                "quality_adjusted_observations": share_obs * max(0, quality_micro),
            }
        )
    return pd.DataFrame(rows)
