# Multiplicity & concentration control — architect recommendation

**Status: §4 APPROVED AS GUIDANCE (owner, 2026-07-30).** The owner approved the v1.2 scope as *frozen
missingness ONLY*, the multiplicity default staying `none`, and *Reading B* for the curve. Under that
decision **§4 is the recommendation of record for published guidance** — the **shipped curve scale
with a per-cohort 10%`B` saturation cap** (recalibration was evaluated and REJECTED on
under-deployment grounds, Condition 1 / `docs/compensation-study.md`), which each experiment freezes
for itself. It is **NOT a spec change**: it moves no frozen field and no spec golden (§4a Reading B).
**The frozen default is UNCHANGED: `none`** (independent one-sided 5% test per cohort,
`reward-policy.md` Stage 1). The §4.0 curve numbers are FINALIZED (Condition 1): cap = 10% of `B`,
fixture `reward_curve_hash sha256:eeab732e…`.

This document was previously WITHDRAWN-PENDING-DATA. It was withdrawn for two reasons, both now
resolved:

1. a correction to its structural premise, which was **wrong** (§1 below) — corrected and committed
   (reward-policy.md erratum + Q-CURVE-1, commit `70c3d4c`); and
2. the four-way regime comparison + floor sweep + per-cohort-cap + curve-recalibration numbers, now
   produced and committed by `causal-inference-engineer` (`docs/multiplicity-study.md`, commit
   `ea6de6b`; every number pinned as a test in `causal-engine/tests/test_levers.py`).

The measured results are the data of record for §3/§4 and are cited here rather than re-transcribed.
§4 is written against them.

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

## 2. Why a floor is the wrong lever — CONFIRMED against measured valuations

A cohort that clears a one-sided test under a true null clears it *because* its conservative bound
came out large. A floor placed **below** the curve's first paying breakpoint therefore deletes the
small marginal winners — the same ones a multiplicity correction already deletes — and leaves the
large one untouched. This is now confirmed against the actual `s2_null_effect` valuations
(`causal-engine/tests/test_levers.py`; `docs/multiplicity-study.md`):

| paid cohort | `conservative_s` | allocation (share of `B`) | removed by a floor in `(0.018384, 0.139576]`? | removed by BH? |
| --- | --- | --- | --- | --- |
| `cell0007` | **0.139576** | **25.94%** | **no** | **no** (one-sided p = 5.09e-05) |
| `cell0048` | **0.018384** |  3.68% | yes | yes |

**The floor and BH are one lever wearing two hats.** ANY floor in `(0.018384, 0.139576]` removes
*only* `cell0048` — the exact same cohort BH removes. BH alone, floor `0.030`, floor `0.050`, floor
`0.100`, and every BH+floor combination up to `0.100` all land on **identical** 25.94% waste and
25.94% max single-cohort share. So `floor-only`, `BH-only` and `BH+floor` are redundant with each
other; BH+floor pays two frozen changes for one effect.

**No floor separates signal from noise.** The only grid floor that zeroes `s2` waste is `0.150`,
which drives `s1` power to 0.00%, `s5` to 0.00% and `s4` to 4.55%. The null cohort's conservative
effect (0.139576) **exceeds every true positive in the benchmark** (`s1` max 0.123141, `s5` max
0.121521), because per-cohort noise (simulator `cluster_noise_sd = 0.08`) is the same order as the
per-cohort signal these designs try to detect. Any floor high enough to reject the null artifact
rejects the real signal first. **The floor is dominated and redundant at every tested parameter.**

---

## 3. Results — measured (data of record: `docs/multiplicity-study.md`)

The full six-scenario × four-regime table, the floor sweep, the per-cohort-cap sweep, the
curve-recalibration arm (arm 6), and the saturating-curve arm (arm 6b) are in
`docs/multiplicity-study.md` and pinned in `causal-engine/tests/test_levers.py`. Regenerate
deterministically with `python -m crp_engine.studies` (byte-identical across `PYTHONHASHSEED`
values). The decision-relevant extract:

### 3.1 The `s2_null_effect` headline (true zero effect)

