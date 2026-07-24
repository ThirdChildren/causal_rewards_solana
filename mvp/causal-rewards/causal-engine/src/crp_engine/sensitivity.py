"""Sensitivity analyses — DESCRIPTIVE outputs that never move a payout.

The protocol has exactly **one primary outcome and one primary estimate** (CLAUDE.md; the
manifest allows exactly one ``primary_outcome``). Everything in this module is a secondary,
descriptive diagnostic: it is reported in ``analysis.json`` and is grounds for a challenge, but
it never enters ``conservative_effect``. Re-selecting an estimate on the basis of a sensitivity
result after seeing outcomes would violate Invariant 1, and reporting an uncorrected secondary
p-value as if it were confirmatory would violate the one-primary-outcome rule.

Which analyses run is frozen in ``analysis_plan.sensitivity_analyses``. Supported names:

``leave_one_cohort_out``
    Refit the primary estimate dropping each cohort in turn; report the min/max/range. A single
    cohort driving the whole effect is a fragility signal.
``placebo_time_shift``
    Rotate every cohort's arm labels forward by one time block and refit. The true effect is
    destroyed by the rotation, so a large placebo estimate indicates residual confounding or
    carryover leaking into the contrast.
``wild_cluster_bootstrap``
    Cameron-Gelbach-Miller wild cluster bootstrap with Rademacher weights under the RESTRICTED
    null (Cameron & Miller 2015 §VI.C.2; Davidson & Flachaire 2008 for the two-point weights).
    Reports a bootstrap p-value for H0: effect = 0. Randomness is derived **only** from the
    committed seed via a domain-separated SHA-256 stream (Invariant 2).
``interference_spillover``
    Regress the outcome on own-treatment plus the fraction of treated *neighbours* in the same
    block (requires an adjacency map). Reports the spillover coefficient and how much the direct
    effect moves once spillover is admitted — DePIN cohorts interfere, so this is surfaced, not
    hidden.
``carryover_washout_sensitivity``
    Refit with the frozen washout and with washout+1 to show the estimate is not an artefact of
    the discard boundary.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from crp_engine import numeric as nm
from crp_engine.estimators import ols_cluster_robust, pooled_effect
from crp_engine.panel import IdentificationMode, Panel

__all__ = [
    "SensitivityResult",
    "SUPPORTED",
    "run_sensitivity",
    "rademacher_stream",
]

SUPPORTED: tuple[str, ...] = (
    "leave_one_cohort_out",
    "placebo_time_shift",
    "wild_cluster_bootstrap",
    "interference_spillover",
    "carryover_washout_sensitivity",
)

WILD_BOOTSTRAP_REPLICATIONS = 999
_BOOTSTRAP_DOMAIN = b"CRP-engine-wildboot-v1"


@dataclass(frozen=True)
class SensitivityResult:
    name: str
    kind: str  # always "descriptive"
    status: str  # "ok" | "skipped" | "unsupported"
    values: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""


def rademacher_stream(seed: bytes, n_clusters: int, replication: int) -> list[float]:
    """Deterministic Rademacher (+/-1) weights for one bootstrap replication.

    Derived ONLY from the committed seed: ``SHA-256(domain || seed || u32be(rep) || u32be(chunk))``
    expanded bitwise. No ``numpy.random``, no OS entropy, no wall-clock — the same seed always
    yields the same bootstrap p-value, so the committed number is reproducible (Invariant 2).
    """
    out: list[float] = []
    chunk = 0
    while len(out) < n_clusters:
        digest = hashlib.sha256(
            _BOOTSTRAP_DOMAIN
            + seed
            + replication.to_bytes(4, "big")
            + chunk.to_bytes(4, "big")
        ).digest()
        for byte in digest:
            for bit in range(8):
                if len(out) >= n_clusters:
                    break
                out.append(1.0 if (byte >> bit) & 1 else -1.0)
        chunk += 1
    return out


# --------------------------------------------------------------------------------------


def run_sensitivity(
    panel: Panel,
    *,
    covariates: Sequence[str] = (),
    seed: bytes = b"\x00" * 32,
    adjacency: Mapping[str, Sequence[str]] | None = None,
) -> list[SensitivityResult]:
    """Run the frozen sensitivity list, in the frozen order, skipping what the data cannot support."""
    plan = panel.manifest.analysis_plan
    out: list[SensitivityResult] = []
    for name in plan.sensitivity_analyses:
        if name not in SUPPORTED:
            out.append(
                SensitivityResult(
                    name, "descriptive", "unsupported",
                    note="frozen sensitivity analysis %r has no implementation in this engine "
                         "version; reported as not run rather than silently skipped" % name,
                )
            )
            continue
        fn = _DISPATCH[name]
        try:
            out.append(fn(panel, covariates, seed, adjacency))
        except Exception as exc:  # a diagnostic must never take down the primary artifact
            out.append(
                SensitivityResult(name, "descriptive", "skipped", note="%s: %s" % (type(exc).__name__, exc))
            )
    return out


def _loco(panel: Panel, covariates, seed, adjacency) -> SensitivityResult:
    base = pooled_effect(panel, covariates=covariates).get("treated")[0]
    vals: list[tuple[str, float]] = []
    for cid in panel.cohort_ids:
        sub = panel.frame[panel.frame["cohort_id"] != cid]
        if sub["cohort_id"].nunique() < 2:
            continue
        try:
            refit = pooled_effect(_replace_frame(panel, sub), covariates=covariates)
            vals.append((cid, refit.get("treated")[0]))
        except Exception:
            continue
    if not vals:
        return SensitivityResult("leave_one_cohort_out", "descriptive", "skipped",
                                 note="fewer than 2 cohorts remain after dropping one")
    effects = [v for _, v in vals]
    lo_i = min(range(len(vals)), key=lambda i: effects[i])
    hi_i = max(range(len(vals)), key=lambda i: effects[i])
    return SensitivityResult(
        "leave_one_cohort_out", "descriptive", "ok",
        {
            "full_sample_effect": base,
            "min_effect": effects[lo_i],
            "min_effect_dropped_cohort": vals[lo_i][0],
            "max_effect": effects[hi_i],
            "max_effect_dropped_cohort": vals[hi_i][0],
            "range": effects[hi_i] - effects[lo_i],
            "n_refits": len(vals),
        },
        note="A range comparable to the effect itself means one cohort drives the result.",
    )


def _placebo(panel: Panel, covariates, seed, adjacency) -> SensitivityResult:
    frame = panel.frame.sort_values(["cohort_id", "time_block"], kind="mergesort").copy()
    original = frame["arm"].tolist()
    shifted: list[str] = []
    for _cid, grp in frame.groupby("cohort_id", sort=True):
        arms = grp["arm"].tolist()
        shifted.extend([arms[-1]] + arms[:-1] if arms else [])
    frame["arm"] = shifted
    if frame["arm"].nunique() < 2:
        return SensitivityResult("placebo_time_shift", "descriptive", "skipped",
                                 note="rotation leaves a single arm")

    n = len(original)
    same = sum(1 for a, b in zip(original, shifted) if a == b) / n
    flipped = 1.0 - same
    if same > 0.999 or flipped > 0.999:
        # A period-1 switchback alternates every block, so a one-block rotation reproduces the
        # assignment exactly inverted. The placebo statistic is then -1 x the real effect BY
        # CONSTRUCTION and carries no information. Say so rather than reporting a spurious pass.
        return SensitivityResult(
            "placebo_time_shift", "descriptive", "skipped",
            {"shift_blocks": 1, "fraction_unchanged": same},
            note="A one-block rotation reproduces the real assignment %s, so the placebo is "
                 "uninformative by construction for this schedule (a period-1 alternating "
                 "switchback). No placebo evidence either way." % (
                     "exactly" if same > 0.999 else "exactly inverted"),
        )

    real = pooled_effect(panel, covariates=covariates).get("treated")
    fake = pooled_effect(_replace_frame(panel, frame), covariates=covariates).get("treated")
    return SensitivityResult(
        "placebo_time_shift", "descriptive", "ok",
        {
            "shift_blocks": 1,
            "fraction_unchanged": same,
            "real_effect": real[0], "real_se": real[1],
            "placebo_effect": fake[0], "placebo_se": fake[1],
            "placebo_abs_over_real_abs": (abs(fake[0]) / abs(real[0])) if real[0] != 0 else math.inf,
        },
        note="Arm labels rotated one block forward within each cohort. A placebo effect close to "
             "the real one indicates the contrast is not carrying treatment information.",
    )


def _wild_bootstrap(panel: Panel, covariates, seed, adjacency) -> SensitivityResult:
    """Wild cluster bootstrap-t, Rademacher weights, restricted null (Cameron & Miller 2015)."""
    frame = panel.frame
    y = frame["outcome"].to_numpy(dtype=np.float64)
    treated = (frame["arm"].to_numpy() == "treatment").astype(np.float64)
    covs = [c for c in covariates if c in frame.columns]
    cols = [np.ones(len(frame)), treated] + [frame[c].to_numpy(dtype=np.float64) for c in covs]
    names = ["intercept", "treated"] + ["cov:" + c for c in covs]
    X = np.column_stack(cols)
    clusters = frame["cohort_id"].tolist()

    fit = ols_cluster_robust(X, y, clusters, names)
    b, se = fit.get("treated")
    if se == 0.0:
        return SensitivityResult("wild_cluster_bootstrap", "descriptive", "skipped",
                                 note="zero standard error")
    w_obs = abs(b / se)

    # Restricted null: refit WITHOUT the treated column, then resample its residuals.
    keep = [i for i, n in enumerate(names) if n != "treated"]
    X0 = X[:, keep]
    names0 = [names[i] for i in keep]
    fit0 = ols_cluster_robust(X0, y, clusters, names0)
    resid0 = y - nm.matvec(X0, fit0.coef)
    fitted0 = nm.matvec(X0, fit0.coef)

    labels = np.asarray(clusters, dtype=object)
    uniq = sorted(set(clusters))
    idx_of = {g: i for i, g in enumerate(uniq)}
    cluster_idx = np.asarray([idx_of[c] for c in clusters], dtype=np.int64)

    exceed = 0
    done = 0
    for rep in range(WILD_BOOTSTRAP_REPLICATIONS):
        d = rademacher_stream(seed, len(uniq), rep)
        w = np.asarray([d[i] for i in cluster_idx], dtype=np.float64)
        y_star = fitted0 + resid0 * w
        try:
            f = ols_cluster_robust(X, y_star, clusters, names)
        except Exception:
            continue
        bb, sb = f.get("treated")
        done += 1
        if sb > 0 and abs(bb / sb) > w_obs:
            exceed += 1
    if done == 0:
        return SensitivityResult("wild_cluster_bootstrap", "descriptive", "skipped",
                                 note="no bootstrap replication converged")
    return SensitivityResult(
        "wild_cluster_bootstrap", "descriptive", "ok",
        {
            "wald_statistic": w_obs,
            "p_value": exceed / done,
            "replications": done,
            "n_clusters": len(uniq),
            "weights": "rademacher_two_point",
            "null": "restricted",
        },
        note="Descriptive only. With G < 10 clusters the two-point bootstrap p-value is coarse "
             "(Webb 2013); the frozen critical value, not this p-value, governs payout.",
    )


def _spillover(panel: Panel, covariates, seed, adjacency) -> SensitivityResult:
    if not adjacency:
        return SensitivityResult(
            "interference_spillover", "descriptive", "skipped",
            note="no adjacency map supplied; cannot measure spillover from treated neighbours",
        )
    frame = panel.frame
    treated_by_key = {
        (r.cohort_id, int(r.time_block)): (r.arm == "treatment")
        for r in frame.itertuples(index=False)
    }
    share: list[float] = []
    for r in frame.itertuples(index=False):
        nbrs = [n for n in adjacency.get(r.cohort_id, ()) if (n, int(r.time_block)) in treated_by_key]
        if not nbrs:
            share.append(0.0)
        else:
            share.append(
                nm.fsum(1.0 if treated_by_key[(n, int(r.time_block))] else 0.0 for n in nbrs)
                / len(nbrs)
            )
    y = frame["outcome"].to_numpy(dtype=np.float64)
    treated = (frame["arm"].to_numpy() == "treatment").astype(np.float64)
    nbr = np.asarray(share, dtype=np.float64)
    base = ols_cluster_robust(
        np.column_stack([np.ones(len(y)), treated]), y,
        frame["cohort_id"].tolist(), ["intercept", "treated"],
    ).get("treated")
    if float(nbr.max() - nbr.min()) == 0.0:
        return SensitivityResult("interference_spillover", "descriptive", "skipped",
                                 note="treated-neighbour share has no variation")
    adj = ols_cluster_robust(
        np.column_stack([np.ones(len(y)), treated, nbr]), y,
        frame["cohort_id"].tolist(), ["intercept", "treated", "neighbour_treated_share"],
    )
    direct = adj.get("treated")
    spill = adj.get("neighbour_treated_share")
    return SensitivityResult(
        "interference_spillover", "descriptive", "ok",
        {
            "naive_effect": base[0], "naive_se": base[1],
            "direct_effect_adjusted": direct[0], "direct_se_adjusted": direct[1],
            "spillover_coefficient": spill[0], "spillover_se": spill[1],
            "bias_from_ignoring_spillover": base[0] - direct[0],
        },
        note="A spillover coefficient of the same sign as the direct effect means the frozen "
             "interference assumption (%s) understates the true benefit of inclusion; the "
             "cohort-level estimand is then a lower bound, not an unbiased ATE."
             % panel.manifest.design.interference_assumption,
    )


def _washout_sensitivity(panel: Panel, covariates, seed, adjacency) -> SensitivityResult:
    from crp_engine.panel import _apply_washout  # local import: internal helper

    frozen = panel.manifest.design.washout_blocks
    rows = []
    for w in (frozen, frozen + 1):
        sub, dropped = _apply_washout(panel.frame, w)
        if sub.empty or sub["arm"].nunique() < 2 or sub["cohort_id"].nunique() < 2:
            continue
        try:
            fit = pooled_effect(_replace_frame(panel, sub), covariates=covariates)
        except Exception:
            continue
        e, s = fit.get("treated")
        rows.append({"washout_blocks": w, "effect": e, "se": s, "rows_dropped": dropped,
                     "rows_used": len(sub)})
    if len(rows) < 2:
        return SensitivityResult("carryover_washout_sensitivity", "descriptive", "skipped",
                                 note="not enough data to refit at washout+1")
    return SensitivityResult(
        "carryover_washout_sensitivity", "descriptive", "ok",
        {"fits": rows, "effect_shift": rows[1]["effect"] - rows[0]["effect"]},
        note="Frozen washout vs washout+1. A large shift means the frozen carryover order is "
             "probably too small (Bojinov-Simchi-Levi-Zhao Assumption 2 misspecified).",
    )


def _replace_frame(panel: Panel, frame: pd.DataFrame) -> Panel:
    """A shallow Panel clone over a filtered frame (diagnostics only, never re-derives eligibility)."""
    from dataclasses import replace

    return replace(panel, frame=frame.reset_index(drop=True))


_DISPATCH = {
    "leave_one_cohort_out": _loco,
    "placebo_time_shift": _placebo,
    "wild_cluster_bootstrap": _wild_bootstrap,
    "interference_spillover": _spillover,
    "carryover_washout_sensitivity": _washout_sensitivity,
}
