# simulator/ — Configurable DePIN simulator (Python 3.11+)

Generates a synthetic environmental-sensor DePIN network — tunable **coverage, redundancy,
hardware quality, fault risk, Sybil replication, and demand shifts** — and emits a
**deterministic** artifact (sensor set, cohort assignment, signed-observation counts, and
cohort × time-block outcomes) plus a **canonical content hash**. It drives the six benchmark
scenarios comparing the four reward baselines (activity / quality / scarcity / causal).

Package: `depin_sim` (in `src/`). Status: **M1 alpha**.

## Cohort-level estimand (invariant)

The experimental unit is a **geographic cohort (cell) within a time block** — `geo_cohort_time_block`,
matching `specs/manifest.schema.json`. Sensors are generated *below* the estimand line (to produce
activity counts and give the activity/quality/scarcity baselines something to score) but no
per-device counterfactual is ever formed. See CLAUDE.md invariant #4.

## Quick start

```bash
make setup          # create .venv and install pinned deps (requirements.txt)
make baseline       # emit the deterministic baseline bundle + content hash -> out/baseline_alpha/
make determinism    # run baseline twice, FAIL if content hashes differ (M1 acceptance gate)
make test           # pytest: determinism, canonical serialization, seeds, scenarios
```

Direct CLI:

```bash
python -m depin_sim.cli run  --scenario scenarios/s1_strong_signal.json --out out/s1
python -m depin_sim.cli hash --scenario scenarios/s2_null_effect.json   # prints only the hash
python -m depin_sim.cli run  --scenario scenarios/baseline_alpha.json --seed 0xdeadbeef  # override seed
```

## Scenarios (`scenarios/`)

`baseline_alpha` is the M1 determinism baseline. The six benchmark scenarios (see
`docs/benchmark-plan.md`) are: `s1_strong_signal`, `s2_null_effect`, `s3_low_power`,
`s4_interference` (+ `s4b_interference_guardband` mitigation companion), `s5_sybil_contamination`,
`s6_demand_shift`. **The null and low-power scenarios are first-class valid outcomes** — if the
causal engine pays little/nothing there, that is the correct, publishable result (CLAUDE.md #8).

## How determinism is enforced (primary acceptance criterion, CLAUDE.md #2)

- **Single seed source.** Every random draw descends from the one committed seed via numpy
  `SeedSequence` spawning (`seeds.py`). One fixed, append-only stream order per component — a
  determinism contract. No wall-clock, no unseeded RNG, no `os.urandom`.
- **numpy PCG64 only** for the data-generating process (no scipy sampling, no BLAS matmul), so
  draws are BLAS-independent.
- **Fixed iteration order.** Grids/tables are built in explicit index order; no reliance on
  dict/set iteration order in any artifact-producing path.
- **Isolated seed → assignment.** All treatment-assignment logic lives in `assignment.py` behind
  one function so it can later be swapped for the canonical seed→assignment derivation ratified by
  `verifier-reproducibility-engineer` without touching the rest of the pipeline. The alpha uses a
  clearly marked placeholder derivation (`ALPHA_DERIVATION`).
- **Float-free canonical hash.** The content hash (`canonical.py`) conforms to
  `specs/serialization.md`: **no floating-point in the hashed bytes** — every real value is
  integer-scaled (micro, round-half-to-even), keys sorted by code point, SHA-256 hex. The hash is
  computed over canonical JSON, **not** parquet bytes (parquet is not byte-stable). Parquet/JSON
  export (`export.py`) is convenience output only, never the source of the guarantee.
- **Content vs. environment.** The hash covers the scientific content (config + generated tables +
  DGP version), and deliberately **excludes** environment provenance (package versions, host,
  wall-clock) so same-seed reruns reproduce an identical hash within the pinned environment.
  Cross-environment reproducibility is closed by the committed container digest (below).

Proven by `tests/test_determinism.py` (same-seed → identical hash, including a cross-process
subprocess check) and `make determinism`.

## Pinning / container

`requirements.txt` and `pyproject.toml` pin exact dependency versions. These are the first step
toward the committed **container digest** that `verifier-reproducibility-engineer` produces; the
container additionally pins the interpreter build and BLAS to keep committed numbers byte-stable
across machines. Same container + scenario + seed ⇒ identical content hash and every downstream leaf.

## Layout

```
simulator/
  src/depin_sim/
    config.py        scenario config (dataclasses, JSON load); manifest-aligned field names
    seeds.py         committed seed -> independent, reproducible RNG streams
    network.py       geographic cells (cohorts) + sensors; coverage/redundancy/quality/Sybils
    assignment.py    ISOLATED seed -> treatment assignment (swappable for canonical rule)
    observations.py  signed-observation counts; faults, Sybil inflation, demand shift; aggregation
    outcomes.py      held-out-RMSE outcome DGP (true effect, interference, confounding) — sim truth
    canonical.py     float-free canonical serialization + SHA-256 content hash (per serialization.md)
    run.py           orchestrates one deterministic run -> artifact + hash
    export.py        optional Parquet/JSON bundle (NOT the hash source)
    cli.py           `run` / `hash` commands
  scenarios/         baseline + six benchmark scenario JSONs
  tests/             determinism, canonical, seeds, scenarios
  Makefile  requirements.txt  pyproject.toml
```

## Alignment notes for other agents

- **protocol-architect:** field names mirror `specs/manifest.schema.json` where they overlap
  (`unit` = `geo_cohort_time_block`, `primary_outcome` = held-out RMSE, `treatment`,
  `minimum_sample`, `confidence_level`, `design` enum). MISMATCH to reconcile: the simulator's
  ground-truth knobs (`true_effect`, `interference`, `confounding`, Sybil params) are simulator-only
  and must **never** appear in a real frozen manifest.
- **verifier-reproducibility-engineer:** `canonical.py` follows the provisional CJSON in
  `serialization.md §2`. If §3 (RATIFIED) diverges, `canonical.py` is the single reconciliation
  point and any committed golden hash here is regenerated in the same change. Assignment derivation
  is isolated in `assignment.py` for the same reason.

## License

MIT (analysis library).