| arm | s2 waste (%B→null) | s2 max single-cohort share (%B) | s1 legit (%B to true positives) | waste-to-legit ratio |
| --- | --- | --- | --- | --- |
| baseline (`none`, frozen policy) | 29.61% | 25.94% | 73.75% | 0.402 |
| BH FDR | 25.94% | 25.94% | 69.22% | 0.375 |
| per-cohort cap 10.0%B | **13.68%** | **10.00%** | 55.90% | **0.245** |
| C-R recalibration ×1/12 | **2.47%** | **2.16%** | 6.15% | 0.402 |

The two decisive columns: **max single-cohort share** is the concentration channel; the
**waste-to-legit ratio** is the targeting channel (waste per unit of legitimate payout). Read them
together:

- **BH** cuts the false-positive *count* 2→1 but the survivor is the *large* one, so max share is
  unchanged (25.94%) and the ratio barely moves (0.402→0.375).
- **The cap** is the ONLY lever that moves the ratio (0.402→0.245): it acts on the *size* of a single
  cheque, which is what the exposure actually is.
- **C-R** slashes absolute exposure hard (29.61%→2.47% waste, 25.94%→2.16% max share) but the ratio
  is **unchanged at 0.402** — it scales waste and legit down by the same factor. It is an *exposure*
  fix, not a *targeting* fix.

### 3.2 Weak-signal scenarios pay zero under every arm

`s3_low_power` (true effect 0.030) and `s6_demand_shift` (0.050) pay **zero** under EVERY arm,
including baseline — 100% of budget recovered. This study therefore **cannot rank levers on
weak-signal power**; it can only certify that no lever makes weak-signal power *worse*. Recovering the
weak-signal true positives is a **design** change (switchback, to difference out cohort-shared
noise), not a reward-policy field. CLAUDE.md Invariant 8 governs: a null payout on a design with no
per-cohort power is a correct, honest output, not a defect to tune away.

---

## 4. Recommendation (owner-approved v1.2 scope: guidance only)

**Frozen default is UNCHANGED (`none`, per-cohort one-sided 5% test). No spec golden moves for the
curve (Reading B, §4a). This section is published GUIDANCE that each experiment freezes for itself.**

### 4.0 The recommended default configuration — CAP-ONLY (recalibration REJECTED)

**The recommended default is the SHIPPED curve scale plus a per-cohort saturation cap at 10% of `B`.
Recalibration was evaluated under Condition 1 and REJECTED.** This supersedes the earlier "calibration
+ cap together" framing: the Condition-1 compensation study (`docs/compensation-study.md`, commit
`4137d7a`) flipped it.

**Why recalibration is rejected — it under-deploys.** Proportional recalibration (scaling the whole
curve down by `5/cohort_count`, e.g. ×1/12 for 60 cohorts) is a pure exposure/`value_scale` change:
it scales *both* waste and legitimate payout down by the same factor, so its waste-to-legit ratio
never moves (0.402 at every scale, §3.1). The compensation view exposed what head-count power hid: on
a **strong-signal** network (`s1`) the recalibrated curve pays true positives only **6.15% of `B`** and
**recovers 93.85%** — the "spending badly by spending little" failure Condition 1 named. Per
Condition 1's own instruction ("if recalibration systematically under-deploys, say so and adjust"),
**we adjust: no recalibration; keep the shipped curve scale.**

**Why the cap is the whole default.** The per-cohort saturation cap is the *only* lever measured that
improves **targeting** (waste-to-legit ratio 0.402 → 0.245 at a 10%`B` ceiling — the frontier
optimum; tighter caps start clipping true positives and *worsen* the ratio) while **dropping no true
positive** at 10%`B` (head-count power on `s1`/`s5` unchanged). It binds exactly when few cohorts pay
and is inert when many do — the property no multiplicity threshold, floor, or uniform rescale can
offer. So the recommended default is: **shipped curve scale, clipped by a per-cohort 10%`B`
saturation ceiling.**

