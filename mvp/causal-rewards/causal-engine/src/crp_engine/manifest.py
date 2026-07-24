"""Frozen-manifest model + the cross-field checks the causal engine is responsible for.

`specs/manifest.schema.json` (owned by ``protocol-architect``) is normative for *shape*. This
module parses a schema-valid manifest into typed Python and enforces the semantic guards that
`specs/serialization.md` §7.4 and `specs/reward-policy.md` explicitly delegate to the engine:

* switchback ⇒ ``treated_fraction_micro == "500000"`` (the alternation is structurally 50/50),
* switchback ⇒ ``washout_blocks >= carryover_blocks``,
* reward curve: first breakpoint ``[0, 0]``, strictly increasing in x, non-decreasing in y,
* ``reward_curve_hash`` matches SHA-256 over the canonical bytes of ``reward_curve``,
* ``critical_value_reference == "student_t"`` ⇒ ``df`` present,
* CRP-WS1 ``weight_formula`` parses against the closed attribute vocabulary.

Nothing here can change after freeze; the engine only ever *reads* a manifest.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from crp_engine.reference import canonical_json_bytes, sha256_hex

__all__ = [
    "CRP_WS1_ATTRIBUTES",
    "MinimumSample",
    "RewardPolicy",
    "AnalysisPlan",
    "Design",
    "Manifest",
    "ManifestError",
    "parse_weight_formula",
]


class ManifestError(ValueError):
    """A frozen manifest violated a semantic guard the engine is responsible for."""


#: Closed CRP-WS1 attribute vocabulary v1 (``reward-policy.md``). Extending it is a versioned
#: migration (CRP-WS2), never a silent edit.
CRP_WS1_ATTRIBUTES: tuple[str, ...] = (
    "accepted_observations",
    "quality_adjusted_observations",
    "uptime_micro",
    "redundancy_score_micro",
)

_UINT_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_INT_RE = re.compile(r"^(0|-?[1-9][0-9]*)$")
_TERM_RE = re.compile(r"^(0|[1-9][0-9]*)\*([a-z][a-z0-9_]*)$")


def _uint(obj: Mapping[str, Any], key: str) -> int:
    v = obj[key]
    if not isinstance(v, str) or not _UINT_RE.match(v):
        raise ManifestError("%s must be a canonical unsigned integer string, got %r" % (key, v))
    return int(v)


def _sint(obj: Mapping[str, Any], key: str) -> int:
    v = obj[key]
    if not isinstance(v, str) or not _INT_RE.match(v):
        raise ManifestError("%s must be a canonical signed integer string, got %r" % (key, v))
    return int(v)


def parse_weight_formula(formula: str) -> list[tuple[int, str]]:
    """Parse a CRP-WS1 ``weight_formula`` into ``[(coef, attribute), ...]``.

    Grammar (``reward-policy.md``): ``term (" + " term)*`` with ``term := coef "*" attribute``.
    Terms are joined by EXACTLY ``" + "``. No division, no subtraction, no exponent, no product
    of two attributes. An attribute may appear at most once.
    """
    if not isinstance(formula, str) or formula == "":
        raise ManifestError("weight_formula must be a non-empty string")
    terms = formula.split(" + ")
    out: list[tuple[int, str]] = []
    seen: set[str] = set()
    for term in terms:
        m = _TERM_RE.match(term)
        if not m:
            raise ManifestError(
                "weight_formula term %r is not CRP-WS1 'coef*attribute' form" % (term,)
            )
        coef_s, attr = m.group(1), m.group(2)
        if attr not in CRP_WS1_ATTRIBUTES:
            raise ManifestError(
                "weight_formula attribute %r is outside the closed CRP-WS1 v1 vocabulary %s"
                % (attr, list(CRP_WS1_ATTRIBUTES))
            )
        if attr in seen:
            raise ManifestError("weight_formula repeats attribute %r" % (attr,))
        seen.add(attr)
        out.append((int(coef_s), attr))
    return out


@dataclass(frozen=True)
class MinimumSample:
    """Frozen minimum-sample rule (``reward-policy.md`` Stage 1 step 4, Invariant 3)."""

    min_units_per_cohort: int
    min_observations_per_cohort: int
    min_time_blocks: int
    min_eligible_cohorts: int


@dataclass(frozen=True)
class AnalysisPlan:
    estimator: str
    standard_error_method: str
    test_sidedness: str
    confidence_level_micro: int
    critical_value_micro: int
    critical_value_reference: str | None
    df: int | None
    covariate_adjustment: tuple[str, ...]
    minimum_sample: MinimumSample
    sensitivity_analyses: tuple[str, ...]
    analysis_container_digest: str


@dataclass(frozen=True)
class RewardPolicy:
    budget_base_units: int
    mint: str
    transform_type: str
    effect_scale: int
    breakpoints: tuple[tuple[int, int], ...]
    reward_curve_hash: str
    split_rule: str
    weight_formula: str
    weight_terms: tuple[tuple[int, str], ...]
    weight_scale: int
    overflow_policy: str
    unused_budget_policy: str


@dataclass(frozen=True)
class Design:
    template: str
    eligible_for_strong_causal_claim: bool
    assignment_method: str
    treated_fraction_micro: int
    interference_assumption: str
    carryover_blocks: int
    washout_blocks: int
    #: OPTIONAL, not yet a frozen schema field. See docs/modeling-notes.md and the spec-change
    #: proposal in the M3 report. Absent -> unrestricted within-geo clustering (most general).
    hac_bandwidth_blocks: int | None
    #: OPTIONAL, not yet a frozen schema field. Default "ineligible" (strictest).
    missingness_policy: str
    balance_check: str | None
    raw_parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Manifest:
    experiment_id: str
    spec_version: str
    manifest_version: str
    primary_outcome_id: str
    improvement_direction: str
    unit_type: str
    cohort_count: int
    block_count: int
    design: Design
    analysis_plan: AnalysisPlan
    reward_policy: RewardPolicy
    manifest_hash: str
    raw: Mapping[str, Any]

    # -------------------------------------------------------------- loading
    @staticmethod
    def from_path(path: str | Path) -> "Manifest":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return Manifest.from_obj(raw)

    @staticmethod
    def from_obj(raw: Mapping[str, Any]) -> "Manifest":
        try:
            return _build(raw)
        except KeyError as exc:  # missing required field
            raise ManifestError("manifest is missing required field %s" % exc) from exc


def _build(raw: Mapping[str, Any]) -> Manifest:
    est = raw["estimand"]
    if est["unit_type"] != "geo_cohort_time_block":
        raise ManifestError(
            "Invariant 4: unit_type must be 'geo_cohort_time_block', got %r" % est["unit_type"]
        )

    d = raw["design"]
    t = raw["treatment"]
    params: Mapping[str, Any] = d.get("parameters", {}) or {}
    template = d["template"]
    treated_fraction_micro = _uint(t, "treated_fraction_micro")

    carryover = int(params["carryover_blocks"]) if "carryover_blocks" in params else 0
    washout = int(params["washout_blocks"]) if "washout_blocks" in params else 0

    if template == "switchback":
        # serialization.md §7.4: the alternation is structurally 50/50; the engine enforces the
        # manifest value (the byte derivation deliberately does NOT read it).
        if treated_fraction_micro != 500000:
            raise ManifestError(
                "switchback requires treated_fraction_micro == '500000', got %r"
                % t["treated_fraction_micro"]
            )
        if "carryover_blocks" not in params or "washout_blocks" not in params:
            raise ManifestError("switchback requires carryover_blocks and washout_blocks")
        if washout < carryover:
            raise ManifestError(
                "washout_blocks (%d) must be >= carryover_blocks (%d)" % (washout, carryover)
            )
    if template == "observational_replay" and d.get("eligible_for_strong_causal_claim", False):
        raise ManifestError(
            "observational_replay must have eligible_for_strong_causal_claim = false"
        )

    hac_bw = params.get("hac_bandwidth_blocks")
    design = Design(
        template=template,
        eligible_for_strong_causal_claim=bool(d["eligible_for_strong_causal_claim"]),
        assignment_method=t["assignment_method"],
        treated_fraction_micro=treated_fraction_micro,
        interference_assumption=params.get("interference_assumption", "no_interference"),
        carryover_blocks=carryover,
        washout_blocks=washout,
        hac_bandwidth_blocks=int(hac_bw) if hac_bw is not None else None,
        missingness_policy=params.get("missingness_policy", "ineligible"),
        balance_check=params.get("balance_check"),
        raw_parameters=dict(params),
    )
    if design.missingness_policy not in ("ineligible", "impute_cohort_mean"):
        raise ManifestError(
            "unsupported missingness_policy %r (expected 'ineligible' or 'impute_cohort_mean')"
            % design.missingness_policy
        )

    ap = raw["analysis_plan"]
    if ap["test_sidedness"] != "one_sided_lower":
        raise ManifestError(
            "Invariant 3: test_sidedness must be 'one_sided_lower', got %r" % ap["test_sidedness"]
        )
    cvr = ap.get("critical_value_reference")
    if cvr == "student_t" and "df" not in ap:
        raise ManifestError("critical_value_reference='student_t' requires df")
    if cvr == "normal_approx" and "df" in ap:
        raise ManifestError("critical_value_reference='normal_approx' must not carry df")
    ms = ap["minimum_sample"]
    plan = AnalysisPlan(
        estimator=ap["estimator"],
        standard_error_method=ap["standard_error_method"],
        test_sidedness=ap["test_sidedness"],
        confidence_level_micro=_uint(ap, "confidence_level_micro"),
        critical_value_micro=_uint(ap, "critical_value_micro"),
        critical_value_reference=cvr,
        df=_uint(ap, "df") if "df" in ap else None,
        covariate_adjustment=tuple(ap.get("covariate_adjustment", ())),
        minimum_sample=MinimumSample(
            min_units_per_cohort=_uint(ms, "min_units_per_cohort"),
            min_observations_per_cohort=_uint(ms, "min_observations_per_cohort"),
            min_time_blocks=_uint(ms, "min_time_blocks"),
            min_eligible_cohorts=_uint(ms, "min_eligible_cohorts"),
        ),
        sensitivity_analyses=tuple(ap.get("sensitivity_analyses", ())),
        analysis_container_digest=ap["analysis_container_digest"],
    )

    rp = raw["reward_policy"]
    pit = rp["positive_improvement_transform"]
    curve = rp["reward_curve"]
    bps_raw = curve["breakpoints"]
    bps: list[tuple[int, int]] = []
    for pair in bps_raw:
        if len(pair) != 2 or not all(isinstance(v, str) and _UINT_RE.match(v) for v in pair):
            raise ManifestError("reward_curve breakpoint %r is not a pair of uint strings" % (pair,))
        bps.append((int(pair[0]), int(pair[1])))
    if bps[0] != (0, 0):
        raise ManifestError("reward_curve first breakpoint must be ['0','0'], got %r" % (bps[0],))
    for (x0, y0), (x1, y1) in zip(bps, bps[1:]):
        if x1 <= x0:
            raise ManifestError("reward_curve must be strictly increasing in x")
        if y1 < y0:
            raise ManifestError("reward_curve must be non-decreasing in y (monotonic)")
    curve_hash = "sha256:" + sha256_hex(canonical_json_bytes(curve))
    if rp["reward_curve_hash"] != curve_hash:
        raise ManifestError(
            "reward_curve_hash mismatch: manifest says %s, canonical bytes hash to %s"
            % (rp["reward_curve_hash"], curve_hash)
        )

    split = rp["intra_cohort_split"]
    if split["rule"] != "quality_weighted":
        raise ManifestError("Invariant 4: intra_cohort_split.rule must be 'quality_weighted'")
    terms = parse_weight_formula(split["weight_formula"])

    policy = RewardPolicy(
        budget_base_units=_uint(rp, "budget_base_units"),
        mint=rp["mint"],
        transform_type=pit["type"],
        effect_scale=_sint(pit, "effect_scale"),
        breakpoints=tuple(bps),
        reward_curve_hash=rp["reward_curve_hash"],
        split_rule=split["rule"],
        weight_formula=split["weight_formula"],
        weight_terms=tuple(terms),
        weight_scale=_sint(split, "weight_scale"),
        overflow_policy=rp["overflow_policy"],
        unused_budget_policy=rp["unused_budget_policy"],
    )
    if not (-12 <= policy.effect_scale <= 0):
        raise ManifestError("effect_scale out of semantic range [-12, 0]: %d" % policy.effect_scale)

    po = raw["primary_outcome"]
    return Manifest(
        experiment_id=raw["experiment_id"],
        spec_version=raw["spec_version"],
        manifest_version=raw["manifest_version"],
        primary_outcome_id=po["metric_id"],
        improvement_direction=po["improvement_direction"],
        unit_type=est["unit_type"],
        cohort_count=_uint(est["cohort_definition"], "cohort_count"),
        block_count=_uint(est["time_block"], "block_count"),
        design=design,
        analysis_plan=plan,
        reward_policy=policy,
        manifest_hash="sha256:" + sha256_hex(canonical_json_bytes(raw)),
        raw=dict(raw),
    )
