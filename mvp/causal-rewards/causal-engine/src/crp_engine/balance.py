"""Covariate balance checks (guardrail, reported — never a payout gate).

Balance is measured by the **standardized mean difference** (SMD), the standard randomization
diagnostic:

    SMD_x = ( mean(x | treated) - mean(x | control) ) / sqrt( ( var_t(x) + var_c(x) ) / 2 )

with the *pooled* denominator (Austin 2009's recommended form; the pooled SD is deliberately NOT
recomputed under the treatment assignment, so the diagnostic does not move with the outcome).
The conventional threshold is |SMD| <= 0.1; the manifest may freeze it as
``design.parameters.balance_check = "standardized_mean_difference_max_<micro>"``.

**Balance failure does not zero a payout.** The frozen payout gates are exactly two
(``reward-policy.md`` Stage 1 step 3/4): the minimum-sample rule and a conservative lower bound
<= 0. Adding an unfrozen third gate after seeing the data would violate Invariant 1. A balance
failure is therefore surfaced loudly in ``analysis.json`` and is grounds for a challenge, not a
silent adjustment.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd

from crp_engine import numeric as nm

__all__ = ["BalanceItem", "BalanceReport", "DEFAULT_SMD_THRESHOLD_MICRO", "balance_report"]

#: |SMD| <= 0.1 — the conventional cut-off, micro-scaled.
DEFAULT_SMD_THRESHOLD_MICRO = 100_000

_THRESH_RE = re.compile(r"standardized_mean_difference_max_(\d+)")


@dataclass(frozen=True)
class BalanceItem:
    name: str
    mean_treated: float
    mean_control: float
    smd: float
    n_treated: int
    n_control: int
    passed: bool


@dataclass(frozen=True)
class BalanceReport:
    threshold_micro: int
    items: tuple[BalanceItem, ...]
    passed: bool
    max_abs_smd: float
    arm_share_treated_micro: int


def threshold_micro(balance_check: str | None) -> int:
    """Parse the frozen balance threshold, defaulting to the conventional 0.1."""
    if not balance_check:
        return DEFAULT_SMD_THRESHOLD_MICRO
    m = _THRESH_RE.search(balance_check)
    return int(m.group(1)) if m else DEFAULT_SMD_THRESHOLD_MICRO


def _smd(t: Sequence[float], c: Sequence[float]) -> float:
    if len(t) == 0 or len(c) == 0:
        return 0.0
    mt, mc = nm.fsum(t) / len(t), nm.fsum(c) / len(c)
    vt, vc = nm.sample_variance(t), nm.sample_variance(c)
    denom = math.sqrt((vt + vc) / 2.0)
    if denom == 0.0:
        return 0.0 if mt == mc else math.inf
    return (mt - mc) / denom


def balance_report(
    frame: pd.DataFrame,
    covariates: Sequence[str],
    *,
    balance_check: str | None = None,
) -> BalanceReport:
    """SMD balance for each frozen covariate, plus exposure-size proxies.

    ``n_units`` and ``n_observations`` are always checked: an imbalance in *how much data* the
    arms carry is a first-order threat in a DePIN panel (it is how Sybil inflation and demand
    shifts show up), so it is checked even when the manifest freezes no covariate list.
    """
    thr_micro = threshold_micro(balance_check)
    thr = thr_micro / 1e6
    treated = frame["arm"].to_numpy() == "treatment"
    names = [c for c in covariates if c in frame.columns]
    for extra in ("n_units", "n_observations"):
        if extra in frame.columns and extra not in names:
            names.append(extra)

    items: list[BalanceItem] = []
    for name in sorted(names):
        col = frame[name].to_numpy(dtype=np.float64)
        t = col[treated].tolist()
        c = col[~treated].tolist()
        smd = _smd(t, c)
        items.append(
            BalanceItem(
                name=name,
                mean_treated=(nm.fsum(t) / len(t)) if t else 0.0,
                mean_control=(nm.fsum(c) / len(c)) if c else 0.0,
                smd=smd,
                n_treated=len(t),
                n_control=len(c),
                passed=abs(smd) <= thr,
            )
        )
    max_abs = max((abs(i.smd) for i in items), default=0.0)
    n = len(frame)
    share = nm.round_half_even_div(int(treated.sum()) * 1_000_000, n) if n else 0
    return BalanceReport(
        threshold_micro=thr_micro,
        items=tuple(items),
        passed=all(i.passed for i in items),
        max_abs_smd=max_abs,
        arm_share_treated_micro=share,
    )
