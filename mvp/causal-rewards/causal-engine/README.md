# causal-engine

The Python causal engine and reward compiler for the Causal Rewards Protocol (milestone M3).

Given a **frozen manifest**, a **participant panel**, and the **revealed assignment seed**, it
estimates a cohort-level treatment effect with cluster-robust uncertainty, converts that effect
into a *conservative* reward distribution, and emits the analysis artifacts the audit bundle
commits. Every artifact-producing path is deterministic and integer-scaled — no wall-clock, no
unseeded RNG, no locale/float nondeterminism (CLAUDE.md invariant 2).

## Invariants this package enforces

- **Cohort-level estimand (invariant 4).** The unit is a geo-cohort × time-block; the engine never
  claims to identify an individual device's counterfactual.
- **Conservative payouts (invariant 3).** Per cohort, on the positive-improvement metric:
  `margin = round_half_even(critical_value_micro · standard_error / 1e6)`,
  `conservative = max(0, improvement − margin)`. A cohort that fails any frozen minimum-sample
  threshold, or whose effect is not identified, is forced to `conservative = 0`. Below
  `min_eligible_cohorts` eligible cohorts, the whole distribution is null.
- **Null results are valid (invariant 8).** Low-power / null / discovery-only outcomes are
  first-class outputs, not failures. The engine is never tuned to make causal allocation "win".
- **The chain verifies process, not truth (invariant 6).** Every artifact repeats that the causal
  claim is only as good as the design, data, and stated assumptions.

## One encoder, one leaf set

There is exactly one canonical-JSON encoder, one Merkle builder, and one reward-leaf preimage in
this repository: `verifier-cli/reference/{canonical,merkle,reward,assignment}.py`. This package
**imports them by path** (`crp_engine.reference`) rather than re-implementing them, so drift from
the conformance oracle is impossible by construction. `reference.py` resolves the reference
directory from `$CRP_REFERENCE_DIR` (set inside the pinned container) or the repo tree, and fails
loudly if neither is present — there is no silent local fallback.

The reward leaf set is the RATIFIED aggregate shape (serialization.md §6.6): exactly one leaf per
recipient, ranked by `recipient` (BE32) then `amount`, `leaf_index` contiguous from 0, zero-sum
recipients omitted, duplicate recipient = hard error.

## Layout

```
src/crp_engine/
  reference.py        # by-path bridge to verifier-cli/reference (the ONLY encoder)
  numeric.py          # integer / micro-scaled arithmetic, round-half-to-even, piecewise-linear curve
  manifest.py         # frozen-manifest reader + validation
  panel.py            # participant/observation panel loader
  estimators.py       # cohort effect + cluster-robust SE (CR1), absorbed fixed effects
  balance.py          # covariate balance diagnostics (never gates payout)
  sensitivity.py      # leave-one-cohort-out, placebo time-shift, wild cluster bootstrap
  reward_compiler.py  # Stage-1 conservative valuation + Stage-2 CRP-WS1 split -> aggregate leaf set
  baselines.py        # activity / quality / scarcity / causal reward baselines
  adapters.py         # design adapters (cluster-randomized, switchback, matched_cluster, replay)
  artifacts.py        # analysis.json / rewards.parquet (leaf set) / rewards_detail.parquet writers
  multiplicity.py     # cross-cohort false-positive regimes (none/Bonferroni/Šidák/BH) — study only
  studies.py          # deterministic §2.1 multiplicity study -> docs/multiplicity-study.md
  run.py, cli.py      # `crp-engine analyze | vectors | digest`
  demo.py             # human-readable demo inputs (NOT a hashed path)
docs/
  artifact-schemas.md # analysis.json / rewards.parquet / rewards_detail.parquet / provenance.json
  modeling-notes.md   # switchback + matched_cluster policy; identification modes; open spec proposals
container.lock.json   # pinned build inputs; recipe_digest + reference_source_digest
Dockerfile            # pinned analysis container
```

## Usage

```bash
pip install -e .
crp-engine analyze --manifest <frozen.json> --panel <panel.parquet> \
                   --participants <participants.parquet> --seed <hex> --out <dir>
crp-engine vectors            # replay the ratified reward test vectors (acceptance gate)
crp-engine digest             # print engine / reference / container digests
```

`analyze` writes `analysis.json`, `rewards.parquet`, `rewards_detail.parquet`, and
`provenance.json`. Schemas: `docs/artifact-schemas.md`.

> **Bundle-seam contract (RATIFIED, `docs/m3-integration-and-spec-round.md` §1).** The bundle's
> `rewards.parquet` **is the on-chain leaf set** — one row per recipient, columns
> `(leaf_index, recipient_hex, amount_base_units, leaf_hash_hex)`, `leaf_index` ascending from 0.
> It is what settlement claims against and what the reward root commits. `recipient_hex` is 64
> lowercase hex (presentation only; the §6.6 leaf preimage consumes the 32 raw bytes, so the
> column dtype never enters any committed hash — the `recipient_pubkey`/`recipient_hex` choice is
> not hash-moving). The per-`(cohort, recipient)` Stage-2 split is supplementary auditability and
> is emitted as `rewards_detail.parquet` (NOT the settlement source). `analysis.json` keeps its
> richer `primary_estimate`/`reward_summary`/`cohorts` schema and additionally carries a top-level
> `evidence_epoch_roots` (ascending epoch order) echoed from the assembler via
> `analyze(..., evidence_epoch_roots=...)` or `crp-engine analyze --evidence-epoch-roots`.

## Determinism & acceptance gate

```bash
pytest -q                       # full suite
pytest -q tests/test_reward_golden.py   # HARD GATE: reproduce the ratified reward roots
pytest -q tests/test_determinism.py     # two fresh interpreters -> identical artifact bytes
```

The reward compiler reproduces the ratified golden roots from `test-vectors/reward/`
(`reward-01 a9c35cf4…`, `reward-02 ea943182…`, `reward-03 b882c899…`, the empty `00…` root, and
the duplicate-recipient hard error). A golden root is never adjusted to match code — if the gate
fails, the engine does not ship.

## Reproducibility of every payout

Every payout number in `analysis.json` is recomputable from published fields alone:

```
margin_s       = round_half_even(critical_value_micro · standard_error_s / 1e6)
conservative_s = max(0, improvement_s − margin_s)     # 0 if not eligible or not identified
allocation     = reward_curve(conservative_s)          # frozen piecewise-linear curve
```

## Open spec-change proposals

The engine does not act unilaterally on protocol semantics. Proposals routed to
`protocol-architect` (missingness policy as a frozen field, HAC bandwidth, discovery-only
settlement, Stage-1 "cohort" wording, and cross-cohort multiplicity control) are in
`docs/modeling-notes.md` §6. Notably, the frozen one-sided 5% per-cohort rule has **no
family-wise correction**, so a true-null network of N cohorts is expected to pay ~5% of them;
this is a disclosed property of the policy, recorded for the benchmark report.

## License

MIT (analysis library).
