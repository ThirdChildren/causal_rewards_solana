"""Causal Rewards Protocol — causal engine.

Deterministic pipeline: frozen manifest + evidence bundle -> ``analysis.json`` +
``rewards.parquet`` + a reward Merkle root. Cohort-level estimand only; conservative
(lower-confidence-bound) valuation; null results are first-class outputs.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
