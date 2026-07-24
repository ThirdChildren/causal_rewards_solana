"""Multiplicity selection regimes + the §2.1 study.

Known-answer coverage for each regime (no simulator needed) plus a determinism / integration
check over the committed simulator artifacts. The frozen DEFAULT policy must be untouched: the
selection layer is inert when ``selected_cohorts=None`` (asserted here and, byte-for-byte, by the
existing golden + determinism gates).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from crp_engine.multiplicity import (
    DEFAULT_ALPHA,
    REGIMES,
    one_sided_pvalue,
    select_cohorts,
)

SRC = Path(__file__).resolve().parents[1] / "src"


# ------------------------------------------------------------------ p-values

def test_pvalue_matches_the_frozen_critical_value_boundary() -> None:
    # z = 1.645 == the frozen critical_value_micro=1_645_000; sf(1.645) ~= 0.04998 < 0.05.
    p = one_sided_pvalue(1_645_000, 1_000_000)
    assert 0.0499 < p < 0.0500
    # A far-significant improvement is tiny p; a non-positive improvement is p >= 0.5.
    assert one_sided_pvalue(10_000_000, 1_000_000) < 1e-6
    assert one_sided_pvalue(0, 1_000_000) == pytest.approx(0.5, abs=1e-9)
    assert one_sided_pvalue(-5_000_000, 1_000_000) > 0.5


def test_pvalue_degenerate_zero_se() -> None:
    assert one_sided_pvalue(1, 0) == 0.0        # any positive improvement, zero SE -> certain
    assert one_sided_pvalue(0, 0) == 1.0        # non-positive improvement, zero SE -> null
    with pytest.raises(ValueError):
        one_sided_pvalue(1, -1)


# ------------------------------------------------------------------ regime known answers

def _p() -> dict[str, float]:
    # 10 cohorts; five "signals" and five clear nulls. Deterministic ids.
    return {
        "c0": 0.001, "c1": 0.004, "c2": 0.010, "c3": 0.020, "c4": 0.030,
        "c5": 0.200, "c6": 0.400, "c7": 0.600, "c8": 0.800, "c9": 0.990,
    }


def test_none_reproduces_independent_five_percent() -> None:
    sel = select_cohorts(_p(), "none", alpha=0.05)
    assert sel.selected == {"c0", "c1", "c2", "c3", "c4"}  # all p < 0.05
    assert sel.threshold == 0.05


def test_bonferroni_uses_alpha_over_m() -> None:
    sel = select_cohorts(_p(), "bonferroni", alpha=0.05)
    assert sel.family_size == 10
    assert sel.threshold == pytest.approx(0.005)
    assert sel.selected == {"c0", "c1"}  # p < 0.005


def test_sidak_threshold_is_slightly_larger_than_bonferroni() -> None:
    b = select_cohorts(_p(), "bonferroni")
    s = select_cohorts(_p(), "sidak")
    assert s.threshold > b.threshold                     # Šidák cut is marginally larger
    assert s.selected >= b.selected                      # so weakly more power


def test_benjamini_hochberg_step_up_known_answer() -> None:
    # m=10, alpha=0.05. Sorted p: 0.001,0.004,0.010,0.020,0.030,...
    # (k/m)*alpha thresholds: k=1:0.005, k=2:0.010, k=3:0.015, k=4:0.020, k=5:0.025.
    # p_(k)<=thr at k=1(0.001<=0.005),k=2(0.004<=0.010),k=3(0.010<=0.015),k=4(0.020<=0.020);
    # k=5: 0.030<=0.025 false. Largest passing k=4 -> cutoff p_(4)=0.020 -> select p<=0.020.
    sel = select_cohorts(_p(), "benjamini_hochberg", alpha=0.05)
    assert sel.threshold == pytest.approx(0.020)
    assert sel.selected == {"c0", "c1", "c2", "c3"}


def test_bh_selects_nobody_under_a_flat_null() -> None:
    flat = {"a": 0.9, "b": 0.8, "c": 0.7}
    sel = select_cohorts(flat, "benjamini_hochberg")
    assert sel.selected == frozenset()
    assert sel.threshold < 0.0  # sentinel: no k qualifies


def test_bh_is_at_least_as_powerful_as_bonferroni() -> None:
    p = _p()
    assert select_cohorts(p, "benjamini_hochberg").selected >= select_cohorts(p, "bonferroni").selected


def test_empty_family_selects_nothing() -> None:
    for regime in REGIMES:
        sel = select_cohorts({}, regime)
        assert sel.selected == frozenset()
        assert sel.family_size == 0


def test_selection_is_order_independent() -> None:
    p = _p()
    a = select_cohorts(p, "benjamini_hochberg").selected
    b = select_cohorts(dict(reversed(list(p.items()))), "benjamini_hochberg").selected
    assert a == b


# ------------------------------------------------------------------ selection layer is inert by default

def test_selected_cohorts_none_is_the_frozen_behavior() -> None:
    """selected_cohorts=None must equal the shipped compilation, leaf-for-leaf."""
    from crp_engine.reward_compiler import compile_rewards
    from tests.conftest import SPEC_MANIFEST
    from crp_engine.manifest import Manifest
    from crp_engine.demo import write_demo
    import json, tempfile

    with tempfile.TemporaryDirectory() as d:
        spec = json.loads(SPEC_MANIFEST.read_text(encoding="utf-8"))
        seed = bytes.fromhex("00" * 24 + "0123456789abcdef")
        paths = write_demo(Path(d), spec, seed)
        m = Manifest.from_path(paths["manifest"])
        from crp_engine.run import analyze, load_participants

        run = analyze(m, paths["panel"], paths["participants"], seed=seed)
        prows = load_participants(paths["participants"])
        base = compile_rewards(
            m, run.effects, run.panel.samples, prows,
            identification=run.panel.identification,
        )
        explicit = compile_rewards(
            m, run.effects, run.panel.samples, prows,
            identification=run.panel.identification, selected_cohorts=None,
        )
        assert base.reward_root_hex == explicit.reward_root_hex == run.compilation.reward_root_hex


# ------------------------------------------------------------------ study integration + determinism

def _sim_ready() -> bool:
    repo = Path(__file__).resolve().parents[2]
    return (repo / "simulator" / "out" / "s2_null_effect" / "cohort_blocks.parquet").is_file()


@pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")
def test_study_runs_and_s2_waste_is_positive_and_bounded() -> None:
    from crp_engine.studies import run_study

    studies = {s.scenario: s for s in run_study()}
    s2 = studies["s2_null_effect"]
    assert s2.label == "true_null"
    none = next(c for c in s2.cells if c.regime == "none")
    # Under a true null the current policy DOES waste budget (the disclosed finding), and every
    # regime keeps deployment within the fixed budget.
    assert none.waste_ppm > 0
    for c in s2.cells:
        assert 0 <= c.deployed_ppm <= 1_000_000
        assert c.deployed_ppm + c.recovered_ppm == 1_000_000
        # A correction never increases the count of paid (null) cohorts vs none.
        assert c.n_paid <= none.n_paid


@pytest.mark.skipif(not _sim_ready(), reason="simulator outputs not generated")
def test_study_is_deterministic_across_fresh_processes() -> None:
    prog = (
        "import json;from crp_engine.studies import run_study,render_markdown;"
        "print(render_markdown(run_study()))"
    )

    def once(hashseed: str) -> str:
        import os

        env = dict(os.environ)
        env["PYTHONPATH"] = str(SRC)
        env["PYTHONHASHSEED"] = hashseed
        out = subprocess.run(
            [sys.executable, "-c", prog], env=env, capture_output=True, text=True
        )
        assert out.returncode == 0, out.stderr
        return out.stdout

    assert once("1") == once("99999")
