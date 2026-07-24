"""Artifact emission: ``analysis.json``, ``rewards.parquet``, ``reward_leaves.parquet``.

Two hard rules, both from ``specs/serialization.md``:

1. **No JSON number tokens in a hashed artifact.** Every numeric value in ``analysis.json`` is a
   canonical decimal *string*, at a declared integer scale. The encoder
   (``verifier-cli/reference/canonical.py``, imported via :mod:`crp_engine.reference`) rejects
   Python ``int``/``float`` outright, so this is mechanically enforced rather than reviewed.
2. **One canonical byte sequence.** Object keys are NFC-normalized and sorted by UTF-16 code
   unit; arrays keep declared order. ``analysis_hash`` is SHA-256 over exactly those bytes — this
   is the value ``submit_evaluation`` anchors on chain.

Parquet is *convenience output*. Parquet bytes are not a stable commitment target (writer
version, statistics, row-group layout all leak in), so — exactly as the simulator does for its
content hash — every parquet table also gets a canonical-JSON mirror whose SHA-256 is the
committed number. ``rewards.parquet`` remains the audit-bundle table; ``rewards.canonical.json``
is what a verifier hashes.

Scales used in ``analysis.json``:

* ``*_s``      — the manifest's ``positive_improvement_transform.effect_scale`` (e.g. 1e-6)
* ``*_micro``  — 1e-6 fixed (SMDs, shares, p-values, ratios)
* ``*_base_units`` / counts — scale 1 (integers)
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from crp_engine import numeric as nm
from crp_engine.balance import BalanceReport
from crp_engine.estimators import CohortEffect, OLSResult
from crp_engine.manifest import Manifest
from crp_engine.panel import Panel
from crp_engine.reference import canonical_json_bytes, sha256_hex
from crp_engine.reward_compiler import RewardCompilation
from crp_engine.sensitivity import SensitivityResult

__all__ = [
    "ANALYSIS_SCHEMA",
    "REWARDS_SCHEMA",
    "LEAVES_SCHEMA",
    "build_analysis",
    "write_analysis",
    "write_rewards",
    "write_leaves",
    "build_provenance",
]

ANALYSIS_SCHEMA = "crp.analysis/v1"
REWARDS_SCHEMA = "crp.rewards/v1"
LEAVES_SCHEMA = "crp.reward_leaves/v1"

_MICRO = -6


def _i(v: int) -> str:
    """Canonical integer string (``serialization.md`` §2.1)."""
    return str(int(v))


def _b(v: bool) -> str:
    return "true" if v else "false"


def _micro(v: float) -> str:
    """Quantize a diagnostic float to 1e-6 and render it canonically. Non-finite -> sentinel."""
    if not math.isfinite(v):
        return "null" if math.isnan(v) else ("+inf" if v > 0 else "-inf")
    return _i(nm.quantize(v, _MICRO))


def _scaled(v: float, scale: int) -> str:
    return _i(nm.quantize(v, scale))


def _jsonify(value: Any, scale: int) -> Any:
    """Recursively render a diagnostic payload into number-free canonical JSON values."""
    if isinstance(value, bool):
        return _b(value)
    if isinstance(value, int):
        return _i(value)
    if isinstance(value, float):
        return _micro(value)
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return {str(k): _jsonify(v, scale) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_jsonify(v, scale) for v in value]
    if value is None:
        return None
    return str(value)


# --------------------------------------------------------------------------------------
# analysis.json
# --------------------------------------------------------------------------------------

def build_analysis(
    *,
    manifest: Manifest,
    panel: Panel,
    primary: OLSResult,
    effects: Mapping[str, CohortEffect],
    balance: BalanceReport,
    sensitivity: Sequence[SensitivityResult],
    compilation: RewardCompilation,
    engine_version: str,
    reference_digest: str,
) -> dict[str, Any]:
    """Assemble the ``analysis.json`` object. Pure function of its inputs — no wall-clock."""
    scale = manifest.reward_policy.effect_scale
    plan = manifest.analysis_plan
    b_eff, b_se = primary.get("treated")
    improvement_sign = -1 if manifest.improvement_direction == "decrease" else 1
    primary_improvement_s = improvement_sign * nm.quantize(b_eff, scale)
    primary_margin_s = nm.round_half_even_div(
        plan.critical_value_micro * nm.quantize(b_se, scale), 1_000_000
    )

    s1 = compilation.stage1
    val_by_id = {v.cohort_id: v for v in s1.cohorts}

    cohorts_out = []
    for cid in panel.cohort_ids:
        v = val_by_id[cid]
        s = panel.samples[cid]
        e = effects.get(cid)
        cohorts_out.append(
            {
                "cohort_id": cid,
                "effect_s": _i(v.effect_s),
                "standard_error_s": _i(v.se_s),
                "improvement_s": _i(v.improvement_s),
                "margin_s": _i(v.margin_s),
                "conservative_effect_s": _i(v.conservative_s),
                "allocation_base_units": _i(v.alloc_base_units),
                "budget_base_units": _i(v.budget_base_units),
                "identified": _b(v.identified),
                "identification_mode": (e.mode if e else "none"),
                "meets_minimum_sample": _b(v.min_sample_eligible),
                "exclusion_reasons": list(v.reasons),
                "n_time_blocks": _i(s.n_time_blocks),
                "n_treated_blocks": _i(s.n_treated_blocks),
                "n_control_blocks": _i(s.n_control_blocks),
                "n_observations": _i(s.n_observations),
                "min_units_in_any_block": _i(s.n_units_min),
                "n_clusters": _i(e.n_clusters if e else 0),
                "note": (e.note if e else ""),
            }
        )

    obj: dict[str, Any] = {
        "schema": ANALYSIS_SCHEMA,
        "spec_version": manifest.spec_version,
        "experiment_id": manifest.experiment_id,
        "manifest_hash": manifest.manifest_hash,
        "engine": {
            "name": "crp-causal-engine",
            "version": engine_version,
            "analysis_container_digest": plan.analysis_container_digest,
            "reference_source_digest": reference_digest,
        },
        "estimand": {
            "unit_type": manifest.unit_type,
            "primary_outcome_metric_id": manifest.primary_outcome_id,
            "improvement_direction": manifest.improvement_direction,
            "effect_scale": _i(manifest.reward_policy.effect_scale),
            "statement": (
                "Average effect of INCLUDING a geo-cohort's data on out-of-sample prediction "
                "error, at the geo-cohort x time-block level, with cluster-robust standard "
                "errors. No individual-device counterfactual is claimed (Invariant 4)."
            ),
        },
        "design": {
            "template": manifest.design.template,
            "assignment_method": manifest.design.assignment_method,
            "treated_fraction_micro": _i(manifest.design.treated_fraction_micro),
            "interference_assumption": manifest.design.interference_assumption,
            "carryover_blocks": _i(manifest.design.carryover_blocks),
            "washout_blocks": _i(manifest.design.washout_blocks),
            "eligible_for_strong_causal_claim": _b(
                manifest.design.eligible_for_strong_causal_claim
            ),
            "missingness_policy": manifest.design.missingness_policy,
        },
        "analysis_plan": {
            "estimator": plan.estimator,
            "standard_error_method": plan.standard_error_method,
            "test_sidedness": plan.test_sidedness,
            "confidence_level_micro": _i(plan.confidence_level_micro),
            "critical_value_micro": _i(plan.critical_value_micro),
            "critical_value_reference": plan.critical_value_reference or "",
            "df_frozen": _i(plan.df) if plan.df is not None else "",
            "minimum_sample": {
                "min_units_per_cohort": _i(plan.minimum_sample.min_units_per_cohort),
                "min_observations_per_cohort": _i(plan.minimum_sample.min_observations_per_cohort),
                "min_time_blocks": _i(plan.minimum_sample.min_time_blocks),
                "min_eligible_cohorts": _i(plan.minimum_sample.min_eligible_cohorts),
            },
        },
        "identification": {
            "per_cohort_mode": panel.identification.value,
            "supports_strong_causal_claim": _b(
                manifest.design.eligible_for_strong_causal_claim
                and panel.identification.value == "within_cohort"
            ),
            "assumptions": list(panel.identification_assumptions),
            "caveat": (
                "The chain verifies process, not truth: on-chain checks bind commitments and "
                "settlement only. The causal claim is only as good as this design, these data "
                "and these assumptions."
            ),
        },
        "primary_estimate": {
            "term": "treated",
            "effect_s": _scaled(b_eff, scale),
            "standard_error_s": _scaled(b_se, scale),
            "improvement_s": _i(primary_improvement_s),
            "margin_s": _i(primary_margin_s),
            "conservative_improvement_s": _i(max(0, primary_improvement_s - primary_margin_s)),
            "n_units": _i(primary.n_obs),
            "n_clusters": _i(primary.n_clusters),
            "n_parameters": _i(primary.n_params),
            "n_absorbed_fe_groups": _i(primary.n_absorbed_groups),
            "cluster_robust_df": _i(primary.n_clusters - 1),
            "finite_sample_correction_micro": _micro(primary.finite_sample_correction),
            "residual_sd_s": _scaled(primary.residual_sd, scale),
            "se_method": (
                "CR1 sandwich, c = G/(G-1) * (N-1)/(N-K) (Cameron & Miller 2015 eq. 12); "
                "fixed effects absorbed by within-demeaning so K counts only within-varying "
                "regressors (their section III.B: the LSDV dummy count is the wrong correction)"
            ),
        },
        "balance": {
            "threshold_micro": _i(balance.threshold_micro),
            "passed": _b(balance.passed),
            "max_abs_smd_micro": _micro(balance.max_abs_smd),
            "treated_share_micro": _i(balance.arm_share_treated_micro),
            "gates_payout": "false",
            "covariates": [
                {
                    "name": it.name,
                    "mean_treated_micro": _micro(it.mean_treated),
                    "mean_control_micro": _micro(it.mean_control),
                    "smd_micro": _micro(it.smd),
                    "n_treated": _i(it.n_treated),
                    "n_control": _i(it.n_control),
                    "passed": _b(it.passed),
                }
                for it in balance.items
            ],
        },
        "sensitivity": [
            {
                "name": r.name,
                "kind": r.kind,
                "status": r.status,
                "note": r.note,
                "values": _jsonify(dict(r.values), scale),
            }
            for r in sensitivity
        ],
        "cohorts": cohorts_out,
        "excluded_records": {
            "total": _i(sum(panel.excluded.values())),
            "by_reason": [
                {"reason": k, "count": _i(v)} for k, v in sorted(panel.excluded.items())
            ],
        },
        "reward_summary": {
            "budget_base_units": _i(s1.budget_base_units),
            "total_allocation_before_cap_base_units": _i(s1.total_alloc_before_cap),
            "total_cohort_budget_base_units": _i(s1.total_budget_allocated),
            "total_leaf_base_units": _i(compilation.total_leaf_base_units),
            "recoverable_base_units": _i(
                s1.budget_base_units - compilation.total_leaf_base_units
            ),
            "scaled_to_budget": _b(s1.scaled_to_budget),
            "leaf_count": _i(compilation.leaf_count),
            "dropped_zero_sum_recipients": _i(len(compilation.dropped_zero_sum_recipients)),
            "reward_root_hex": compilation.reward_root_hex,
            "null_distribution": _b(s1.null_distribution),
            "null_reasons": list(s1.null_reasons),
            "n_eligible_cohorts": _i(s1.n_eligible_cohorts),
            "leaf_set_shape": "aggregate_one_leaf_per_recipient",
        },
    }
    return obj


def write_analysis(obj: Mapping[str, Any], out_dir: str | Path) -> tuple[Path, str]:
    """Write ``analysis.json`` in canonical bytes; return ``(path, "sha256:<hex>")``."""
    data = canonical_json_bytes(obj)
    path = Path(out_dir) / "analysis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path, "sha256:" + sha256_hex(data)


# --------------------------------------------------------------------------------------
# rewards.parquet / reward_leaves.parquet
# --------------------------------------------------------------------------------------

_REWARDS_FIELDS = pa.schema(
    [
        pa.field("cohort_id", pa.string(), nullable=False),
        pa.field("recipient_hex", pa.string(), nullable=False),
        pa.field("weight", pa.uint64(), nullable=False),
        pa.field("cohort_weight_total", pa.uint64(), nullable=False),
        pa.field("cohort_budget_base_units", pa.uint64(), nullable=False),
        pa.field("amount_base_units", pa.uint64(), nullable=False),
        pa.field("recipient_aggregate_base_units", pa.uint64(), nullable=False),
        pa.field("leaf_index", pa.uint64(), nullable=True),
        pa.field("included_in_leaf_set", pa.bool_(), nullable=False),
    ]
)

_LEAVES_FIELDS = pa.schema(
    [
        pa.field("leaf_index", pa.uint64(), nullable=False),
        pa.field("recipient_hex", pa.string(), nullable=False),
        pa.field("amount_base_units", pa.uint64(), nullable=False),
        pa.field("leaf_hash_hex", pa.string(), nullable=False),
    ]
)

_PARQUET_KW = dict(compression="none", version="2.6", write_statistics=False)


def _rewards_rows(compilation: RewardCompilation) -> list[dict[str, Any]]:
    agg: dict[bytes, int] = {}
    for r in compilation.split_rows:
        agg[r.recipient] = agg.get(r.recipient, 0) + r.amount_base_units
    index_of = {lf.recipient: lf.leaf_index for lf in compilation.leaves}
    rows = []
    for r in sorted(compilation.split_rows, key=lambda r: (r.cohort_id, r.recipient)):
        rows.append(
            {
                "cohort_id": r.cohort_id,
                "recipient_hex": r.recipient.hex(),
                "weight": r.weight,
                "cohort_weight_total": r.cohort_weight_total,
                "cohort_budget_base_units": r.cohort_budget_base_units,
                "amount_base_units": r.amount_base_units,
                "recipient_aggregate_base_units": agg.get(r.recipient, 0),
                "leaf_index": index_of.get(r.recipient),
                "included_in_leaf_set": r.recipient in index_of,
            }
        )
    return rows


def write_rewards(compilation: RewardCompilation, out_dir: str | Path) -> tuple[Path, str]:
    """Write the per-(cohort, recipient) Stage-2 detail table + its canonical-JSON mirror."""
    rows = _rewards_rows(compilation)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pylist(rows, schema=_REWARDS_FIELDS)
    pq.write_table(table, out / "rewards.parquet", **_PARQUET_KW)

    mirror = {
        "schema": REWARDS_SCHEMA,
        "rows": [
            {
                "cohort_id": r["cohort_id"],
                "recipient_hex": r["recipient_hex"],
                "weight": _i(r["weight"]),
                "cohort_weight_total": _i(r["cohort_weight_total"]),
                "cohort_budget_base_units": _i(r["cohort_budget_base_units"]),
                "amount_base_units": _i(r["amount_base_units"]),
                "recipient_aggregate_base_units": _i(r["recipient_aggregate_base_units"]),
                "leaf_index": _i(r["leaf_index"]) if r["leaf_index"] is not None else "",
                "included_in_leaf_set": _b(r["included_in_leaf_set"]),
            }
            for r in rows
        ],
    }
    data = canonical_json_bytes(mirror)
    (out / "rewards.canonical.json").write_bytes(data)
    return out / "rewards.parquet", "sha256:" + sha256_hex(data)


def write_leaves(compilation: RewardCompilation, out_dir: str | Path) -> tuple[Path, str]:
    """Write the RATIFIED aggregate leaf set (one row per on-chain reward leaf)."""
    from crp_engine.reward_compiler import leaf_hash_hex

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "leaf_index": lf.leaf_index,
            "recipient_hex": lf.recipient.hex(),
            "amount_base_units": lf.amount_base_units,
            "leaf_hash_hex": leaf_hash_hex(lf),
        }
        for lf in compilation.leaves
    ]
    table = pa.Table.from_pylist(rows, schema=_LEAVES_FIELDS)
    pq.write_table(table, out / "reward_leaves.parquet", **_PARQUET_KW)
    mirror = {
        "schema": LEAVES_SCHEMA,
        "reward_root_hex": compilation.reward_root_hex,
        "leaf_set_shape": "aggregate_one_leaf_per_recipient",
        "leaves": [
            {
                "leaf_index": _i(r["leaf_index"]),
                "recipient_hex": r["recipient_hex"],
                "amount_base_units": _i(r["amount_base_units"]),
                "leaf_hash_hex": r["leaf_hash_hex"],
            }
            for r in rows
        ],
    }
    data = canonical_json_bytes(mirror)
    (out / "reward_leaves.canonical.json").write_bytes(data)
    return out / "reward_leaves.parquet", "sha256:" + sha256_hex(data)


@dataclass(frozen=True)
class Provenance:
    obj: dict[str, Any]


def build_provenance(
    *,
    engine_version: str,
    manifest: Manifest,
    reference_digest: str,
    source_commit: str = "",
    package_versions: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Environment provenance. Deliberately EXCLUDED from every committed hash.

    ``provenance.json`` records *how* the artifact was produced (versions, digests, commit); the
    committed hashes cover only scientific content, so the same content reproduces the same hash
    across environments. Cross-environment byte-stability is guaranteed by the pinned container
    digest, not by this file. Note there is no execution timestamp here — a wall-clock field in a
    reproduced artifact would defeat the point (``backend-data-engineer`` owns the bundle-level
    ``provenance.json`` and may add non-hashed fields there).
    """
    return {
        "schema": "crp.engine_provenance/v1",
        "engine_name": "crp-causal-engine",
        "engine_version": engine_version,
        "source_commit": source_commit,
        "analysis_container_digest": manifest.analysis_plan.analysis_container_digest,
        "reference_source_digest": reference_digest,
        "packages": dict(sorted((package_versions or {}).items())),
    }
