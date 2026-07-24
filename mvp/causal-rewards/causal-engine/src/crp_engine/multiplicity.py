"""Cross-cohort multiplicity corrections as a deterministic SELECTION LAYER.

The frozen reward policy tests each cohort independently with a one-sided 5% test and no
family-wise correction (``docs/m3-integration-and-spec-round.md`` §2). Over ~60 cohorts this
inflates the family-wise error rate: under a true null the fixed budget does not shrink, it
*concentrates* on the few cohorts that pass by chance (``s2_null_effect``: ~29.6% of budget to
2/60 cohorts). This module implements four candidate regimes over the per-cohort p-values so the
architect can rule on the tradeoff against real simulator data. It changes NO frozen default —
selection is fed to :func:`crp_engine.reward_compiler.stage1_valuation` only when a study asks.

Determinism (CLAUDE.md invariant 2). Every regime is a pure function of the p-value vector plus a
frozen ``alpha``. The p-value itself is a pure function of the already-quantized integer
``(improvement_s, se_s)`` — the *same* integers the frozen margin test consumes — so two
fresh-process runs select byte-identical sets. No wall-clock, no RNG, no dict/set-order
dependence: ordering ties are broken by ``cohort_id`` under a stable sort.

The reference distribution is the manifest's ``critical_value_reference = normal_approx``: the
one-sided lower test on prediction error maps to ``p = P(Z >= z)`` with ``z = improvement / se``.
At ``alpha = 0.05`` the ``none`` regime's ``p < alpha`` cut reproduces the frozen
``critical_value_micro = 1_645_000`` (``norm.sf(1.645) = 0.04998``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from scipy.stats import norm

__all__ = [
    "REGIMES",
    "one_sided_pvalue",
    "select_cohorts",
    "SelectionResult",
]

#: The regimes the §2.1 study compares. ``none`` is the current frozen default.
REGIMES: tuple[str, ...] = ("none", "bonferroni", "sidak", "benjamini_hochberg")

#: One-sided family-wise / FDR level. 0.05 == the frozen one-sided 5% test.
DEFAULT_ALPHA = 0.05


def one_sided_pvalue(improvement_s: int, se_s: int) -> float:
    """One-sided p-value for H0: improvement <= 0 vs H1: improvement > 0, ``normal_approx``.

    Consumes the SAME quantized integers the frozen Stage-1 margin test uses, so ``p < 0.05``
    agrees with ``conservative = improvement - 1.645*se > 0`` at the frozen critical value. A
    quantized ``se_s`` of 0 is degenerate: an exactly-zero SE makes any positive improvement
    infinitely significant (``p = 0``) and a non-positive one wholly insignificant (``p = 1``).
    """
    if se_s < 0:
        raise ValueError("se_s must be non-negative, got %d" % se_s)
    if se_s == 0:
        return 0.0 if improvement_s > 0 else 1.0
    z = improvement_s / se_s
    return float(norm.sf(z))


@dataclass(frozen=True)
class SelectionResult:
    """Which candidate cohorts a regime keeps, plus the audit trail behind the decision."""

    regime: str
    alpha: float
    family_size: int
    threshold: float          # the (effective) p cutoff a cohort had to beat; BH: the step-up cut
    selected: frozenset[str]
    pvalues: Mapping[str, float]


def _bh_cutoff(sorted_p: Sequence[float], m: int, alpha: float) -> float:
    """Benjamini-Hochberg (1995) step-up cutoff. ``sorted_p`` ascending, length ``m``.

    Largest ``k`` (1-based) with ``p_(k) <= (k/m)*alpha``; the cutoff is that ``p_(k)`` (or a
    negative sentinel selecting nobody). Deterministic: pure arithmetic over a sorted vector.
    """
    cutoff = -1.0
    for i, p in enumerate(sorted_p):  # i is 0-based; rank k = i+1
        if p <= ((i + 1) / m) * alpha:
            cutoff = p
    return cutoff


def select_cohorts(
    pvalues: Mapping[str, float],
    regime: str,
    *,
    alpha: float = DEFAULT_ALPHA,
) -> SelectionResult:
    """Apply ``regime`` to the candidate p-values; return the selected cohort ids.

    ``pvalues`` maps candidate cohort id -> its one-sided p-value. Candidates are exactly the
    cohorts a payout could reach under the frozen policy (eligible, identified, causal design);
    the family size ``m`` is ``len(pvalues)`` — the number of simultaneous tests. Ineligible /
    unidentified cohorts are already zeroed upstream and are not part of the family.
    """
    if regime not in REGIMES:
        raise ValueError("unknown regime %r; expected one of %s" % (regime, REGIMES))
    m = len(pvalues)
    items = sorted(pvalues.items(), key=lambda kv: (kv[1], kv[0]))  # stable: p then id
    if m == 0:
        return SelectionResult(regime, alpha, 0, 0.0, frozenset(), dict(pvalues))

    if regime == "none":
        thr = alpha
        selected = {cid for cid, p in items if p < thr}
    elif regime == "bonferroni":
        thr = alpha / m
        selected = {cid for cid, p in items if p < thr}
    elif regime == "sidak":
        thr = 1.0 - (1.0 - alpha) ** (1.0 / m)
        selected = {cid for cid, p in items if p < thr}
    elif regime == "benjamini_hochberg":
        sorted_p = [p for _, p in items]
        cut = _bh_cutoff(sorted_p, m, alpha)
        thr = cut
        # BH selects every hypothesis with p <= p_(k); the sentinel -1 selects nobody.
        selected = {cid for cid, p in items if cut >= 0.0 and p <= cut}
    else:  # pragma: no cover - guarded above
        raise AssertionError(regime)

    return SelectionResult(
        regime=regime,
        alpha=alpha,
        family_size=m,
        threshold=float(thr),
        selected=frozenset(selected),
        pvalues=dict(pvalues),
    )
