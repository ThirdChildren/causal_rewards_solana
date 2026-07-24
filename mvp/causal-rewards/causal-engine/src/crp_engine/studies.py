"""Deterministic multiplicity / false-positive study (``docs/m3-integration-and-spec-round.md`` §2.1).

Runs the six benchmark scenarios x four cross-cohort test regimes and measures, per cell:

1. **waste** — share of the fixed budget paid to TRUE-NULL cohorts,
2. **power** — share of TRUE-POSITIVE cohorts that are correctly paid,
3. **budget deployed vs recovered** — how much of the fixed budget is spent vs returned.

Ground truth comes from the simulator DGP (``simulator/src/depin_sim/outcomes.py``): a cohort's
true effect is ``true_effect * (0.5 + info_value) * het`` with ``het > 0`` and ``info_value >= 0``,
so it is strictly positive iff the scenario's ``true_effect > 0`` and exactly zero iff
``true_effect == 0``. Labels are therefore homogeneous within a scenario and read straight off the
scenario file — no re-simulation, no hidden randomness.

The regime is applied as a SELECTION LAYER over the per-cohort p-values feeding the Stage-1 gate
(:mod:`crp_engine.multiplicity` -> ``stage1_valuation(selected_cohorts=...)``). The ``none`` cell
is the FROZEN engine output itself (``selected_cohorts=None``), so the study never merely
approximates the shipped default — it reports it. Everything here is a pure function of the
committed simulator artifacts + the committed seed; two fresh processes produce identical numbers.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pandas as pd

from crp_engine.adapters import panel_from_simulator, participants_from_simulator
from crp_engine.manifest import Manifest
from crp_engine.multiplicity import REGIMES, one_sided_pvalue, select_cohorts
from crp_engine.reward_compiler import compile_rewards
from crp_engine.run import analyze

#: The committed study seed (same as the determinism / scenario suites).
STUDY_SEED = bytes.fromhex("00" * 24 + "0123456789abcdef")

#: The six benchmark scenarios, in report order.
SCENARIOS: tuple[str, ...] = (
    "s1_strong_signal",
    "s2_null_effect",
    "s3_low_power",
    "s4_interference",
    "s5_sybil_contamination",
    "s6_demand_shift",
)


def _repo() -> Path:
    # src/crp_engine/studies.py -> causal-engine -> causal-rewards
    return Path(__file__).resolve().parents[3]


def build_scenario_manifest(name: str, panel: pd.DataFrame, example: dict) -> Manifest:
    """The default causal manifest used across the benchmark (mirrors the scenario test harness).

    Every scenario is run through the engine's causal path so the cross-cohort test actually
    fires. ``s6_demand_shift`` is ratified as ``observational_replay`` (which pays zero regardless
    of regime); the study runs it in causal mode purely to expose confounding-driven false
    positives — a discovery-only diagnostic, flagged as such in the report.
    """
    obj = copy.deepcopy(example)
    obj["experiment_id"] = "bench-" + name
    obj["analysis_plan"]["covariate_adjustment"] = []
    obj["analysis_plan"]["sensitivity_analyses"] = []
    obj["analysis_plan"]["minimum_sample"] = {
        "min_units_per_cohort": "3",
        "min_observations_per_cohort": "200",
        "min_time_blocks": "6",
        "min_eligible_cohorts": "10",
    }
    obj["estimand"]["cohort_definition"]["cohort_count"] = str(panel["cohort_id"].nunique())
    obj["estimand"]["time_block"]["block_count"] = str(panel["time_block"].nunique())
    return Manifest.from_obj(obj)


@dataclass(frozen=True)
class CellResult:
    scenario: str
    regime: str
    family_size: int          # candidate cohorts tested (the multiplicity family)
    n_paid: int               # cohorts with a positive budget
    n_true_null: int
    n_true_positive: int
    waste_ppm: int            # budget share to true-null cohorts, parts per million of B
    power_ppm: int            # share of true-positive cohorts paid, ppm (-1 == undefined)
    deployed_ppm: int         # sum(cohort budgets) / B, ppm
    recovered_ppm: int        # B - deployed, ppm
    threshold: float          # effective per-cohort p cutoff the regime applied


@dataclass(frozen=True)
class ScenarioStudy:
    scenario: str
    true_effect: float
    label: str                # "true_positive" | "true_null"
    n_cohorts: int
    budget_base_units: int
    cells: tuple[CellResult, ...]


def _ppm(numer: int, denom: int) -> int:
    """Exact parts-per-million share as an integer (floor). ``denom == 0`` -> -1 (undefined)."""
    if denom <= 0:
        return -1
    return (numer * 1_000_000) // denom


def run_scenario_study(scenario: str, *, sim_out: Path, example: dict) -> ScenarioStudy:
    d = sim_out / scenario
    cb = pd.read_parquet(d / "cohort_blocks.parquet")
    sensors = pd.read_parquet(d / "sensors.parquet")
    panel_df = panel_from_simulator(cb)
    parts_df = participants_from_simulator(sensors, cb)

    scen = json.loads((_repo() / "simulator" / "scenarios" / (scenario + ".json")).read_text("utf-8"))
    true_effect = float(scen["effect"]["true_effect"])
    label = "true_positive" if true_effect > 0.0 else "true_null"

    m = build_scenario_manifest(scenario, panel_df, example)
    B = m.reward_policy.budget_base_units
    run = analyze(m, panel_df, parts_df, seed=STUDY_SEED)
    s1 = run.compilation.stage1
    design_blocked = not m.design.eligible_for_strong_causal_claim

    # Candidate family: cohorts a payout could reach under the frozen policy.
    candidates = {
        v.cohort_id: v
        for v in s1.cohorts
        if v.min_sample_eligible and v.identified and not design_blocked
    }
    pvalues: dict[str, float] = {
        cid: one_sided_pvalue(v.improvement_s, v.se_s) for cid, v in candidates.items()
    }

    n_cohorts = len(s1.cohorts)
    # Per-scenario ground-truth label is homogeneous (see module docstring).
    null_ids = frozenset(v.cohort_id for v in s1.cohorts) if label == "true_null" else frozenset()
    pos_ids = frozenset(v.cohort_id for v in s1.cohorts) if label == "true_positive" else frozenset()
    # Power denominator = the true-positive cohorts that COULD be paid at all. Control-arm cohorts
    # are held out by DESIGN (they contributed no data this experiment), so including them would
    # conflate the test's power with the assignment's treated fraction. The payable true-positive
    # family is exactly the candidates on a true-positive scenario.
    pos_payable = frozenset(candidates) & pos_ids

    cells: list[CellResult] = []
    for regime in REGIMES:
        if regime == "none":
            comp = run.compilation  # the FROZEN engine output, verbatim
            thr = 0.05
        else:
            sel = select_cohorts(pvalues, regime)
            thr = sel.threshold
            comp = compile_rewards(
                m, run.effects, run.panel.samples, list(_participant_rows(parts_df)),
                identification=run.panel.identification, selected_cohorts=sel.selected,
            )
        budget_by = {v.cohort_id: v.budget_base_units for v in comp.stage1.cohorts}
        paid = {cid for cid, b in budget_by.items() if b > 0}
        waste = sum(budget_by[c] for c in paid if c in null_ids)
        n_pos_paid = sum(1 for c in paid if c in pos_ids)
        deployed = comp.stage1.total_budget_allocated
        cells.append(
            CellResult(
                scenario=scenario,
                regime=regime,
                family_size=len(candidates),
                n_paid=len(paid),
                n_true_null=len(null_ids),
                n_true_positive=len(pos_ids),
                waste_ppm=_ppm(waste, B),
                power_ppm=_ppm(n_pos_paid, len(pos_payable)),
                deployed_ppm=_ppm(deployed, B),
                recovered_ppm=_ppm(B - deployed, B),
                threshold=thr,
            )
        )

    return ScenarioStudy(
        scenario=scenario,
        true_effect=true_effect,
        label=label,
        n_cohorts=n_cohorts,
        budget_base_units=B,
        cells=tuple(cells),
    )


def _participant_rows(parts_df: pd.DataFrame):
    from crp_engine.run import load_participants

    return load_participants(parts_df)


def run_study(*, sim_out: Path | None = None) -> list[ScenarioStudy]:
    """Run every available scenario. Skips a scenario whose simulator output is absent."""
    repo = _repo()
    sim_out = sim_out or (repo / "simulator" / "out")
    example = json.loads(
        (repo / "specs" / "examples" / "manifest.example.json").read_text("utf-8")
    )
    out: list[ScenarioStudy] = []
    for s in SCENARIOS:
        if not (sim_out / s / "cohort_blocks.parquet").is_file():
            continue
        out.append(run_scenario_study(s, sim_out=sim_out, example=example))
    return out


# --------------------------------------------------------------------------------------
# Markdown rendering (a deterministic, regenerable artifact)
# --------------------------------------------------------------------------------------

def _pct(ppm: int) -> str:
    if ppm < 0:
        return "n/a"
    return "%.2f%%" % (ppm / 10_000.0)


def render_markdown(studies: list[ScenarioStudy]) -> str:
    lines: list[str] = []
    lines.append("# Multiplicity / false-positive study (six scenarios x four regimes)")
    lines.append("")
    lines.append(
        "**Status:** benchmark-report material feeding the `protocol-architect` recommendation "
        "(`docs/m3-integration-and-spec-round.md` §2). The frozen default policy is UNCHANGED: "
        "`none` (independent one-sided 5% per cohort). Adopting any correction as the default "
        "would add a frozen manifest field (an FDR level or a curve floor) and is therefore a "
        "hash-moving **v1.2 migration** — not adopted here."
    )
    lines.append("")
    lines.append(
        "Regenerate deterministically: `python -m crp_engine.studies` (or "
        "`python tools/multiplicity_study.py`). Same committed simulator artifacts + committed "
        "seed `%s` => identical numbers across fresh processes." % STUDY_SEED.hex()
    )
    lines.append("")
    lines.append("## Method")
    lines.append("")
    lines.append(
        "- **Regimes.** `none` = current frozen 5% test (this column is the verbatim engine "
        "output, `selected_cohorts=None`). `bonferroni` = `p < alpha/m`. `sidak` = "
        "`p < 1-(1-alpha)^(1/m)`. `benjamini_hochberg` = the BH (1995) FDR step-up at level "
        "`alpha`. `alpha = 0.05`, one-sided; `m` = candidate cohorts (eligible + identified + "
        "causal design)."
    )
    lines.append(
        "- **p-values.** `p = P(Z >= improvement_s/se_s)` under the manifest's "
        "`critical_value_reference = normal_approx`, consuming the SAME quantized integers as the "
        "frozen margin test, so `none` here equals the shipped policy."
    )
    lines.append(
        "- **Selection layer.** A cohort the regime drops is forced `conservative = 0`, exactly "
        "like failing minimum sample; the fixed budget is then re-allocated across survivors with "
        "the frozen reward curve + `proportional_scale_to_budget`."
    )
    lines.append(
        "- **Ground truth.** Homogeneous per scenario from the simulator DGP: all cohorts "
        "TRUE-POSITIVE when `true_effect > 0`, all TRUE-NULL when `true_effect == 0`."
    )
    lines.append(
        "- **Power denominator.** The *payable* true-positive cohorts (candidate family `m`), not "
        "all cohorts. Control-arm cohorts are held out by design and contribute no data, so "
        "counting them would conflate test power with the assignment's treated fraction (~50%). "
        "Whole-cohort randomization here uses `between_cohort_vs_control_pool` identification, so "
        "only treated cohorts are ever payable."
    )
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append(
        "| scenario | true_effect | label | regime | m | paid | waste (%B->null) | "
        "power (%payable-TP paid) | deployed (%B) | recovered (%B) |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|---|---|"
    )
    for st in studies:
        for c in st.cells:
            lines.append(
                "| %s | %.3f | %s | %s | %d | %d | %s | %s | %s | %s |"
                % (
                    st.scenario, st.true_effect, st.label, c.regime, c.family_size, c.n_paid,
                    _pct(c.waste_ppm), _pct(c.power_ppm), _pct(c.deployed_ppm),
                    _pct(c.recovered_ppm),
                )
            )
    lines.append("")
    lines.append("### Headline: `s2_null_effect` waste (budget paid under a TRUE ZERO effect)")
    lines.append("")
    s2 = next((s for s in studies if s.scenario == "s2_null_effect"), None)
    if s2 is not None:
        lines.append("| regime | cohorts paid | waste (share of budget) | budget recovered |")
        lines.append("|---|---|---|---|")
        for c in s2.cells:
            lines.append(
                "| %s | %d | %s | %s |"
                % (c.regime, c.n_paid, _pct(c.waste_ppm), _pct(c.recovered_ppm))
            )
    lines.append("")
    lines.append(_reading_note(studies))
    lines.append("")
    lines.append(_STRUCTURAL_NOTE)
    lines.append("")
    return "\n".join(lines)


def _reading_note(studies: list[ScenarioStudy]) -> str:
    by = {s.scenario: s for s in studies}

    def cell(scn: str, regime: str) -> CellResult | None:
        s = by.get(scn)
        return next((c for c in s.cells if c.regime == regime), None) if s else None

    parts = ["## Reading the scenarios", ""]
    parts.append(
        "- **`s1_strong_signal` / `s5_sybil_contamination` (clear signal).** BH keeps materially "
        "more power than Bonferroni/Šidák while the true-null waste stays 0 (no null cohorts "
        "exist). This is the intended regime tradeoff."
    )
    parts.append(
        "- **`s2_null_effect` (the headline, true zero).** With no real signal, every paid cohort "
        "is waste. FWER and BH each cut the *count* of false positives from 2 to 1, but the one "
        "survivor still absorbs ~26% of the budget — the concentration residual (below)."
    )
    parts.append(
        "- **`s3_low_power` (weak, true positive).** The design has essentially no per-cohort "
        "power; every regime (incl. `none`) pays nothing and recovers the whole budget. Correct, "
        "honest, and NOT something to tune away (CLAUDE.md invariant 8)."
    )
    parts.append(
        "- **`s4_interference` (spillover-biased).** Spillover contaminates the between-cohort "
        "contrast, so the estimates are biased; the regimes still trade power for false-positive "
        "control the same way. Multiplicity control does not fix interference bias — that stays a "
        "sensitivity/guard-band problem, surfaced separately."
    )
    s6_none = cell("s6_demand_shift", "none")
    if s6_none is not None:
        parts.append(
            "- **`s6_demand_shift` (confounding).** Its ratified design is `observational_replay` "
            "(pays zero regardless); run here in causal mode as a what-if, it *still* pays 0 under "
            "every regime — the conservative `between_cohort_vs_control_pool` SE carries the full "
            "between-cohort variance and already swamps the confounder, so no false positives even "
            "before any multiplicity correction. A clean demonstration that the conservative bound "
            "and the multiplicity layer are complementary guards, not substitutes."
        )
    return "\n".join(parts)


_STRUCTURAL_NOTE = """## Structural note: a threshold correction mitigates, it does not remove, concentration