> **Recommended default curve (guidance) — FINALIZED (Condition 1, `docs/compensation-study.md`).**
> For the example manifest (`B = 100,000,000,000`, `N = 60` valuation cohorts):
>
> - **Cap ceiling:** `cap_base_units = 10,000,000,000` (= 10% of `B`; general rule: **10% of `B'` for
>   any budget `B'`**).
> - **Saturating breakpoints** (shipped curve clipped at the ceiling; the 10e9 ceiling crosses the
>   shipped first segment at `conservative_s = 50000`):
>   `[["0","0"],["50000","10000000000"],["100000","10000000000"],["500000","10000000000"],["1000000","10000000000"]]`.
>   Valid `piecewise_linear_monotonic`; validates against the frozen manifest schema unchanged.
> - **Fixture `reward_curve_hash`:** `sha256:eeab732ec6ff4cf09e1185b2b42ad5e5aa83524fefbd6f3d6b079ab43d227ff3`
>   (computed by `canonical.py` over the curve above; it is a FIXTURE hash, NOT a spec golden —
>   §4a Reading B, §4c fixture contract).
> - **NO recalibration / value_scale change.** The shipped `budget → curve-output` scale is unchanged;
>   only the ceiling is added.

**Cap is TUNABLE per experiment.** The 10%`B` ceiling is a *recommended default*, not a protocol
constant. Each experiment freezes its own `reward_curve` (Invariant 1); a winner-take-most design MAY
freeze a higher ceiling or none at all, and MUST justify it in its manifest description. The default
exists so that "no explicit concentration control" is a deliberate, documented choice rather than the
silent status quo. Because the cap lives inside the already-frozen `reward_curve`/`reward_curve_hash`,
adopting it as the default adds **no new frozen field** and moves **no spec golden** (§4a). The
shipped example manifest is NOT edited to carry the cap — it stays the shipped scale (Reading B).

### 4.1 Supporting analysis (priority order, cheapest lever first)

The per-lever findings below are the evidence for §4.0. The frozen default stays `none`; each is a
proposal answered in the priority order set by the original §4 questions.

### (i) Does curve recalibration (C-R) close the concentration problem? — REJECTED. It under-deploys (Condition 1).

C-R is the cheapest lever mechanically (it moves **no spec golden**, costs **zero head-count power**,
and at ×1/12 cuts `s2` waste 29.61%→2.47% and max single-cohort share 25.94%→2.16%), and the earlier
draft of this section recommended adopting it. **The Condition-1 compensation study reversed that.**

**Its waste-to-legit ratio never moves (0.402 at every scale)** — it shrinks the whole cheque book
uniformly without aiming the money better. Worse, the compensation view showed the uniform shrink
**under-deploys on genuine signal**: on `s1` (strong signal) the ×1/12 curve pays true positives only
**6.15% of `B`** and recovers 93.85% — trading over-concentration for gross under-payment, the exact
failure Condition 1 was written to catch. Head-count power (unchanged) hid this because the *number*
of paid cohorts is scale-invariant while the *dollars* collapse. **Recommendation: do NOT recalibrate.
Keep the shipped curve scale.** C-R is neither a targeting fix nor a safe exposure fix; it is
dominated by the cap, which improves targeting without sacrificing deployment.

### (ii) Is a per-cohort cap worth a new frozen field? — NO NEW FIELD, and it IS the recommended default (§4.0), on its own.

A per-cohort cap needs **no new schema field**. It is exactly a **saturating `reward_curve`**:
`saturate_curve` (inserting the ceiling-crossing breakpoint) reproduces the post-hoc per-cohort cap
to the ppm on all six scenarios at 10/5/2.5%B (1 ppm short, never over, at 25%B where the crossing is
non-integral — study arm 6b == arm 5). `reward_curve` and `reward_curve_hash` are ALREADY in
`manifest.schema.json` `reward_policy.required`, so a cap lives inside the existing frozen commitment.

