"""A small, fully deterministic demo dataset — used by the determinism gate and the examples.

This is NOT the simulator. ``simulator/`` owns the six benchmark scenarios and its committed
baseline content hash; this module only needs a *self-contained*, seed-derived panel so the
engine's determinism gate has no cross-package dependency.

Every draw comes from ``numpy.random.default_rng`` seeded with the committed seed's low 64 bits
and nothing else. No wall-clock, no OS entropy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

__all__ = ["build_panel", "build_participants", "build_manifest", "write_demo"]

_ATTRS = ("accepted_observations", "quality_adjusted_observations")


def build_panel(
    seed: bytes,
    *,
    n_cohorts: int = 24,
    n_blocks: int = 24,
    true_effect: float = 0.12,
) -> pd.DataFrame:
    """A within-cohort (switchback-shaped) panel with a KNOWN true effect on held-out RMSE."""
    rng = np.random.default_rng(int.from_bytes(seed[-8:], "big"))
    rows = []
    for c in range(n_cohorts):
        cohort_shock = float(rng.normal(0.0, 0.30))
        phase = int(rng.integers(0, 2))
        eff = true_effect * float(rng.lognormal(0.0, 0.25))
        for t in range(n_blocks):
            treated = ((t + phase) % 2) == 1
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated else "control",
                    "outcome": 1.0
                    + cohort_shock
                    - (eff if treated else 0.0)
                    + float(rng.normal(0.0, 0.04)),
                    "n_units": int(6 + rng.integers(0, 10)),
                    "n_observations": int(200 + rng.integers(0, 200)),
                }
            )
    return pd.DataFrame(rows)


def build_participants(
    seed: bytes, *, n_cohorts: int = 24, per_cohort: int = 5
) -> pd.DataFrame:
    """One row per (cohort, device signer). ``recipient_hex`` is the 32-byte ed25519 pubkey."""
    rng = np.random.default_rng(int.from_bytes(seed[-8:], "big") ^ 0xA5A5A5A5)
    rows = []
    for c in range(n_cohorts):
        for d in range(per_cohort):
            pk = bytes([(c * 251 + d * 17 + 1) % 256]) * 32
            obs = int(50 + rng.integers(0, 200))
            quality_micro = int(500_000 + rng.integers(0, 500_000))
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "recipient_hex": pk.hex(),
                    "accepted_observations": obs,
                    "quality_adjusted_observations": obs * quality_micro,
                }
            )
    return pd.DataFrame(rows)


def build_manifest(spec_example: dict) -> dict:
    """Adapt the ratified example manifest to the demo's size. Curve/budget untouched."""
    obj = json.loads(json.dumps(spec_example))
    obj["experiment_id"] = "engine-demo-001"
    obj["estimand"]["cohort_definition"]["cohort_count"] = "24"
    obj["estimand"]["time_block"]["block_count"] = "24"
    obj["analysis_plan"]["covariate_adjustment"] = []
    obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "5",
        "min_observations_per_cohort": "2000",
        "min_time_blocks": "12",
        "min_eligible_cohorts": "10",
    }
    obj["analysis_plan"]["sensitivity_analyses"] = [
        "leave_one_cohort_out",
        "placebo_time_shift",
        "wild_cluster_bootstrap",
    ]
    return obj


def write_demo(out_dir: str | Path, spec_example: dict, seed: bytes) -> dict[str, Path]:
    """Write ``manifest.json`` / ``panel.parquet`` / ``participants.parquet`` into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    manifest = build_manifest(spec_example)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    build_panel(seed).to_parquet(out / "panel.parquet", index=False)
    build_participants(seed).to_parquet(out / "participants.parquet", index=False)
    return {
        "manifest": out / "manifest.json",
        "panel": out / "panel.parquet",
        "participants": out / "participants.parquet",
    }
