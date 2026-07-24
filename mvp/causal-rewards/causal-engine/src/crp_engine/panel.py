"""The analysis panel: one row per (cohort_id, time_block) — the frozen experimental unit.

Invariant 4 is structural here. A panel row is a **geo-cohort within a time block**. There is no
device-level row anywhere in the estimation path; device-level data enters only at Stage 2 of the
reward compiler, where it splits an already-decided cohort amount.

Responsibilities:

* load / validate the panel,
* apply the **frozen missingness policy** before any estimate is computed,
* apply the switchback **washout** discard (``serialization.md`` §7.4 defers this to analysis),
* evaluate the frozen **minimum-sample rule** per cohort,
* determine, from the frozen design *and the observed assignment pattern*, which per-cohort
  identification mode is available — and say plainly when none is.

Every exclusion is counted and reported in ``analysis.json`` (``excluded_records``). Nothing is
dropped silently.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from crp_engine.manifest import Manifest

__all__ = [
    "REQUIRED_COLUMNS",
    "IdentificationMode",
    "CohortSample",
    "Panel",
    "load_panel",
]

#: Minimum panel contract. Extra columns are treated as covariates when named in
#: ``analysis_plan.covariate_adjustment``.
REQUIRED_COLUMNS: tuple[str, ...] = (
    "cohort_id",       # str  — the geo-cohort id (composite "group|index" for switchback/matched)
    "time_block",      # int  — 0-based time-block index
    "arm",             # str  — "treatment" | "control"
    "outcome",         # float — the primary outcome for this cohort x block (raw metric)
    "n_units",         # int  — devices contributing to this cohort x block
    "n_observations",  # int  — accepted, signature-verified observations in this cohort x block
)


class IdentificationMode(str, Enum):
    """How a **per-cohort** effect is identified. The pooled ATE is always identified."""

    #: The cohort's arm varies across its own time blocks (per-block randomization or
    #: switchback). The per-cohort contrast is a within-cohort comparison — the strongest case.
    WITHIN_COHORT = "within_cohort"
    #: matched_cluster: the cohort is contrasted against the opposite-arm members of its own
    #: frozen matched stratum, block by block.
    MATCHED_STRATUM = "matched_stratum"
    #: The cohort's arm is constant for the whole experiment (whole-cohort cluster
    #: randomization). The per-cohort contrast is against the randomized control POOL and rests
    #: on an additional exchangeability assumption. Disclosed, never hidden.
    BETWEEN_COHORT_VS_CONTROL_POOL = "between_cohort_vs_control_pool"
    #: No credible per-cohort contrast exists (e.g. every cohort is treated, or the design is
    #: observational replay). All per-cohort conservative effects are forced to 0.
    NOT_IDENTIFIED = "not_identified"


@dataclass(frozen=True)
class CohortSample:
    """Frozen minimum-sample evaluation for one cohort (``reward-policy.md`` Stage 1 step 4)."""

    cohort_id: str
    n_units_min: int
    n_observations: int
    n_time_blocks: int
    n_treated_blocks: int
    n_control_blocks: int
    eligible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Panel:
    frame: pd.DataFrame
    manifest: Manifest
    identification: IdentificationMode
    identification_assumptions: tuple[str, ...]
    samples: Mapping[str, CohortSample]
    excluded: Mapping[str, int]
    strata: Mapping[str, tuple[str, ...]]  # stratum/group id -> member cohort ids (sorted)

    @property
    def cohort_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self.samples.keys()))

    @property
    def eligible_cohort_ids(self) -> tuple[str, ...]:
        return tuple(cid for cid in self.cohort_ids if self.samples[cid].eligible)

    def rows(self, cohort_id: str) -> pd.DataFrame:
        return self.frame[self.frame["cohort_id"] == cohort_id]


# --------------------------------------------------------------------------------------


def _read_any(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix == ".parquet":
        return pd.read_parquet(p)
    if p.suffix == ".csv":
        return pd.read_csv(p)
    if p.suffix in (".json", ".jsonl"):
        return pd.read_json(p, lines=p.suffix == ".jsonl")
    raise ValueError("unsupported panel format: %s" % p.suffix)


def _group_of(cohort_id: str) -> str:
    """Composite-id group (``serialization.md`` §7.4). Non-composite ids are their own group."""
    if cohort_id.count("|") == 1:
        return cohort_id.split("|", 1)[0]
    return cohort_id


def _apply_washout(frame: pd.DataFrame, washout_blocks: int) -> tuple[pd.DataFrame, int]:
    """Discard the first ``washout_blocks`` blocks after each arm switch, within a GEO GROUP.

    ``serialization.md`` §7.4 pins ``carryover_blocks`` / ``washout_blocks`` in the manifest but
    routes them to ANALYSIS time. Under Bojinov-Simchi-Levi-Zhao Assumption 2 (m-carryover), the
    potential outcome at t depends only on ``w_{t-m:t}``; restricting the analysis set to blocks
    whose preceding ``m`` blocks carried the SAME arm therefore removes carryover contamination
    by construction. ``washout_blocks >= carryover_blocks`` is enforced at manifest load.

    The switch is detected **per geo group**, not per composite ``cohort_id``: under the
    §7.4 switchback grammar a composite id is ``geo|period`` and the arm is constant *within* a
    period, so the flip happens between two consecutive composite ids of the same geo. Carryover
    is a physical property of the geo, so the geo group is the right sequence to walk.

    The first blocks of a geo group are NOT discarded — at the start of the experiment there is
    no prior treatment to carry over.
    """
    if washout_blocks <= 0:
        return frame, 0
    # Deterministic: explicit sort by (group, time_block); no reliance on groupby iteration order.
    ordered = frame.assign(_grp=[_group_of(c) for c in frame["cohort_id"]]).sort_values(
        ["_grp", "time_block"], kind="mergesort"
    )
    groups = ordered["_grp"].to_numpy()
    arms = ordered["arm"].to_numpy()
    drop_labels: list[object] = []
    since_switch = washout_blocks
    for i, label in enumerate(ordered.index.to_numpy()):
        if i == 0 or groups[i] != groups[i - 1]:
            since_switch = washout_blocks  # new geo: nothing precedes it
        elif arms[i] != arms[i - 1]:
            since_switch = 0
        if since_switch < washout_blocks:
            drop_labels.append(label)
        since_switch += 1
    if not drop_labels:
        return frame, 0
    return frame.drop(index=drop_labels), len(drop_labels)


def load_panel(
    source: str | Path | pd.DataFrame,
    manifest: Manifest,
    *,
    covariates: Sequence[str] = (),
) -> Panel:
    """Load, clean and classify the analysis panel under the frozen manifest."""
    frame = source.copy() if isinstance(source, pd.DataFrame) else _read_any(source)

    missing_cols = [c for c in REQUIRED_COLUMNS if c not in frame.columns]
    if missing_cols:
        raise ValueError("panel is missing required columns: %s" % missing_cols)

    frame = frame.reset_index(drop=True)
    frame["cohort_id"] = frame["cohort_id"].astype(str)
    frame["arm"] = frame["arm"].astype(str)
    frame["time_block"] = frame["time_block"].astype("int64")
    frame["outcome"] = frame["outcome"].astype("float64")
    frame["n_units"] = frame["n_units"].astype("int64")
    frame["n_observations"] = frame["n_observations"].astype("int64")

    bad_arm = ~frame["arm"].isin(["treatment", "control"])
    if bool(bad_arm.any()):
        raise ValueError(
            "panel arm must be 'treatment' or 'control'; saw %s"
            % sorted(set(frame.loc[bad_arm, "arm"]))
        )
    dup = frame.duplicated(subset=["cohort_id", "time_block"])
    if bool(dup.any()):
        raise ValueError("panel has duplicate (cohort_id, time_block) rows")

    excluded: dict[str, int] = {}

    # ---- frozen missingness policy (applied BEFORE any estimate) -------------------------
    cov_cols = [c for c in covariates if c in frame.columns]
    na_mask = frame["outcome"].isna()
    for c in cov_cols:
        na_mask = na_mask | frame[c].isna()
    n_missing = int(na_mask.sum())
    if n_missing:
        if manifest.design.missingness_policy == "ineligible":
            frame = frame.loc[~na_mask]
            excluded["missing_data_ineligible"] = n_missing
        else:  # impute_cohort_mean — frozen alternative, deterministic cohort-mean fill
            for col in ["outcome", *cov_cols]:
                fill = frame.groupby("cohort_id", sort=True)[col].transform("mean")
                frame[col] = frame[col].fillna(fill)
            still = frame["outcome"].isna()
            if bool(still.any()):
                excluded["missing_data_unimputable"] = int(still.sum())
                frame = frame.loc[~still]
            excluded["missing_data_imputed"] = n_missing

    # ---- switchback washout --------------------------------------------------------------
    if manifest.design.template == "switchback" and manifest.design.washout_blocks > 0:
        frame, dropped = _apply_washout(frame, manifest.design.washout_blocks)
        if dropped:
            excluded["switchback_washout"] = dropped

    # ---- optional caller-supplied eligibility flag (guard bands / carryover from upstream)
    if "eligible" in frame.columns:
        flag = frame["eligible"].astype(bool)
        n_drop = int((~flag).sum())
        if n_drop:
            excluded["upstream_ineligible"] = n_drop
        frame = frame.loc[flag]

    frame = frame.sort_values(["cohort_id", "time_block"], kind="mergesort").reset_index(drop=True)
    if frame.empty:
        raise ValueError("panel is empty after applying the frozen exclusion policies")

    # ---- minimum-sample rule --------------------------------------------------------------
    ms = manifest.analysis_plan.minimum_sample
    samples: dict[str, CohortSample] = {}
    for cid, grp in sorted(frame.groupby("cohort_id", sort=True), key=lambda kv: kv[0]):
        n_units_min = int(grp["n_units"].min())
        n_obs = int(grp["n_observations"].sum())
        n_blocks = int(grp["time_block"].nunique())
        n_treat = int((grp["arm"] == "treatment").sum())
        n_ctrl = int((grp["arm"] == "control").sum())
        reasons: list[str] = []
        if n_units_min < ms.min_units_per_cohort:
            reasons.append("below_min_units_per_cohort")
        if n_obs < ms.min_observations_per_cohort:
            reasons.append("below_min_observations_per_cohort")
        if n_blocks < ms.min_time_blocks:
            reasons.append("below_min_time_blocks")
        samples[cid] = CohortSample(
            cohort_id=cid,
            n_units_min=n_units_min,
            n_observations=n_obs,
            n_time_blocks=n_blocks,
            n_treated_blocks=n_treat,
            n_control_blocks=n_ctrl,
            eligible=not reasons,
            reasons=tuple(reasons),
        )

    strata: dict[str, list[str]] = {}
    for cid in sorted(samples):
        strata.setdefault(_group_of(cid), []).append(cid)

    mode, assumptions = _classify(manifest, samples, strata)

    return Panel(
        frame=frame,
        manifest=manifest,
        identification=mode,
        identification_assumptions=assumptions,
        samples=samples,
        excluded=dict(sorted(excluded.items())),
        strata={g: tuple(v) for g, v in sorted(strata.items())},
    )


def _classify(
    manifest: Manifest,
    samples: Mapping[str, CohortSample],
    strata: Mapping[str, Iterable[str]],
) -> tuple[IdentificationMode, tuple[str, ...]]:
    """Pick the per-cohort identification mode from the frozen design + observed arm pattern.

    Deterministic and data-derived; never a human choice made after seeing outcomes.
    """
    if manifest.design.template == "observational_replay":
        return (
            IdentificationMode.NOT_IDENTIFIED,
            (
                "design.template=observational_replay: inclusion was not randomized, so no "
                "credible counterfactual exists. Discovery/planning output only; "
                "eligible_for_strong_causal_claim is false and the reward compiler pays nothing.",
            ),
        )

    n_with_both = sum(
        1 for s in samples.values() if s.n_treated_blocks > 0 and s.n_control_blocks > 0
    )
    if n_with_both == len(samples) and len(samples) > 0:
        return (
            IdentificationMode.WITHIN_COHORT,
            (
                "Per-cohort effects are within-cohort contrasts (the cohort's own treated blocks "
                "vs its own control blocks), so cohort-level confounders that are constant in "
                "time difference out. Requires no cross-cohort exchangeability assumption.",
                "Assumes the frozen interference_assumption holds: %s."
                % manifest.design.interference_assumption,
            ),
        )

    if manifest.design.template == "matched_cluster" and any(
        len(tuple(members)) > 1 for members in strata.values()
    ):
        return (
            IdentificationMode.MATCHED_STRATUM,
            (
                "Per-cohort effects contrast a member against the opposite-arm members of its own "
                "frozen matched stratum, block by block. Validity rests on the QUALITY of the "
                "frozen matching (baseline comparability within a stratum), which is a design "
                "property, not an estimation property — see docs/modeling-notes.md.",
                "Assumes the frozen interference_assumption holds: %s."
                % manifest.design.interference_assumption,
            ),
        )

    n_treated_cohorts = sum(1 for s in samples.values() if s.n_treated_blocks > 0)
    n_control_cohorts = sum(1 for s in samples.values() if s.n_control_blocks > 0)
    if n_treated_cohorts > 0 and n_control_cohorts > 0:
        return (
            IdentificationMode.BETWEEN_COHORT_VS_CONTROL_POOL,
            (
                "Each cohort's arm is constant for the whole experiment, so NO within-cohort "
                "contrast exists. A per-cohort effect is only identified against the randomized "
                "CONTROL POOL, which additionally assumes cohort baselines are exchangeable "
                "(a treated cohort's counterfactual mean equals the control-pool mean in "
                "expectation). This assumption is untestable and is NOT required by the pooled "
                "ATE, which remains fully randomization-justified.",
                "The per-cohort standard error therefore carries the full BETWEEN-cohort "
                "variance and is deliberately conservative; most cohorts are expected to have a "
                "conservative lower bound of 0 unless the network is large or the effect strong.",
            ),
        )

    return (
        IdentificationMode.NOT_IDENTIFIED,
        ("No control units are present in the panel; no contrast exists.",),
    )
