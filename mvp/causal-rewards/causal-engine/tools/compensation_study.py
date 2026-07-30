#!/usr/bin/env python
"""Regenerate ``docs/compensation-study.md`` deterministically.

Thin wrapper over :func:`crp_engine.studies.main_compensation`. Answers the treasury owner's
CONDITION 1: measure how much genuine signal is PAID (not just detected) before fixing the
recommended reward curve. Run from the causal-engine directory:

    python tools/compensation_study.py

Requires the committed simulator outputs under ``simulator/out/<scenario>/``. Same artifacts +
committed seed => identical numbers across fresh processes (CLAUDE.md invariant 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crp_engine.studies import main_compensation  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main_compensation())
