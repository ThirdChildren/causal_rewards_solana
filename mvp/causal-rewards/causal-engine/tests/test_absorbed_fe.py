"""Absorbed fixed effects: same coefficients as LSDV, but the WITHIN finite-sample correction.

Cameron & Miller (2015) §III.B: "Within and LSDV estimation lead to the same cluster-robust
standard errors if we apply formula (11) ... Differences arise, however, if we multiply by the
small-sample correction c given in (12). ... Within estimation leads to the correct finite-sample
correction." This test pins that behaviour so a future refactor cannot silently reintroduce the
LSDV (dummy-column) correction.
"""

from __future__ import annotations

import numpy as np
import pytest

from crp_engine.estimators import ols_cluster_robust


def _panel(n_groups=10, per=6, seed=17):
    rng = np.random.default_rng(seed)
    treat, y, groups = [], [], []
    for g in range(n_groups):
        fe = rng.normal(0, 3.0)  # large group fixed effect
        for t in range(per):
            d = float(t % 2)
            treat.append(d)
            y.append(fe + 0.5 * d + rng.normal(0, 0.2))
            groups.append("g%02d" % g)
    return np.asarray(treat), np.asarray(y), groups


def test_absorbed_and_lsdv_coefficients_agree() -> None:
    treat, y, groups = _panel()
    absorbed = ols_cluster_robust(
        treat.reshape(-1, 1), y, groups, ["treated"], absorb=groups
    )
    levels = sorted(set(groups))[1:]
    arr = np.asarray(groups, dtype=object)
    dummies = [(arr == lv).astype(float) for lv in levels]
    X = np.column_stack([np.ones(len(y)), treat, *dummies])
    names = ["intercept", "treated"] + ["fe:%s" % lv for lv in levels]
    lsdv = ols_cluster_robust(X, y, groups, names)
    assert absorbed.get("treated")[0] == pytest.approx(lsdv.get("treated")[0], rel=1e-9)


def test_absorbed_uses_the_within_correction_not_the_lsdv_one() -> None:
    treat, y, groups = _panel()
    n = len(y)
    G = len(set(groups))
    absorbed = ols_cluster_robust(
        treat.reshape(-1, 1), y, groups, ["treated"], absorb=groups
    )
    # Within: K = 1 (just `treated`; the within model has no intercept).
    assert absorbed.n_params == 1
    assert absorbed.n_absorbed_groups == G
    assert absorbed.finite_sample_correction == pytest.approx((G / (G - 1)) * ((n - 1) / (n - 1)))

    levels = sorted(set(groups))[1:]
    arr = np.asarray(groups, dtype=object)
    X = np.column_stack(
        [np.ones(n), treat, *[(arr == lv).astype(float) for lv in levels]]
    )
    lsdv = ols_cluster_robust(
        X, y, groups, ["intercept", "treated"] + ["fe:%s" % lv for lv in levels]
    )
    # LSDV inflates K by the G-1 dummies and therefore inflates c — the wrong correction.
    assert lsdv.finite_sample_correction > absorbed.finite_sample_correction
    assert lsdv.get("treated")[1] > absorbed.get("treated")[1]


def test_absorb_rejects_an_explicit_intercept() -> None:
    treat, y, groups = _panel()
    X = np.column_stack([np.ones(len(y)), treat])
    with pytest.raises(ValueError, match="intercept"):
        ols_cluster_robust(X, y, groups, ["intercept", "treated"], absorb=groups)


def test_demeaning_is_order_independent() -> None:
    from crp_engine.estimators import _demean

    treat, y, groups = _panel()
    order = np.argsort(np.asarray([hash(g) for g in groups]))  # arbitrary permutation
    a = _demean(y, groups)
    b = _demean(y[order], [groups[i] for i in order])
    assert a[order].tolist() == b.tolist()
