"""End-to-end deterministic analysis run.

    frozen manifest + analysis panel + participant evidence + committed seed
        -> balance checks
        -> primary (pooled) cluster-robust estimate
        -> per-cohort effects
        -> sensitivity analyses (descriptive)
        -> Stage-1 conservative valuation -> Stage-2 split -> aggregate reward leaves + root
        -> analysis.json / rewards.parquet / reward_leaves.parquet / provenance.json

Determinism contract for this module (CLAUDE.md invariant 2):

* the ONLY randomness is the committed seed, consumed through
  :func:`crp_engine.sensitivity.rademacher_stream` (SHA-256 expansion, no ``numpy.random``);
* no wall-clock value reaches any artifact;
* every iteration that reaches an output is over an explicitly sorted sequence;
* BLAS threading is pinned to 1 at import time of the entrypoint, and no committed number goes
  through a BLAS reduction anyway (see :mod:`crp_engine.numeric`).
"""

from __future__ import annotations

import os

# Pinned BEFORE numpy is imported anywhere downstream: belt-and-braces, since no committed
# number goes through a BLAS reduction (crp_engine.numeric), but a stray threaded reduction in
# a future edit would then still be reproducible.
for _var in (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OMP_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
):
    os.environ.setdefault(_var, "1")

from dataclasses import dataclass  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any, Iterable, Mapping, Sequence  # noqa: E402

import pandas as pd  # noqa: E402

from crp_engine import __version__  # noqa: E402
from crp_engine import artifacts, balance as balance_mod  # noqa: E402
from crp_engine.estimators import CohortEffect, OLSResult, cohort_effects, pooled_effect  # noqa: E402
from crp_engine.manifest import Manifest  # noqa: E402
from crp_engine.panel import Panel, load_panel  # noqa: E402
from crp_engine.reference import reference_source_digest  # noqa: E402
from crp_engine.reward_compiler import (  # noqa: E402
    ParticipantRow,
    RewardCompilation,
    compile_rewards,
)
from crp_engine.sensitivity import SensitivityResult, run_sensitivity  # noqa: E402

__all__ = ["AnalysisRun", "analyze", "write_all", "load_participants"]


@dataclass(frozen=True)
class AnalysisRun:
    manifest: Manifest
    panel: Panel
    primary: OLSResult
    effects: Mapping[str, CohortEffect]
    balance: balance_mod.BalanceReport
    sensitivity: tuple[SensitivityResult, ...]
    compilation: RewardCompilation
    analysis: dict[str, Any]


def load_participants(source: str | Path | pd.DataFrame) -> list[ParticipantRow]:
    """Load the Stage-2 participant table.

    Required columns: ``cohort_id``, ``recipient_hex`` (64 lowercase hex chars = the 32-byte
    ed25519 signer pubkey). Any CRP-WS1 attribute column present is carried through:
    ``accepted_observations``, ``quality_adjusted_observations``, ``uptime_micro``,
    ``redundancy_score_micro``.
    """
    from crp_engine.manifest import CRP_WS1_ATTRIBUTES

    if isinstance(source, pd.DataFrame):
        frame = source.copy()
    else:
        p = Path(source)
        frame = (
            pd.read_parquet(p)
            if p.suffix == ".parquet"
            else pd.read_csv(p)
            if p.suffix == ".csv"
            else pd.read_json(p)
        )
    for col in ("cohort_id", "recipient_hex"):
        if col not in frame.columns:
            raise ValueError("participant table is missing required column %r" % col)
    attrs = [a for a in CRP_WS1_ATTRIBUTES if a in frame.columns]
    rows: list[ParticipantRow] = []
    frame = frame.sort_values(["cohort_id", "recipient_hex"], kind="mergesort")
    for r in frame.itertuples(index=False):
        rows.append(
            ParticipantRow(
                cohort_id=str(getattr(r, "cohort_id")),
                recipient=bytes.fromhex(str(getattr(r, "recipient_hex"))),
                attributes={a: int(getattr(r, a)) for a in attrs},
            )
        )
    return rows


def analyze(
    manifest: Manifest,
    panel_source: str | Path | pd.DataFrame,
    participants: Iterable[ParticipantRow] | str | Path | pd.DataFrame = (),
    *,
    seed: bytes = b"\x00" * 32,
    adjacency: Mapping[str, Sequence[str]] | None = None,
) -> AnalysisRun:
    """Run the full pipeline. Pure function of (manifest, panel, participants, seed, adjacency)."""
    covariates = manifest.analysis_plan.covariate_adjustment
    panel = load_panel(panel_source, manifest, covariates=covariates)

    bal = balance_mod.balance_report(
        panel.frame, covariates, balance_check=manifest.design.balance_check
    )
    primary = pooled_effect(panel, covariates=covariates)
    effects = cohort_effects(panel)
    sens = tuple(
        run_sensitivity(panel, covariates=covariates, seed=seed, adjacency=adjacency)
    )

    if isinstance(participants, (str, Path, pd.DataFrame)):
        prows: list[ParticipantRow] = load_participants(participants)
    else:
        prows = list(participants)

    compilation = compile_rewards(
        manifest, effects, panel.samples, prows, identification=panel.identification
    )
    analysis = artifacts.build_analysis(
        manifest=manifest,
        panel=panel,
        primary=primary,
        effects=effects,
        balance=bal,
        sensitivity=sens,
        compilation=compilation,
        engine_version=__version__,
        reference_digest=reference_source_digest(),
    )
    return AnalysisRun(
        manifest=manifest,
        panel=panel,
        primary=primary,
        effects=effects,
        balance=bal,
        sensitivity=sens,
        compilation=compilation,
        analysis=analysis,
    )


def write_all(run: AnalysisRun, out_dir: str | Path, *, source_commit: str = "") -> dict[str, str]:
    """Emit every artifact and return the map ``filename -> content hash`` (hashes over the
    canonical mirrors, never over parquet bytes)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _, analysis_hash = artifacts.write_analysis(run.analysis, out)
    _, rewards_hash = artifacts.write_rewards(run.compilation, out)
    _, leaves_hash = artifacts.write_leaves(run.compilation, out)

    import numpy as np
    import pyarrow as pa
    import scipy

    prov = artifacts.build_provenance(
        engine_version=__version__,
        manifest=run.manifest,
        reference_digest=reference_source_digest(),
        source_commit=source_commit,
        package_versions={
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "pyarrow": pa.__version__,
            "scipy": scipy.__version__,
        },
    )
    from crp_engine.reference import canonical_json_bytes

    (out / "provenance.json").write_bytes(canonical_json_bytes(prov))

    hashes = {
        "analysis.json": analysis_hash,
        "rewards.canonical.json": rewards_hash,
        "reward_leaves.canonical.json": leaves_hash,
        "reward_root_hex": run.compilation.reward_root_hex,
    }
    (out / "engine_hashes.json").write_bytes(
        canonical_json_bytes({"schema": "crp.engine_hashes/v1", **hashes})
    )
    return hashes
