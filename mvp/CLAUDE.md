# Causal Rewards Protocol — Engineering Context (CLAUDE.md)

This file loads into every session and every subagent. Keep it accurate; it is the
shared source of truth for how this codebase is built.

## What we are building

Causal Rewards Protocol is an **open-source measurement and settlement layer for Solana
DePIN networks**. Existing DePIN reward systems verify that a contribution *happened*
(proof of contribution) and score its quality/scarcity. This protocol adds one more
question before settlement: **did the contribution cause measurable additional value
relative to a credible counterfactual?** ("Proof of Additionality" — a product concept,
not a cryptographic claim.)

The MVP delivers a reproducible workflow: freeze an experiment → assign cohorts from a
committed seed → anchor evidence batches → estimate a causal effect with uncertainty →
compile a conservative reward distribution → settle claims on Solana. Raw telemetry stays
off-chain; Solana stores only the manifest hash, commitments, result hashes, reward root,
and dispute state.

This is a **grant-scoped MVP (20 weeks, ~95k USDC target)**. Scope discipline is a feature.

## Non-negotiable invariants

These are correctness properties, not preferences. Violating one is a bug even if tests pass.

1. **Freeze before reveal.** The experiment manifest (primary outcome, unit, design,
   analysis plan, reward curve, assignment-seed *commitment*) is frozen and hashed
   *before* the assignment seed is revealed and *before* any outcome data is analyzed.
   Nothing in the manifest can change after freeze.
2. **Determinism / reproducibility.** Given the same frozen manifest, participant set,
   revealed seed, evidence bundle, and pinned analysis-container digest, an independent
   party must reproduce the *exact* assignment root, result-artifact hash, every reward
   leaf, and the final reward root. Reproducibility is the primary acceptance criterion of
   the whole project. No wall-clock, no unseeded RNG, no locale/float nondeterminism in
   any artifact-producing code path.
3. **Conservative payouts.** Reward from a cohort uses a *lower confidence bound* after
   converting the effect to a positive-improvement metric. `conservative_effect =
   max(0, effect - critical_value * standard_error)`. No positive payout from a cohort
   that fails the minimum-sample rule or whose conservative bound is ≤ 0.
4. **Cohort-level estimand.** The experimental unit is a geographic cohort within a time
   block — never an individual device. Within a cohort, reward is split by a *frozen*
   quality-weighted rule. We never claim to identify an individual device's counterfactual.
5. **Data minimization.** No raw telemetry, exact coordinates, or personal data in any
   Solana account. On-chain = hashes, roots, result summaries, claim state only.
6. **The chain verifies process, not truth.** On-chain code enforces commitments, integrity,
   and settlement. The causal claim is only as valid as the design, data, and assumptions.
   Code and docs must never overstate this.
7. **Devnet only.** No mainnet, no token, no protocol fee, no custody of production reward
   budgets in the MVP. Fees are hard-set to zero.
8. **Null results are valid outputs.** If causal allocation does not beat a baseline in a
   scenario, we publish that. Success = a credible, reproducible comparison, not "causal wins".

## Repository layout

```
causal-rewards/
  programs/                 # Solana (Anchor/Rust) on-chain programs
    experiment-registry/    # frozen manifest hash, funding, status, windows, authorities
    evidence-registry/      # batch roots, time ranges, signer commitments, eval artifact hashes
    settlement/             # reward root, claims, expiry, unused-budget recovery
    challenge/              # challenge records, bonds, finality pause, resolution
  sdk/
    typescript/             # create/freeze/post/challenge/finalize/claim clients
    python/                 # python client mirror
  causal-engine/            # Python: balance checks, estimators, uncertainty, sensitivity, reward compiler
  simulator/                # configurable DePIN sim: coverage, redundancy, faults, Sybils, demand shifts
  verifier-cli/             # reproduces assignment/evidence/analysis/reward roots from an audit bundle
  dashboard/                # web app: experiment/evidence/result/challenge/claim views + audit export
  examples/
    environmental-sensors/  # reference pilot wiring
  specs/                    # protocol spec, schemas, state machine, threat model, reward policy
  test-vectors/             # deterministic vectors for assignment, estimation, reward compilation
  docs/                     # integration guide, benchmark report, developer docs
```

## On-chain state machine