The cap is the **only lever that improves the targeting ratio** (0.402→0.245 at 10%B) and it **drops
no true positive** (`s1`/`s5` power head-count unchanged; the cost shows up in `legit`, not in power,
and only for cohorts whose cheque exceeded the ceiling). It binds exactly when few cohorts pay and is
inert when many do — the property neither BH nor a floor nor uniform C-R can offer. **This IS the
recommended default (§4.0), as a saturating-curve shape (shipped scale, 10%`B` ceiling), not a new
field, and NOT paired with recalibration** (recalibration under-deploys, (i)). 10%`B` is the frontier
optimum: tighter caps clip true positives and worsen the ratio, looser caps recover less waste.

### (iii) Is BH justified on its own merits? — Weak. Do not adopt it as a frozen field on this evidence.

Assessed honestly and *not* as a concentration fix (it provably is not one — max share stays 25.94%):

- It is the **only** candidate here that requires a **new frozen field**
  (`reward_policy.multiplicity_control{method, fdr_level_micro}`), hence the only one that moves a
  golden purely to buy a discovery correction.
- Its concentration benefit is nil (25.94%→25.94%).
- Its waste benefit is thin (29.61%→25.94% of `B`, a 3.7-percentage-point cut — the whole of which is
  the small cohort a floor or the per-cohort test already reaches).
- It **costs true-positive power**: `s5` 62.50%→37.50%, `s1` 36.84%→31.58%, `s4` 36.36%→27.27%.

BH is a defensible *statistical* instrument when many genuine signals coexist with many nulls, and it
dominates Bonferroni/Šidák on power. But on this benchmark the honest verdict is: **the case for
paying a new frozen field for BH is not made.** Recommend AGAINST adopting BH as a v1.2 frozen field
now; keep it as a documented, available `multiplicity_control` value that an experiment MAY freeze if
its own design warrants it (see C-0b hygiene note in the migration proposal).

### (iv) Is a floor worth anything? — NO.

Dominated and redundant with BH at every tested parameter (§2). A floor that bites on the null
artifact rejects the real signal first. **Recommend against. Strike C-2/C-3 from the menu.**

---

## 4a. The hash-cost ruling (state exactly which hashes move — do not let "no new field" slide into "no hashes move")

The claim **"a per-cohort cap needs no new schema field"** is TRUE: the cap lives in the existing,
already-frozen `reward_curve` / `reward_curve_hash`. But **"no new field" is not "no hashes move."**
Two readings, with the exact hashes each moves:

**Reading A — protocol migration (v1.2).** We change the *spec example*
(`specs/examples/manifest.example.json`) to carry the recommended calibrated/saturating curve. Then:

- the example's `reward_curve_hash` moves off `sha256:14b0ec34…` (a saturating curve inserts a
  breakpoint; a recalibrated curve rescales the y-values), and
- the manifest golden **`74e0bb82…` moves** (the curve bytes are inside the manifest).

This is a hash-moving change that must ride the single v1.2 package
(`specs/v1.2-migration-proposal.md`), even though no *field* was added.

**Reading B — fixture + published guidance (RECOMMENDED).** The spec example curve is left
untouched; each experiment freezes whatever `reward_curve` it wants, and we ship a **recommended
calibration** (equal-share scale and/or a saturating ceiling) as guidance plus a benchmark-fixture
curve in `studies.py`. Then:

- the spec manifest golden **`74e0bb82…` is UNCHANGED**,
- the spec `reward_curve_hash` **`sha256:14b0ec34…` is UNCHANGED**,
- only the *benchmark manifest's own* `reward_curve_hash` differs — because every experiment computes
  its own curve hash by construction — which moves **no spec golden**.

**Ruling (owner-approved).** The per-cohort-cap recommendation (recalibration REJECTED, §4.0) is
adopted under **Reading B**: it is a **fixture + published-guidance change, not a protocol
migration**. The protocol already lets an experiment freeze any curve; the cap is a curve *shape*, not
a protocol feature. Adopting it as guidance moves **no spec golden** (the shipped example
`reward_curve_hash sha256:14b0ec34…` is untouched; only the benchmark fixture carries the capped curve
`sha256:eeab732e…`). It would become a migration (Reading A) ONLY if the owner wanted the *shipped
example* to model the capped curve — a presentational choice that costs the manifest golden and the
example `reward_curve_hash`; the owner declined it (Reading B). Neither reading adds a schema field.