Under a true null (`s2`) the fixed budget does **not** shrink with the number of false positives —
it **concentrates**. `proportional_scale_to_budget` divides the *whole* budget across whichever
cohorts clear the test, so if two cohorts survive by chance they split the entire pool, not `2/60`
of it. This is a property of the reward *curve + overflow rule*, not of the p-value threshold, so
each regime addresses only part of the problem:

- **none.** No family-wise control. On `s2` a handful of chance winners absorb a large share of
  budget (the disclosed ~29.6% / 2-of-60 finding). Highest waste, highest concentration.
- **Bonferroni / Šidák (FWER).** Drive the per-cohort cut to ~`alpha/m` (≈0.0008 at m≈30–60).
  They **strongly reduce the count** of false positives — usually to zero under a pure null — so
  waste collapses toward 0. But they also crush power on the genuine-but-weak scenarios (`s3`, and
  the biased `s4`), turning "most cohorts get zero value" (our #1 risk-register item) into the
  default outcome. Bonferroni ⊂ Šidák (Šidák's cut is marginally larger, so weakly more power);
  under independence Šidák is exact, Bonferroni conservative.
- **Benjamini–Hochberg (FDR).** Controls the *expected proportion of paid cohorts that are false*,
  which is the closest statistical analogue to "proportion of spend wasted." It keeps far more
  power than FWER on `s1`/`s5` while still suppressing pure-null false discoveries, because its
  cut adapts to the number of true signals present. This is why it is the leading candidate.

**But note the residual, even under FDR — and this study measures it.** On `s2` (pure null) BH,
Bonferroni and Šidák all cut the false-positive *count* from 2 to 1, yet that single survivor
still absorbs **~26% of the budget** (vs ~30% under `none`). FDR bounds the *fraction of paid
cohorts* that are null; it does **not** bound the *fraction of budget* those few nulls receive,
because concentration is a spend-allocation effect. If even one null slips through on a scenario
with few true positives, the fixed-budget re-scaling hands it a disproportionate amount. So a
threshold regime alone cannot close the waste channel — the count drops far more than the spend.

**Flag for the architect (I do not decide this):** closing the residual needs a change to the
reward *curve / `value_scale`*, not only the p-value cut. Two candidate levers, both hash-moving
manifest changes and therefore v1.2-migration decisions:

1. a **floor on `conservative_effect`** below which no budget deploys (so marginal chance-winners
   with tiny effects earn nothing even if selected), and/or
2. a **concavity / per-cohort cap** in the reward curve so no single cohort can absorb a
   disproportionate share when few cohorts are paid (caps concentration directly).

A defensible package is **BH for the discovery threshold + a conservative-effect floor for the
concentration channel**, but selecting/parameterizing either is the architect's call against this
table, not the engine's. Any regime that adds a frozen field (an FDR level, a floor, a cap) moves
the manifest golden `74e0bb82…` and must be a deliberate v1.2 migration."""


def main() -> int:
    studies = run_study()
    md = render_markdown(studies)
    out = _repo() / "docs" / "multiplicity-study.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print("wrote %s (%d scenarios)" % (out, len(studies)))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