Experiment status: `Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`.
Core instructions (in order): `create_experiment`, `freeze_experiment`, `publish_cohort_root`,
`reveal_seed`, `post_evidence_epoch`, `submit_evaluation`, `open_challenge`,
`resolve_challenge`, `finalize_distribution`, `claim_reward`, `close_experiment`.
Accounts: `ProtocolConfig`, `Experiment`, `CohortSet`, `EvidenceEpoch`, `Evaluation`,
`Challenge`, `Distribution`, `ClaimReceipt`.

## Reference use case (MVP pilot)

Simulated environmental sensor network in **shadow mode**: the live prediction service is
never degraded; a *separate* evaluation pipeline randomly includes/holds out geographic
cohorts across time blocks. Treatment effect = change in out-of-sample prediction error
(e.g. held-out RMSE) caused by including a cohort's data. Templates: cluster-randomized,
switchback, matched-cluster, observational-replay (replay is not eligible for the strongest
causal claim). Scale targets: 10,000 virtual sensors, 250 cohorts, 1,000,000 signed
observations, 4 reward baselines (activity / quality / scarcity / causal) under one fixed budget.

## Tech stack & conventions

- **On-chain:** Rust + Anchor. Small, audited-shaped instructions. Every critical instruction
  has an integration test. Emit public events for every state transition. Multisig authority;
  constrained instructions; no admin path can rewrite frozen records or completed claims.
- **Causal engine & simulator:** Python (3.11+), typed, `numpy`/`scipy`/`pandas`, cluster-robust
  SEs. Favor **simple, auditable estimators** over complex causal ML. Pin everything; ship a
  container digest. All randomness seeded from the committed seed only.
- **Off-chain data:** content-addressed (hash-named) Parquet + JSON. Merkle roots for
  participant/assignment/evidence/reward. Audit bundle files: `manifest.json`,
  `participants.parquet`, `assignment.parquet`, `evidence/*.parquet`, `analysis.json`,
  `rewards.parquet`, `roots.json`, `provenance.json` (source commit, container digest,
  package versions, execution timestamp).
- **SDKs:** TypeScript (primary) + Python. Thin, typed wrappers over the programs. Ship examples.
- **Verifier CLI:** the independent oracle of truth. Must recompute every root from a bundle
  with zero network access and no trust in the coordinator/evaluator.
- **Settlement at scale:** Merkle claims or ZK-compressed accounts (Light Protocol) — never
  one full account per participant. Claims are single-use (nullifier / claim receipt).
- **Licensing:** Apache-2.0 for protocol code, MIT for SDKs and analysis libraries.
- **Optional Arcium adapter:** encrypted aggregation PoC only (sums/counts/means/thresholds).
  Optional dependency, never on the critical path.

Style: small PR-sized commits; conventional-commit messages; every module has a README and
tests; determinism tests are mandatory for any code that emits an artifact.

## Milestones (acceptance-gated)

- **M1 (wk 1–4): Spec & benchmark.** Threat model, manifest schema, state machine, simulator
  alpha, benchmark plan. Accept = frozen public spec + reproducible baseline run.
- **M2 (wk 5–9): Programs & SDK.** Registry, assignment, evidence, settlement, challenge, TS SDK.
  Accept = devnet deploy + local integration tests + deterministic assignment test vectors.
- **M3 (wk 10–14): Evidence & causal engine.** Signed evidence schema, batch commitments,
  causal engine, reward compiler, verifier CLI, Arcium PoC. Accept = independent reproduction
  of result + reward roots from an audit bundle.
- **M4 (wk 15–20): Pilot, hardening, release.** Dashboard, benchmark at target scale, security
  review, pilot validation, docs, final report. Accept = tagged OSS release + public dashboard
  + benchmark report + resolved review findings.

**Milestone gating:** do not start a milestone's implementation until the prior milestone's
acceptance test passes and is demonstrated. The frozen spec (M1) is a hard dependency for M2/M3.

## How work is delegated

The `orchestrator` agent coordinates and delegates to specialists; it does not write feature
code itself. Specialists (all on Opus 4.8):
`protocol-architect`, `solana-program-engineer`, `causal-inference-engineer`,
`backend-data-engineer`, `sdk-engineer`, `verifier-reproducibility-engineer`,
`frontend-engineer`, `security-reviewer`.

When in doubt about protocol semantics, the `specs/` directory (owned by `protocol-architect`)
wins over any individual implementation. If an implementation needs a spec change, that change is
proposed to `protocol-architect` and the spec is updated *before* the code — never silently diverge.
