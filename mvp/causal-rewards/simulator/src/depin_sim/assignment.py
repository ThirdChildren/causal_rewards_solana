"""Cohort treatment assignment — ISOLATED behind one function so it can later be swapped
for the canonical seed->assignment derivation ratified by verifier-reproducibility-engineer.

Contract (do not break when swapping in the canonical rule):
    assign(cfg, net, rng) -> Assignment
where ``rng`` exposes the "assignment" stream derived from the committed seed. The returned
object is a treated-mask over (cell, time_block) plus per-unit eligibility flags for guard
bands / carryover, all fully determined by (cfg, committed seed).

ALPHA derivation (placeholder, clearly marked): we draw a permutation / Bernoulli from the
seeded "assignment" numpy stream. The canonical protocol rule will instead hash the revealed
seed with a domain separator per unit and threshold the digest — same interface, stronger
auditability. Keep all assignment logic in THIS module.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from depin_sim.config import ScenarioConfig
from depin_sim.network import Network, neighbor_cells
from depin_sim.seeds import RngBundle

# Marks the placeholder derivation. verifier-reproducibility-engineer replaces the body of
# ``_assign_core`` with the ratified hash-and-threshold rule; the interface stays fixed.
ALPHA_DERIVATION = "numpy-permutation-v0"


@dataclass(frozen=True)
class Assignment:
    treated: np.ndarray      # bool [n_cells, n_time_blocks]; True == cohort data included
    eligible: np.ndarray     # bool [n_cells, n_time_blocks]; False == dropped (guard/carryover)
    design: str
    derivation: str

    @property
    def shape(self) -> tuple[int, int]:
        return self.treated.shape


def _assign_cluster_randomized(cfg: ScenarioConfig, net: Network, g: np.random.Generator) -> np.ndarray:
    """Whole-cohort assignment: each cell is treated or control for ALL time blocks."""
    n = net.n_cells
    n_treat = int(round(cfg.treatment_fraction * n))
    treated_cells = np.zeros(n, dtype=bool)
    if 0 < n_treat < n:
        idx = np.sort(g.choice(n, size=n_treat, replace=False))
        treated_cells[idx] = True
    treated = np.repeat(treated_cells[:, None], cfg.n_time_blocks, axis=1)
    return treated


def _assign_switchback(cfg: ScenarioConfig, net: Network, g: np.random.Generator) -> np.ndarray:
    """Switchback: each cohort flips treatment across time blocks independently."""
    p = cfg.treatment_fraction
    treated = g.random(size=(net.n_cells, cfg.n_time_blocks)) < p
    return treated


def _assign_matched_cluster(cfg: ScenarioConfig, net: Network, g: np.random.Generator) -> np.ndarray:
    """Matched-cluster: pair cells by info-value (a frozen matching covariate), randomize
    one of each pair to treatment. Improves balance in heterogeneous networks."""
    order = np.argsort(net.cell_info_value, kind="stable")
    treated_cells = np.zeros(net.n_cells, dtype=bool)
    for i in range(0, len(order) - 1, 2):
        a, b = order[i], order[i + 1]
        if g.random() < 0.5:
            treated_cells[a] = True
        else:
            treated_cells[b] = True
    treated = np.repeat(treated_cells[:, None], cfg.n_time_blocks, axis=1)
    return treated


def _assign_observational(cfg: ScenarioConfig, net: Network, g: np.random.Generator) -> np.ndarray:
    """Observational replay: NO randomization. Inclusion propensity is driven by cell info
    value (a proxy for demand/supply), so treatment is CONFOUNDED with the outcome. This is
    discovery-only and not eligible for the strongest causal claim (concept note 6.3)."""
    # Higher info-value cells are more likely to have been "included" historically.
    logit = 2.0 * (net.cell_info_value - net.cell_info_value.mean())
    prob = 1.0 / (1.0 + np.exp(-logit))
    treated_cells = g.random(size=net.n_cells) < prob
    treated = np.repeat(treated_cells[:, None], cfg.n_time_blocks, axis=1)
    return treated


_DISPATCH = {
    "cluster_randomized": _assign_cluster_randomized,
    "cluster_switchback": _assign_switchback,
    "matched_cluster": _assign_matched_cluster,
    "observational_replay": _assign_observational,
}


def _assign_core(cfg: ScenarioConfig, net: Network, g: np.random.Generator) -> np.ndarray:
    return _DISPATCH[cfg.design](cfg, net, g)


def _apply_guard_and_carryover(cfg: ScenarioConfig, net: Network, treated: np.ndarray) -> np.ndarray:
    """Compute eligibility: drop units contaminated by spillover (guard bands) or by a
    recent treatment flip (switchback carryover). Surfacing interference, not hiding it."""
    eligible = np.ones_like(treated, dtype=bool)

    # Guard bands: a control cell adjacent to a treated cell in the same block is dropped.
    if cfg.guard_band_cells > 0:
        nbrs = [neighbor_cells(net, i, radius=cfg.guard_band_cells) for i in range(net.n_cells)]
        for t in range(cfg.n_time_blocks):
            for i in range(net.n_cells):
                if treated[i, t]:
                    continue
                if any(treated[j, t] for j in nbrs[i]):
                    eligible[i, t] = False

    # Carryover: the first ``carryover_blocks`` after any treatment flip are dropped.
    if cfg.carryover_blocks > 0 and cfg.n_time_blocks > 1:
        for i in range(net.n_cells):
            for t in range(1, cfg.n_time_blocks):
                if treated[i, t] != treated[i, t - 1]:
                    hi = min(cfg.n_time_blocks, t + cfg.carryover_blocks)
                    eligible[i, t:hi] = False

    return eligible


def assign(cfg: ScenarioConfig, net: Network, rng: RngBundle) -> Assignment:
    cfg.validate()
    g = rng.stream("assignment")
    treated = _assign_core(cfg, net, g)
    eligible = _apply_guard_and_carryover(cfg, net, treated)
    return Assignment(
        treated=treated,
        eligible=eligible,
        design=cfg.design,
        derivation=ALPHA_DERIVATION,
    )
