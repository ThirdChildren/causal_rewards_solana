"""Determinism gate (CLAUDE.md invariant #2 — the primary acceptance criterion).

Same frozen config + committed seed MUST reproduce the identical content hash, and every
generated table byte-for-byte, across independent runs.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from depin_sim.config import load_scenario, scenario_from_dict
from depin_sim.run import run_scenario

SCENARIO_DIR = Path(__file__).resolve().parents[1] / "scenarios"
BASELINE = SCENARIO_DIR / "baseline_alpha.json"
ALL_SCENARIOS = sorted(SCENARIO_DIR.glob("*.json"))


def test_same_seed_same_hash():
    cfg = load_scenario(BASELINE)
    r1 = run_scenario(cfg)
    r2 = run_scenario(cfg)
    assert r1.content_hash == r2.content_hash


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda p: p.stem)
def test_every_scenario_is_deterministic(scenario):
    cfg = load_scenario(scenario)
    assert run_scenario(cfg).content_hash == run_scenario(cfg).content_hash


def test_tables_are_bytewise_stable():
    cfg = load_scenario(BASELINE)
    r1 = run_scenario(cfg)
    r2 = run_scenario(cfg)
    for name in ("sensors", "cells", "cohort_blocks"):
        t1 = r1.artifact["content"][name]
        t2 = r2.artifact["content"][name]
        assert t1.keys() == t2.keys()
        for col in t1:
            np.testing.assert_array_equal(t1[col], t2[col])


def test_different_seed_changes_hash():
    base = load_scenario(BASELINE).to_dict()
    a = scenario_from_dict({**base, "seed": "0x01"})
    b = scenario_from_dict({**base, "seed": "0x02"})
    assert run_scenario(a).content_hash != run_scenario(b).content_hash


def test_fresh_process_hash_matches_committed_golden(tmp_path):
    """Cross-process reproduction: a subprocess must print the same hash as in-process."""
    import subprocess
    import sys

    in_proc = run_scenario(load_scenario(BASELINE)).content_hash
    root = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, "-m", "depin_sim.cli", "hash", "--scenario", str(BASELINE)],
        cwd=root,
        env={"PYTHONPATH": str(root / "src"), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.stdout.strip() == in_proc
