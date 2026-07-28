# Multiplicity & concentration control — architect recommendation

**Status: WITHDRAWN-PENDING-DATA (2026-07-28). NOT a recommendation of record.**
**The frozen default is UNCHANGED: `none`** (independent one-sided 5% test per cohort,
`reward-policy.md` Stage 1). Nothing here is normative and nothing here is ratified.

This document was previously issued as a recommendation (BH + a `["50000","0"]` conservative-effect
floor). It is **withdrawn** pending two things:

1. a correction to its structural premise, which was **wrong** (§1 below), and
2. the four-way regime comparison + floor sweep + per-cohort-cap numbers currently being produced by
   `causal-inference-engineer` (no-correction / BH / BH+floor / floor-only / cap). Until those exist
   there is no defensible parameter choice, only a menu.

The sections below are structured so the new numbers slot straight in. Every results table is marked
**[PENDING]** and MUST NOT be cited until filled.

---

## 1. Correction of the structural premise (this is why the doc was withdrawn)

The withdrawn version stated:

> "`proportional_scale_to_budget` divides the *whole* budget across whichever cohorts clear the test,
> so two chance winners split the entire pool, not `2/60` of it."

**That is wrong.** Allocation in this protocol is **absolute**, not a share of the budget
(`reward-policy.md` Stage 1 steps 5–6, and the new Appendix B "Property P-ABS"):

```
alloc_c = reward_curve(conservative_c_s)        # a function of cohort c ALONE
S       = Σ_c alloc_c
S ≤ B  ⇒ budget_c = alloc_c                     # overflow rule is a NO-OP; B − S is recovered
S > B  ⇒ budget_c = ⌊alloc_c · B / S⌋           # single downward factor, applied to everyone equally
```

On `s2_null_effect` the engine reported **deployed 29.61% / recovered 70.39%**, i.e. `S ≈ 0.2961·B ≤ B`
— so `proportional_scale_to_budget` **never executed**. (The same published table shows the other
branch does exist: `s4_interference` under `none` deploys 100.00%, which is the `S > B` cap firing.)
Dropping a cohort cannot hand its allocation to a survivor; there is no redistribution mechanism in
the protocol at all.

**The specification and the implementation agree on this.** `causal-engine/src/crp_engine/reward_compiler.py`
implements exactly the branch above. There is **no normalization bug**. The wrong narrative existed
only in non-normative prose (this document, `reward-policy.md` Appendix A, and the generated
"Structural note" in `docs/multiplicity-study.md`).

**What the residual actually is.** A single cohort took 25.94% of `B` because the frozen example
`reward_curve` *pays* one cohort that much: its first paying breakpoint is worth 20% of `B` to a
single cohort and its last is worth 120% of `B` to a single cohort, with no constraint anywhere tying
curve outputs to `B` or to `cohort_count` (`reward-policy.md` Appendix B.2). This is **curve
calibration**, and it is a per-experiment manifest parameter — not a protocol-level allocation defect.

**Consequence for the remedy menu.** The two channels framing survives, but the instruments change:

| Channel | What it is | Instrument that actually moves it |
| --- | --- | --- |
| Discovery | how many null cohorts clear the test | multiplicity threshold (BH / Bonferroni / Šidák) |
| Concentration | how much `B` one survivor absorbs | **curve calibration**: overall height, a floor, or a per-cohort cap |

A multiplicity threshold does not touch concentration — that part of the withdrawn doc was right, for
the wrong reason.

---

## 2. Why a floor at `["50000","0"]` is probably the wrong lever [PENDING confirmation]

A cohort that clears a one-sided test under a true null clears it *because* its conservative bound
came out large. A floor placed **below** the curve's first paying breakpoint therefore deletes the
small marginal winners — the same ones a multiplicity correction already deletes — and leaves the
large one untouched.

Derived from the published `s2_null_effect` allocations against the example curve (`reward-policy.md`
Appendix B.3; **`causal-inference-engineer` to confirm against actual valuations**):

