"""Estimator tests: known answers on hand-computable data + recovery of a KNOWN true effect.

The cluster-robust variance is checked against an INDEPENDENT re-implementation written from
Cameron & Miller (2015) eq. 10-12 directly in the test, not against the engine's own helpers.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from crp_engine.estimators import cohort_effects, ols_cluster_robust, pooled_effect
from crp_engine.manifest import Manifest
from crp_engine.panel import IdentificationMode, load_panel


# ------------------------------------------------------------------ independent CR1 reference

def _cr1_reference(X: np.ndarray, y: np.ndarray, clusters) -> tuple[np.ndarray, np.ndarray]:
    """Textbook CR1 sandwich, written straight from Cameron & Miller (2015) eq. 10-12."""
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    u = y - X @ beta
    labels = np.asarray(clusters, dtype=object)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in sorted(set(labels.tolist())):
        sel = labels == g
        s = X[sel].T @ u[sel]
        meat += np.outer(s, s)
    n, k = X.shape
    G = len(set(labels.tolist()))
    c = (G / (G - 1)) * ((n - 1) / (n - k))
    V = c * XtX_inv @ meat @ XtX_inv
    return beta, np.sqrt(np.diag(V))


def test_ols_recovers_an_exact_linear_relationship() -> None:
    """y = 3 + 2*t exactly -> beta = (3, 2), residuals 0, cluster-robust SE 0."""
    t = np.array([0.0, 1.0] * 6)
    y = 3.0 + 2.0 * t
    X = np.column_stack([np.ones(12), t])
    clusters = ["c%d" % (i // 2) for i in range(12)]
    fit = ols_cluster_robust(X, y, clusters, ["intercept", "treated"])
    assert fit.coef == pytest.approx([3.0, 2.0], abs=1e-12)
    assert fit.se == pytest.approx([0.0, 0.0], abs=1e-12)
    assert fit.n_clusters == 6


def test_cluster_robust_se_matches_independent_reference() -> None:
    rng = np.random.default_rng(4242)
    n_clusters, per = 25, 8
    rows, clusters = [], []
    for g in range(n_clusters):
        shock = rng.normal(0, 1.5)
        treat = float(g % 2)
        for _ in range(per):
            rows.append((1.0, treat, 4.0 - 0.7 * treat + shock + rng.normal(0, 0.4)))
            clusters.append("g%02d" % g)
    arr = np.array(rows)
    X, y = arr[:, :2], arr[:, 2]
    fit = ols_cluster_robust(X, y, clusters, ["intercept", "treated"])
    beta_ref, se_ref = _cr1_reference(X, y, clusters)
    assert fit.coef == pytest.approx(beta_ref.tolist(), rel=1e-10)
    assert fit.se == pytest.approx(se_ref.tolist(), rel=1e-9)
    assert fit.finite_sample_correction == pytest.approx(
        (n_clusters / (n_clusters - 1)) * ((n_clusters * per - 1) / (n_clusters * per - 2))
    )


def test_cluster_robust_se_exceeds_classical_when_clusters_share_noise() -> None:
    """The whole reason for clustering: cohort-shared noise inflates the true variance."""
    rng = np.random.default_rng(99)
    rows, clusters = [], []
    for g in range(30):
        shock = rng.normal(0, 2.0)  # large cohort-level shock
        treat = float(g % 2)
        for _ in range(20):
            rows.append((1.0, treat, 1.0 - 0.2 * treat + shock + rng.normal(0, 0.1)))
            clusters.append("g%02d" % g)
    arr = np.array(rows)
    X, y = arr[:, :2], arr[:, 2]
    clustered = ols_cluster_robust(X, y, clusters, ["intercept", "treated"]).get("treated")[1]
    unclustered = ols_cluster_robust(
        X, y, ["row%d" % i for i in range(len(y))], ["intercept", "treated"]
    ).get("treated")[1]
    # Theory: the ratio tends to sqrt(1 + (m-1)*rho) = sqrt(20) ~= 4.47 for m=20, rho ~= 1.
    assert clustered > 4 * unclustered


def test_needs_at_least_two_clusters() -> None:
    X = np.column_stack([np.ones(6), np.array([0.0, 1.0] * 3)])
    with pytest.raises(ValueError, match="at least|>= 2 clusters|needs"):
        ols_cluster_robust(X, np.arange(6.0), ["only"] * 6, ["intercept", "treated"])


# ------------------------------------------------------------------ known-true-effect recovery

def _switchback_panel(true_effect: float, *, n_cohorts=40, n_blocks=24, seed=1234) -> pd.DataFrame:
    """Within-cohort design with a KNOWN true effect on the raw outcome (RMSE, lower better)."""
    rng = np.random.default_rng(seed)
    rows = []
    for c in range(n_cohorts):
        cohort_shock = rng.normal(0, 0.5)
        phase = int(rng.integers(0, 2))
        for t in range(n_blocks):
            treated = ((t + phase) % 2) == 1
            y = 1.0 + cohort_shock - (true_effect if treated else 0.0) + rng.normal(0, 0.05)
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated else "control",
                    "outcome": y,
                    "n_units": 12,
                    "n_observations": 400,
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture
def within_manifest(manifest_obj):
    manifest_obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "5",
        "min_observations_per_cohort": "200",
        "min_time_blocks": "8",
        "min_eligible_cohorts": "10",
    }
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = []
    return Manifest.from_obj(manifest_obj)


@pytest.mark.parametrize("true_effect", [0.0, 0.05, 0.20])
def test_pooled_estimate_recovers_the_known_true_effect(within_manifest, true_effect) -> None:
    """Known-answer test on synthetic data: the estimate must sit within ~3 SE of the truth."""
    panel = load_panel(_switchback_panel(true_effect), within_manifest)
    assert panel.identification is IdentificationMode.WITHIN_COHORT
    b, se = pooled_effect(panel).get("treated")
    # The raw outcome is RMSE, so a beneficial effect is NEGATIVE on the raw metric.
    assert abs(b - (-true_effect)) < 3 * se + 1e-12


def test_null_effect_is_reported_as_null_not_massaged(within_manifest) -> None:
    """true effect 0 -> the conservative improvement bound must be 0 (Invariant 8)."""
    from crp_engine.reward_compiler import stage1_valuation

    panel = load_panel(_switchback_panel(0.0), within_manifest)
    effects = cohort_effects(panel)
    s1 = stage1_valuation(within_manifest, effects, panel.samples,
                          identification=panel.identification)
    positive = [c for c in s1.cohorts if c.conservative_s > 0]
    assert len(positive) <= 2, (
        "a true-zero effect produced %d cohorts with a positive conservative bound; "
        "the one-sided 95%% bound should almost never fire under the null" % len(positive)
    )


def test_per_cohort_effects_are_identified_within_cohort(within_manifest) -> None:
    panel = load_panel(_switchback_panel(0.15), within_manifest)
    effects = cohort_effects(panel)
    assert len(effects) == 40
    assert all(e.identified for e in effects.values())
    assert all(e.mode == "within_cohort" for e in effects.values())
    mean_effect = sum(e.effect for e in effects.values()) / len(effects)
    assert mean_effect == pytest.approx(-0.15, abs=0.03)


def test_whole_cohort_assignment_is_flagged_as_control_pool_identification(within_manifest) -> None:
    """Whole-cohort randomization gives NO within-cohort contrast — the engine must say so."""
    rng = np.random.default_rng(5)
    rows = []
    for c in range(30):
        treated = c % 2 == 0
        shock = rng.normal(0, 0.4)
        for t in range(12):
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated else "control",
                    "outcome": 1.0 + shock - (0.15 if treated else 0.0) + rng.normal(0, 0.05),
                    "n_units": 12,
                    "n_observations": 400,
                }
            )
    panel = load_panel(pd.DataFrame(rows), within_manifest)
    assert panel.identification is IdentificationMode.BETWEEN_COHORT_VS_CONTROL_POOL
    effects = cohort_effects(panel)
    # Control cohorts contributed no data: nothing to value.
    assert all(not e.identified for cid, e in effects.items() if int(cid[3:]) % 2 == 1)
    # Treated cohorts share one conservative between-cohort SE.
    treated_ses = {round(e.standard_error, 12) for cid, e in effects.items()
                   if int(cid[3:]) % 2 == 0}
    assert len(treated_ses) == 1
    assert next(iter(treated_ses)) > 0.0


def test_matched_stratum_effects(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "matched_cluster"
    manifest_obj["treatment"]["assignment_method"] = "matched_pair"
    manifest_obj["analysis_plan"]["estimator"] = "matched_pair_diff"
    manifest_obj["analysis_plan"]["standard_error_method"] = "matched_pair"
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = []
    manifest_obj["analysis_plan"]["minimum_sample"]["min_time_blocks"] = "8"
    manifest_obj["analysis_plan"]["minimum_sample"]["min_eligible_cohorts"] = "4"
    m = Manifest.from_obj(manifest_obj)

    rng = np.random.default_rng(77)
    rows = []
    for s in range(12):
        base = rng.normal(1.0, 0.3)
        for member in (0, 1):
            treated = member == 0
            for t in range(16):
                rows.append(
                    {
                        "cohort_id": "stratum%02d|%d" % (s, member),
                        "time_block": t,
                        "arm": "treatment" if treated else "control",
                        "outcome": base - (0.10 if treated else 0.0) + rng.normal(0, 0.03),
                        "n_units": 10,
                        "n_observations": 300,
                    }
                )
    panel = load_panel(pd.DataFrame(rows), m)
    assert panel.identification is IdentificationMode.MATCHED_STRATUM
    effects = cohort_effects(panel)
    treated_effects = [e.effect for cid, e in effects.items() if cid.endswith("|0")]
    assert sum(treated_effects) / len(treated_effects) == pytest.approx(-0.10, abs=0.02)


def test_observational_replay_is_never_identified(manifest_obj) -> None:
    manifest_obj["design"]["template"] = "observational_replay"
    manifest_obj["design"]["eligible_for_strong_causal_claim"] = False
    manifest_obj["analysis_plan"]["covariate_adjustment"] = []
    manifest_obj["analysis_plan"]["sensitivity_analyses"] = []
    m = Manifest.from_obj(manifest_obj)
    panel = load_panel(_switchback_panel(0.3), m)
    assert panel.identification is IdentificationMode.NOT_IDENTIFIED
    assert all(not e.identified for e in cohort_effects(panel).values())