## 4b. What the protocol SHOULD normatively guarantee

Three candidate guarantees, ruled on against the ratio-vs-exposure distinction:

1. **A bound on per-cohort concentration** (max single-cohort share ≤ κ). Achievable *without a new
   field* via a saturating curve, and it is the only guarantee that bounds the tail a single chance
   cohort can absorb. **Recommend the protocol offer this as an available, per-experiment curve
   property** (a manifest author MAY freeze a saturating curve), documented normatively — not as a
   mandatory protocol-level constant.
2. **A bound on expected wasted spend** (E[waste] ≤ w). **Reject as a protocol guarantee.** Expected
   waste depends on the true (unknown) effect distribution; the protocol verifies *process, not
   truth* (Invariant 6). Under a true null the honest expected waste is a *disclosed property* of the
   chosen curve and test, not a quantity the chain can guarantee.
3. **Neither — disclosed property only.** This is the status quo and remains the floor.

**Ruling.** The protocol should guarantee **neither as a mandatory bound**, and should instead
*disclose*: (a) that reward is absolute-scale with unused budget recovered (Property P-ABS, already
drafted), and (b) that per-cohort concentration is a *calibration property of the frozen curve*,
boundable by the manifest author via a saturating curve if they want a concentration guarantee for
their experiment. The ratio-vs-exposure distinction is why: the chain can enforce a curve *shape*
(exposure) deterministically, but it cannot certify *targeting* (waste per unit legit) without
knowing the truth it is forbidden to assume.

## 4c. Consequence for the M4 at-scale benchmark — DECOUPLE the fixture

Today `specs/examples/manifest.example.json` is inherited verbatim by
`causal-engine/src/crp_engine/studies.py::run_study` (it reads the spec example directly) **and** by
the M4 at-scale benchmark. Under Reading B the spec example is left **untouched** (its curve golden
`sha256:14b0ec34…` does not move), so if the benchmark kept inheriting it, the M4 at-scale run would
publish numbers from the OLD example curve while this document recommends a NEW default — an
incoherent deliverable.

**Ruling (owner Condition 3): the benchmark gets its OWN manifest fixture** carrying the recommended
**shipped-scale + 10%`B` saturating-cap** curve (recalibration rejected, §4.0),
`reward_curve_hash sha256:eeab732e…`, **distinct from and not derived at runtime from**
`manifest.example.json`. The spec example stays frozen; the benchmark reads the fixture. The full
fixture contract — path, hash rule, and the provenance line the benchmark report must carry — is
specified in `specs/v1.2-migration-proposal.md` "Benchmark manifest fixture (Condition 3)" and
mirrored in `docs/benchmark-plan.md` §7. `studies.py` is rewired to load the fixture (owner:
`causal-inference-engineer`); this document and the migration doc define the contract it wires to.

The curve choice (calibrated scale + saturating ceiling) **must be finalized BEFORE the M4 benchmark
runs** — otherwise the benchmark measures a curve the recommendation then supersedes and the run must
be repeated. This is a gating dependency, not a preference. The fixture decoupling removes the
*second* failure mode (benchmark silently tracking the spec example) but not the *first* (running
before the numbers are final).

## 5. Data reference

Regenerate deterministically: `python -m crp_engine.studies` (see `docs/multiplicity-study.md`), or
`python tools/multiplicity_study.py`. Every number in §3/§4 is pinned in
`causal-engine/tests/test_levers.py`. The earlier "Structural note" that carried the withdrawn
normalization premise has been retracted at its source (`studies.py`, commit `ea6de6b`); the
generated document now states the absolute-scale allocation correctly.

## 6. Reconciliation with the v1.2 migration package

This recommendation **retires slot S2** as a hash-moving multiplicity field. See
`specs/v1.2-migration-proposal.md` "Slot S2" for the ruling: floor struck (redundant), cap needs no
field (saturating curve), BH not worth a new frozen field on this evidence, C-R is a fixture change.
The honest residual of the package is **S1 (missingness) — the only genuine correctness gap** — plus
the cheap S3 clarifications and the independent B1 pin.