| paid cohort | derived `conservative_s` | allocation | share of `B` | removed by `f_s = 50000`? |
| --- | --- | --- | --- | --- |
| #1 | ≈ 139600 | 25.94e9 | 25.94% | **no** |
| #2 | ≈ 18350 | 3.67e9 | 3.67% | yes |

If confirmed, `floor-only(50000)`, `BH-only` and `BH+floor(50000)` all land on **the same 25.94%**,
i.e. the two recommended levers are **redundant with each other** at the proposed parameter values.
A floor that bites on `s2` must exceed ~139600 — *above* the first paying breakpoint — which is a much
more aggressive change than was represented. This is exactly why the floor sweep is required before
any recommendation.

---

## 3. Results [PENDING — `causal-inference-engineer`]

### 3.1 Four-way regime comparison (six scenarios) [PENDING]

Replaces the withdrawn table. Required columns per cell: `m`, `paid`, `waste (%B→null)`,
`power (%payable-TP paid)`, `deployed (%B)`, `recovered (%B)`, **`max single-cohort share (%B)`**
(new — this is the concentration metric the old study never reported and without which the
concentration channel cannot be evaluated), and **`scaled_to_budget` (did the `S > B` branch fire?)**
(new — so no reader can ever again mistake the `S ≤ B` case for normalization).

> _table pending_

### 3.2 Floor sweep [PENDING]

Required: for `f_s` across a grid spanning below, at, and above the first paying breakpoint
(`100000`), report on `s2_null_effect` the `max single-cohort share` and `waste`, and on
`s1_strong_signal` / `s5_sybil_contamination` the power and deployment given up.

> _table pending_

### 3.3 Per-cohort cap sweep [PENDING]

Required: `max_cohort_share_micro` across a grid, same two-sided read (concentration bought vs.
legitimate large-effect payout given up on `s1`/`s5`).

> _table pending_

### 3.4 Curve-recalibration reference arm [PENDING — requested]

Not previously studied and it must be, because it is the **only** candidate that needs **no schema
change at all**: re-run the benchmark with a `reward_curve` whose outputs are calibrated to the
scenario's `cohort_count` (e.g. `y_last ≤ B`) and report the same columns. If recalibration alone
brings `max single-cohort share` to an acceptable level, the whole v1.2 multiplicity item may be
unnecessary. Note the expected tradeoff (`reward-policy.md` Appendix B.3): lowering curve height
suppresses concentration and deployment by the *same* factor, so this arm is expected to trade
under-deployment on `s1`/`s5` for lower `s2` concentration. Quantifying that trade is the point.

> _table pending_

---

## 4. Recommendation [PENDING — deliberately not written]

**No recommendation is issued in this revision.** It will be written against §3 once the tables
exist, and it must answer, in order:

1. Does the **curve-recalibration** arm (no schema change, no new frozen field, no v1.2 dependency)
   close the concentration channel acceptably? If yes, prefer it — it is strictly the cheapest.
2. If not, is the residual concentration worth a **new frozen field**
   (`reward_policy.max_cohort_share_micro`), which is the only lever that bounds concentration
   *without* costing deployment when many cohorts genuinely pay?
3. Is a **discovery** correction (BH) worth adopting *on its own merits* — i.e. justified by the
   power/waste table across all six scenarios, and **not** as a fix for concentration, which it
   provably is not?
4. Is a **floor** worth anything once (1)–(3) are decided, given §2?

Each answer carries an explicit hash cost, enumerated in `specs/v1.2-migration-proposal.md`.

**Honest baseline for that decision, stated up front:** the only concentration improvement any
threshold regime has demonstrated so far is **29.6% → 25.9% of budget wasted under a true null**.
That is a **thin** return, and `reward_curve_hash` is a frozen, golden-bearing commitment. Moving it
must be justified by better numbers than that.

## 5. Data reference

Regenerate deterministically: `python -m crp_engine.studies` (see `docs/multiplicity-study.md`).
Note that the generated "Structural note" section of that document still carries the withdrawn,
incorrect premise from §1; it is emitted by `causal-engine/src/crp_engine/studies.py`
(`_STRUCTURAL_NOTE`, ~line 353; selection-layer bullet, ~line 257) and must be corrected **at that
source**, not by editing the generated markdown.
