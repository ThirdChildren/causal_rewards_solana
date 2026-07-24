"""Estimators: cluster-robust OLS + the per-cohort contrasts that Stage 1 values.

Design rule (CLAUDE.md, causal-engine charter): **simple, auditable estimators over causal ML.**
Everything here is OLS, a difference in means, or a sandwich variance. An auditor with the spec
and a spreadsheet can follow every number.

Cluster-robust variance (Cameron & Miller 2015, *A Practitioner's Guide to Cluster-Robust
Inference*, JHR 50(2):317-372, eq. 10-12):

    beta_hat = (X'X)^-1 X'y
    V_clu    = c * (X'X)^-1 [ sum_g X_g' u_g u_g' X_g ] (X'X)^-1
    c        = G/(G-1) * (N-1)/(N-K)                                     (their eq. 12, "CR1")

with `G` clusters, `N` observations, `K` regressors. `c ~= G/(G-1)`. Cameron & Miller recommend
`T(G-1)` critical values; the protocol instead **freezes** `critical_value_micro` in the manifest
(Invariant 1/2) and this module reports `G-1` as `df` so an auditor can check the frozen value
against the reference distribution.

The cluster is always the **geo-cohort** for the pooled estimate. `G` is therefore the number of
geo-cohorts, not the number of cohort x block rows — treating blocks within a cohort as
independent would understate the variance, which is exactly the failure mode a DePIN panel with
cohort-shared noise produces.

**Fixed effects are ABSORBED, never entered as dummies.** Cameron & Miller §III.B is explicit:
LSDV (dummy-variable) fixed effects and the within (demeaning) estimator give identical
coefficients but *different* finite-sample corrections, and the LSDV one is wrong — it counts the
G-1 dummies in K, inflating `c` toward `N*/(N*-1)` for small clusters. They name
`xtreg y x, fe vce(robust)` (the within estimator) as "the desired CRVE". This module therefore
demeans within the absorbed group and computes `c` with K = the number of *within-varying*
regressors only, matching the within estimator. Time-block dummies are deliberately not added:
under randomization they are an efficiency nicety, and entering T-1 more columns would
re-introduce the same K-inflation problem.

Numerics: every reduction goes through :mod:`crp_engine.numeric` (exactly-rounded `math.fsum`,
BLAS-free tiny solves), so committed numbers are bit-identical across machines and BLAS builds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from crp_engine import numeric as nm
from crp_engine.manifest import Manifest
from crp_engine.panel import IdentificationMode, Panel

__all__ = [
    "OLSResult",
    "CohortEffect",
    "ols_cluster_robust",
    "pooled_effect",
    "cohort_effects",
]


@dataclass(frozen=True)
class OLSResult:
    """Cluster-robust OLS fit. ``coef``/``se`` are indexed by ``names``."""

    names: tuple[str, ...]
    coef: tuple[float, ...]
    se: tuple[float, ...]
    n_obs: int
    n_clusters: int
    n_params: int
    finite_sample_correction: float
    residual_sd: float
    n_absorbed_groups: int = 0

    def get(self, name: str) -> tuple[float, float]:
        i = self.names.index(name)
        return self.coef[i], self.se[i]


@dataclass(frozen=True)
class CohortEffect:
    """A per-cohort effect on the RAW outcome metric (lower/higher is better per the manifest).

    ``effect`` is ``E[Y | treated] - E[Y | control]`` for this cohort under the identification
    mode in force. The positive-improvement transform is applied later, by the reward compiler —
    the estimator never pre-flips a sign.
    """

    cohort_id: str
    effect: float
    standard_error: float
    n_obs: int
    n_clusters: int
    identified: bool
    mode: str
    note: str = ""


# --------------------------------------------------------------------------------------
# Core: cluster-robust OLS
# --------------------------------------------------------------------------------------

def _demean(values: np.ndarray, groups: Sequence[str]) -> np.ndarray:
    """Subtract the group mean from each column (the within transformation).

    Group means use exactly-rounded ``fsum`` accumulation in sorted group order, so the
    transformation is bit-reproducible.
    """
    arr = np.asarray(values, dtype=np.float64)
    two_d = arr.ndim == 2
    mat = arr if two_d else arr.reshape(-1, 1)
    labels = np.asarray([str(g) for g in groups], dtype=object)
    out = mat.copy()
    for g in sorted(set(labels.tolist())):
        sel = labels == g
        n_g = int(sel.sum())
        for j in range(mat.shape[1]):
            out[sel, j] = mat[sel, j] - (math.fsum(mat[sel, j].tolist()) / n_g)
    return out if two_d else out.ravel()


def ols_cluster_robust(
    X: np.ndarray,
    y: np.ndarray,
    clusters: Sequence[str],
    names: Sequence[str],
    absorb: Sequence[str] | None = None,
) -> OLSResult:
    """OLS with the CR1 cluster-robust sandwich variance.

    ``clusters`` labels each row with its cluster id. Cluster iteration order is the SORTED
    unique cluster order — never dict/set iteration order (Invariant 2).

    ``absorb``, when given, labels each row with a fixed-effect group. The group means are
    swept out of ``y`` and ``X`` (the within transformation) instead of adding dummy columns,
    so ``K`` in the CR1 correction counts only the within-varying regressors — the correction
    Cameron & Miller §III.B identify as the correct one. ``X`` must NOT contain an intercept
    when absorbing (the within model is estimated without one).
    """
    Xf = np.asarray(X, dtype=np.float64)
    yf = np.asarray(y, dtype=np.float64).ravel()
    n, k = Xf.shape
    if yf.size != n:
        raise ValueError("ols: X has %d rows but y has %d" % (n, yf.size))
    if len(names) != k:
        raise ValueError("ols: %d names for %d columns" % (len(names), k))
    if n <= k:
        raise ValueError("ols: n (%d) must exceed k (%d)" % (n, k))

    n_absorbed = 0
    if absorb is not None:
        if "intercept" in names:
            raise ValueError("absorbed fixed effects and an explicit intercept are incompatible")
        n_absorbed = len(set(str(g) for g in absorb))
        Xf = _demean(Xf, absorb)
        yf = _demean(yf, absorb)
        if n - n_absorbed <= k:
            raise ValueError(
                "ols: too few residual degrees of freedom after absorbing %d groups" % n_absorbed
            )

    XtX = nm.gram(Xf)
    Xty = nm.xty(Xf, yf)
    beta = nm.solve(XtX, Xty)
    resid = yf - nm.matvec(Xf, beta)

    labels = np.asarray([str(c) for c in clusters], dtype=object)
    uniq = sorted(set(labels.tolist()))
    G = len(uniq)
    if G < 2:
        raise ValueError("cluster-robust inference needs >= 2 clusters, got %d" % G)

    # meat = sum_g (X_g' u_g)(X_g' u_g)'   — deterministic cluster order, fsum accumulation.
    meat = [[0.0] * k for _ in range(k)]
    scores: list[list[float]] = []
    for g in uniq:
        sel = labels == g
        Xg = Xf[sel]
        ug = resid[sel]
        scores.append([math.fsum((Xg[:, j] * ug).tolist()) for j in range(k)])
    for i in range(k):
        for j in range(i, k):
            v = math.fsum(s[i] * s[j] for s in scores)
            meat[i][j] = v
            meat[j][i] = v

    bread = nm.inverse(XtX)
    # CR1 (Cameron & Miller 2015 eq. 12). With absorbed fixed effects this is the WITHIN-estimator
    # correction: K counts only the within-varying regressors, exactly as `xtreg, fe vce(robust)`
    # does, not the LSDV count that would include the G-1 absorbed dummies (their §III.B).
    c = (G / (G - 1)) * ((n - 1) / (n - k))
    V = nm.matmul(nm.matmul(bread, meat), bread)
    se = tuple(math.sqrt(c * V[j][j]) if V[j][j] > 0 else 0.0 for j in range(k))

    dof = n - k - n_absorbed
    rss = math.fsum((resid * resid).tolist())
    return OLSResult(
        names=tuple(names),
        coef=tuple(beta),
        se=se,
        n_obs=n,
        n_clusters=G,
        n_params=k,
        finite_sample_correction=c,
        residual_sd=math.sqrt(rss / dof) if dof > 0 else 0.0,
        n_absorbed_groups=n_absorbed,
    )


# --------------------------------------------------------------------------------------
# Pooled (primary) estimate — ONE primary outcome, one primary estimand
# --------------------------------------------------------------------------------------

def _design_matrix(
    frame: pd.DataFrame, covariates: Sequence[str], *, intercept: bool
) -> tuple[np.ndarray, list[str]]:
    """Build ``[intercept?, treated, covariates...]`` in a FIXED column order.

    Fixed effects never appear here: they are absorbed by :func:`ols_cluster_robust`.
    """
    cols: list[np.ndarray] = []
    names: list[str] = []
    if intercept:
        cols.append(np.ones(len(frame), dtype=np.float64))
        names.append("intercept")
    cols.append((frame["arm"].to_numpy() == "treatment").astype(np.float64))
    names.append("treated")
    for c in covariates:
        cols.append(frame[c].to_numpy(dtype=np.float64))
        names.append("cov:" + c)
    return np.column_stack(cols), names


def pooled_effect(panel: Panel, *, covariates: Sequence[str] = ()) -> OLSResult:
    """The single primary estimate: the average effect of inclusion, clustered on geo-cohort.

    * ``diff_in_means`` -> intercept + treated only, clustered on the cohort.
    * ``cluster_robust_ols`` -> + frozen covariates; cohort fixed effects are ABSORBED when the
      arm varies within a cohort (that is the within contrast), clustered on the cohort.
    * ``switchback_hac`` -> geo-group fixed effects absorbed, clustered on the geo group (the
      randomization unit of a regional switchback). See :mod:`crp_engine.panel` for the washout.
    * ``matched_pair_diff`` -> matched-stratum fixed effects absorbed, clustered on the stratum.

    One primary outcome, one primary number.
    """
    m = panel.manifest
    est = m.analysis_plan.estimator
    frame = panel.frame
    covs = [c for c in covariates if c in frame.columns]
    within = panel.identification is IdentificationMode.WITHIN_COHORT
    y = frame["outcome"].to_numpy(dtype=np.float64)
    groups = [_group(c) for c in frame["cohort_id"].tolist()]

    if est == "diff_in_means":
        X, names = _design_matrix(frame, (), intercept=True)
        return ols_cluster_robust(X, y, frame["cohort_id"].tolist(), names)

    if est == "cluster_robust_ols":
        if within:
            X, names = _design_matrix(frame, covs, intercept=False)
            return ols_cluster_robust(
                X, y, frame["cohort_id"].tolist(), names, absorb=frame["cohort_id"].tolist()
            )
        X, names = _design_matrix(frame, covs, intercept=True)
        return ols_cluster_robust(X, y, frame["cohort_id"].tolist(), names)

    if est == "switchback_hac":
        # Regional switchback: randomization is ONE phase bit per geo group, so the geo group is
        # the cluster. Clustering on the group gives unrestricted within-group autocorrelation
        # robustness — strictly more general than a truncated Newey-West kernel and, unlike a
        # kernel, it needs no unfrozen bandwidth. An explicit bandwidth may be frozen in
        # design.parameters.hac_bandwidth_blocks; see docs/modeling-notes.md.
        X, names = _design_matrix(frame, covs, intercept=False)
        return ols_cluster_robust(X, y, groups, names, absorb=groups)

    if est == "matched_pair_diff":
        X, names = _design_matrix(frame, covs, intercept=False)
        return ols_cluster_robust(X, y, groups, names, absorb=groups)

    raise ValueError("unknown estimator %r" % est)


def _group(cohort_id: str) -> str:
    return cohort_id.split("|", 1)[0] if cohort_id.count("|") == 1 else cohort_id


# --------------------------------------------------------------------------------------
# Per-cohort effects — what Stage 1 actually values
# --------------------------------------------------------------------------------------

def cohort_effects(panel: Panel) -> dict[str, CohortEffect]:
    """Estimate an effect + SE for EVERY cohort, under the panel's identification mode.

    Returns one entry per cohort in sorted cohort order. Cohorts whose effect is not identified
    get ``identified=False`` and are forced to zero allocation by the reward compiler — an honest
    null, not a hidden exclusion.
    """
    mode = panel.identification
    if mode is IdentificationMode.WITHIN_COHORT:
        return _within_cohort_effects(panel)
    if mode is IdentificationMode.MATCHED_STRATUM:
        return _matched_stratum_effects(panel)
    if mode is IdentificationMode.BETWEEN_COHORT_VS_CONTROL_POOL:
        return _control_pool_effects(panel)
    return {
        cid: CohortEffect(cid, 0.0, 0.0, 0, 0, False, mode.value, "no identified contrast")
        for cid in panel.cohort_ids
    }


def _cluster_key(sub: pd.DataFrame) -> list[str]:
    """Cluster label for a within-cohort contrast: the maximal run of equal-arm blocks.

    For per-block randomization each block is its own run (=> heteroskedasticity-robust). For a
    switchback the run is exactly the switchback *period*, so within-period serial correlation is
    absorbed rather than counted as independent information. Uniform, simple, auditable.
    """
    arms = sub["arm"].to_numpy()
    out: list[str] = []
    run = 0
    for i in range(len(arms)):
        if i > 0 and arms[i] != arms[i - 1]:
            run += 1
        out.append("run%d" % run)
    return out


def _within_cohort_effects(panel: Panel) -> dict[str, CohortEffect]:
    res: dict[str, CohortEffect] = {}
    for cid in panel.cohort_ids:
        sub = panel.rows(cid).sort_values("time_block", kind="mergesort")
        y = sub["outcome"].to_numpy(dtype=np.float64)
        treated = (sub["arm"].to_numpy() == "treatment").astype(np.float64)
        n_t = int(treated.sum())
        n_c = int(len(treated) - n_t)
        if n_t == 0 or n_c == 0:
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, len(y), 0, False, "within_cohort",
                "cohort has only one arm; no within-cohort contrast",
            )
            continue
        clusters = _cluster_key(sub)
        n_clusters = len(set(clusters))
        X = np.column_stack([np.ones(len(y)), treated])
        if n_clusters >= 2 and len(y) > 2:
            try:
                fit = ols_cluster_robust(X, y, clusters, ["intercept", "treated"])
                b, se = fit.get("treated")
                res[cid] = CohortEffect(cid, b, se, len(y), n_clusters, True, "within_cohort")
                continue
            except (ValueError, nm.SingularMatrixError):
                pass
        # Fallback: difference in means with an unpooled two-sample SE. Reported as identified
        # only when both arms have >= 2 observations, otherwise the SE is not estimable.
        yt = y[treated == 1.0]
        yc = y[treated == 0.0]
        if len(yt) >= 2 and len(yc) >= 2:
            se = math.sqrt(
                nm.sample_variance(yt.tolist()) / len(yt)
                + nm.sample_variance(yc.tolist()) / len(yc)
            )
            res[cid] = CohortEffect(
                cid, nm.vmean(yt) - nm.vmean(yc), se, len(y), 2, True,
                "within_cohort", "too few runs for a cluster-robust SE; unpooled two-sample SE",
            )
        else:
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, len(y), n_clusters, False, "within_cohort",
                "fewer than 2 observations in one arm; SE not estimable",
            )
    return res


def _matched_stratum_effects(panel: Panel) -> dict[str, CohortEffect]:
    """Contrast each member against the opposite-arm members of its own frozen stratum.

    For member ``c`` in stratum ``s`` the block-level difference is
    ``d_t = y_{c,t} - mean_{c' in s, opposite arm} y_{c',t}``; the cohort effect is ``mean_t d_t``
    signed so that it always reads treatment-minus-control, with SE ``sd(d)/sqrt(T)`` (the paired
    SE — the block is the unit of the paired difference). Only treated members earn value; a
    held-out member contributed no data and has nothing to be paid for.
    """
    res: dict[str, CohortEffect] = {}
    for cid in panel.cohort_ids:
        sub = panel.rows(cid).sort_values("time_block", kind="mergesort")
        arm = sub["arm"].iloc[0] if len(sub) else "control"
        if len(set(sub["arm"].tolist())) > 1:
            # Arm varies within the member: this is a within-cohort contrast after all.
            res.update({k: v for k, v in _within_cohort_effects(panel).items() if k == cid})
            continue
        group = _group(cid)
        partners = [
            p for p in panel.strata.get(group, ())
            if p != cid and panel.rows(p)["arm"].iloc[0] != arm
        ]
        if not partners:
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, len(sub), 0, False, "matched_stratum",
                "no opposite-arm partner in the frozen stratum",
            )
            continue
        own = dict(zip(sub["time_block"].tolist(), sub["outcome"].tolist()))
        partner_rows = pd.concat([panel.rows(p) for p in partners])
        partner_mean = (
            partner_rows.groupby("time_block", sort=True)["outcome"].mean().to_dict()
        )
        blocks = sorted(set(own) & set(partner_mean))
        diffs = [own[t] - partner_mean[t] for t in blocks]
        if arm == "control":
            diffs = [-d for d in diffs]
        if len(diffs) < 2:
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, len(sub), len(blocks), False, "matched_stratum",
                "fewer than 2 overlapping time blocks; SE not estimable",
            )
            continue
        effect = nm.fsum(diffs) / len(diffs)
        se = math.sqrt(nm.sample_variance(diffs) / len(diffs))
        res[cid] = CohortEffect(
            cid, effect, se, len(sub), len(diffs), True, "matched_stratum",
            "" if arm == "treatment" else "held-out member: contrast reported, no data contributed",
        )
    return res


def _control_pool_effects(panel: Panel) -> dict[str, CohortEffect]:
    """Whole-cohort assignment: contrast each cohort against the randomized control POOL.

    ``tau_c = mean(y_c) - mean_over_control_cohorts(mean(y_{c'}))``.

    Variance. The control-pool mean has variance ``s2_b / G0`` where ``s2_b`` is the unbiased
    variance of the ``G0`` control-cohort means — the between-cohort (cluster-robust) variance.
    A *single* cohort's mean has variance ``s2_b`` and it is not estimable from that cohort alone
    (one draw), so we substitute the control-pool estimate:

        SE(tau_c) = sqrt( s2_b * (1 + 1/G0) )

    This is deliberately conservative: it carries the full between-cohort dispersion, which under
    a DePIN panel with cohort-shared noise usually dominates. If that yields a zero conservative
    bound for most cohorts, that is the correct answer about this design's per-cohort power, not
    a defect to tune away (CLAUDE.md invariant 8).
    """
    frame = panel.frame
    means: dict[str, float] = {}
    counts: dict[str, int] = {}
    arms: dict[str, str] = {}
    for cid in panel.cohort_ids:
        sub = panel.rows(cid)
        means[cid] = nm.vmean(sub["outcome"].to_numpy(dtype=np.float64))
        counts[cid] = len(sub)
        arms[cid] = str(sub["arm"].iloc[0])

    control_ids = [c for c in panel.cohort_ids if arms[c] == "control"]
    G0 = len(control_ids)
    res: dict[str, CohortEffect] = {}
    if G0 < 2:
        for cid in panel.cohort_ids:
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, counts[cid], G0, False, "between_cohort_vs_control_pool",
                "fewer than 2 control cohorts; between-cohort variance not estimable",
            )
        return res

    control_means = [means[c] for c in control_ids]
    pool_mean = nm.fsum(control_means) / G0
    s2_b = nm.sample_variance(control_means)
    se = math.sqrt(s2_b * (1.0 + 1.0 / G0))

    for cid in panel.cohort_ids:
        if arms[cid] == "control":
            res[cid] = CohortEffect(
                cid, 0.0, 0.0, counts[cid], G0, False, "between_cohort_vs_control_pool",
                "cohort was held out this experiment; it contributed no data to value",
            )
            continue
        res[cid] = CohortEffect(
            cid, means[cid] - pool_mean, se, counts[cid], G0, True,
            "between_cohort_vs_control_pool",
            "SE carries the full between-cohort variance (see identification assumptions)",
        )
    return res
