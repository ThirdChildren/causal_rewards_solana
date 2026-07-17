# Causal Rewards Protocol — Protocol Specification

**Spec version:** 1.0.0
**Status:** M1 frozen-READY. Serialization is ratified and golden hashes are final; awaiting only
the orchestrator's freeze gate.

This is the narrative specification. Where prose and a schema disagree, the schema in `specs/`
wins for structure and the invariants below win for semantics. Companion documents:
`manifest.schema.json`, `evidence.schema.json`, `state-machine.md`, `threat-model.md`,
`reward-policy.md`, `serialization.md`.

## 1. What the protocol is

An open-source measurement-and-settlement layer for Solana DePIN networks. Existing DePIN
reward systems verify a contribution *happened* and score its quality/scarcity. This protocol
adds one question before settlement: **did the contribution cause measurable additional value
against a credible counterfactual?** — the "Proof of Additionality" product concept. It is a
*product* concept, not a cryptographic claim: the chain verifies process (commitments,
integrity, settlement), never the truth of the causal estimate (Invariant 6).

The workflow: **freeze** an experiment → **assign** cohorts from a committed seed → **anchor**
evidence batches → **estimate** a causal effect with uncertainty → **compile** a conservative
reward distribution → **settle** claims on Solana. Raw telemetry stays off-chain. Solana stores
only the manifest hash, commitments, result hashes, the reward root, and dispute state
(Invariant 5).

MVP is **devnet-only**: no mainnet, no token, no protocol fee, no custody of production budgets
(Invariant 7). Fees are hard-set to zero.

## 2. Lifecycle overview

Experiment status advances `Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`.
Full transition table, guards, and immutability sets are in `state-machine.md`. The load-bearing
ordering property is **freeze-before-reveal** (Invariant 1):

1. **Draft.** The coordinator authors the manifest — the pre-analysis plan. It contains the
   primary outcome, the estimand (cohort × time-block unit), the design template, the analysis
   plan with a pinned container digest, the reward policy (curve + intra-cohort split), windows,
   authorities, and the assignment-seed **commitment**. The seed itself is withheld.
2. **Frozen.** The multisig freezes the manifest. Its canonical hash is recorded on-chain. From
   here, no manifest field can change. Freeze happens **before** the seed is revealed and
   **before** any outcome data is analyzed. This is enforced structurally: the seed has no home
   in the manifest schema, and `reveal_seed` is only legal after `freeze_experiment`.
3. **Active.** The cohort/assignment root is published (`publish_cohort_root`), then the seed is
   revealed (`reveal_seed`). The revealed seed must open the committed value; anyone can then
   recompute the assignment from the frozen method + revealed seed and check it against the
   published root. Evidence epochs are anchored (`post_evidence_epoch`) as signed batches of
   commitments over the active window.
4. **Evaluating.** After the active window closes, the evaluator runs the pinned analysis
   container over the audit bundle and submits the result-artifact hash and reward root
   (`submit_evaluation`). Because the container, estimator, and reward policy were all frozen
   pre-reveal, the evaluator has no residual degrees of freedom to fish for an outcome.
5. **Challenged.** Within the challenge window, any challenger can post a bond and open a
   challenge (`open_challenge`) asserting the evaluation is not reproducible or violates the
   frozen plan. The multisig resolves it (`resolve_challenge`) — typically by pointing to the
   verifier CLI re-run of the audit bundle.
6. **Final.** With challenges resolved (or none opened), the distribution is finalized
   (`finalize_distribution`): the reward root is locked and claims open.
7. **Closed.** After the claim window, unclaimed and unallocated budget is recovered
   (`close_experiment`).

## 3. Actors and trust model

Trust model in one line: **the chain and the verifier CLI are trusted; every human role is
partially untrusted and constrained by commitments made before it could see outcomes.** The
verifier CLI is the independent oracle — it recomputes every root from an audit bundle with zero
network access and no trust in the coordinator or evaluator.

| Actor | Does | Trusted for | NOT trusted for / cannot do after freeze |
| --- | --- | --- | --- |
| **Coordinator** | Authors manifest; runs the network; collects and anchors signed evidence batches; publishes the cohort/assignment root; reveals the seed. | Availability/liveness (posting batches, revealing on time). | Cannot alter the manifest, the estimator, the reward curve, or the assignment method after freeze. Cannot choose the seed after seeing outcomes (bound by the pre-freeze commitment). Cannot inject raw telemetry on-chain. |
| **Evaluator** | Runs the pinned analysis container over the audit bundle; submits result-artifact hash + reward root. | Executing the *frozen* plan faithfully. | Cannot swap estimator, SE method, confidence level, or reward policy (all frozen). Any output that the verifier CLI cannot reproduce from the frozen plan + bundle is challengeable. May be the same or a different key than the coordinator; separation is recommended, not required by the state machine. |
| **Participant** | Runs devices; signs observations; earns a share of a cohort's allocation via the frozen quality-weighted split. | Signing its own observations. | Cannot forge membership in a cohort it did not sign into (signer-set commitment). Sybil-splitting a device across identities does not increase a *cohort's* valuation, because the estimand is cohort-level (Invariant 4); it can only dilute that cohort's own intra-cohort split (see `threat-model.md`). |
| **Challenger** | Posts a bond; opens a challenge that an evaluation is non-reproducible or violates the frozen plan. | Nothing — challenges are adjudicated against the verifier CLI, not trusted on their word. | Cannot pause finality for free: a challenge requires a bond, forfeited on a frivolous/losing challenge (griefing deterrent). |
| **Multisig authority** | Freezes the manifest; resolves challenges; finalizes the distribution. Threshold m-of-n. | Governance actions that gate state transitions. | Cannot rewrite a frozen manifest, alter completed claims, redirect funds outside the frozen policy, or resolve a challenge in a way that contradicts a verifier re-run without that being publicly visible on-chain. No single signer can act alone. |

## 4. On-chain vs off-chain (data minimization, Invariant 5)

**On-chain (Solana accounts only):** hashes, roots, summaries, and claim state. Specifically:
manifest hash; assignment/cohort root; assignment-seed commitment and later the revealed seed;
evidence epoch roots (signer-set root, observations root), time ranges, and integer aggregate
counts; the evaluation result-artifact hash and reward root; challenge records and bond state;
the finalized distribution root and per-claim receipts; status and window bounds. Account set:
`ProtocolConfig`, `Experiment`, `CohortSet`, `EvidenceEpoch`, `Evaluation`, `Challenge`,
`Distribution`, `ClaimReceipt` (mapped in `state-machine.md`).

**Off-chain (content-addressed audit bundle):** everything else. Raw signed observations, the
participant set, the assignment table, evidence parquet, the analysis result JSON, the reward
leaves, and provenance. Bundle files: `manifest.json`, `participants.parquet`,
`assignment.parquet`, `evidence/*.parquet`, `analysis.json`, `rewards.parquet`, `roots.json`,
`provenance.json`. **Forbidden anywhere in the protocol** (on- or off-chain artifacts): raw
telemetry values, exact coordinates, per-reading wall-clock timestamps, and any personal data.
Even off-chain observation leaves carry only a payload *commitment* (`evidence.schema.json`
`$defs.observation_leaf`).

## 5. Determinism (Invariant 2)

Reproducibility is the primary acceptance criterion of the whole project. Given the same frozen
manifest, participant set, revealed seed, evidence bundle, and pinned container digest, an
independent party reproduces the *exact* assignment root, result-artifact hash, every reward
leaf, and the final reward root. All hashing goes through the one canonical serialization
(`serialization.md`): no floats in hashed artifacts, integer-scaled decimals, banker's rounding
applied once, stable key ordering, one Merkle construction. No wall-clock, no unseeded RNG, no
locale/float nondeterminism in any artifact-producing path. All randomness derives solely from
the committed-then-revealed seed.

## 6. Invariant enforcement map

Where each of the eight non-negotiable invariants is enforced. A reader should be able to jump
from any invariant to the exact mechanism.

| # | Invariant | Enforced by |
| --- | --- | --- |
| 1 | Freeze before reveal | `manifest.schema.json` has no property to hold the seed (only `assignment.seed_commitment`); `state-machine.md` makes `reveal_seed` legal only after `freeze_experiment`; §2 lifecycle; immutability set frozen at `Frozen` in `state-machine.md`. |
| 2 | Determinism / reproducibility | `serialization.md` (canonical bytes, no floats, integer-scaled decimals, one Merkle rule); `analysis_plan.analysis_container_digest`; `manifest.golden.md` golden hash; seed-only randomness (§5). |
| 3 | Conservative payouts | `reward-policy.md` stage 1: `conservative_effect = max(0, effect - critical_value * standard_error)`; `analysis_plan.critical_value_micro` + `test_sidedness = one_sided_lower`; `minimum_sample` rule; `reward_policy.overflow_policy = proportional_scale_to_budget` bounds total ≤ budget; curve maps input 0 → output 0. |
| 4 | Cohort-level estimand | `manifest.schema.json` `estimand.unit_type` is the const `geo_cohort_time_block`; `reward-policy.md` valuation is per cohort; intra-cohort split never claims individual counterfactuals. |
| 5 | Data minimization | §4; `evidence.schema.json` carries only commitments/roots/integer counts with `additionalProperties:false` and no coordinate/telemetry field; observation leaves hold only a payload commitment. |
| 6 | Chain verifies process, not truth | §1, §3 (verifier CLI adjudicates process); spec language throughout avoids causal overclaim; `design.eligible_for_strong_causal_claim` forced `false` for `observational_replay`. |
| 7 | Devnet only | `manifest.schema.json` `network.cluster` const `devnet`; no fee/token fields; mint is a devnet SPL mint. |
| 8 | Null results are valid | `reward-policy.md`: a cohort with conservative bound ≤ 0 or below minimum sample pays zero; unused budget is recoverable, not force-redistributed; a null distribution is a valid `Final` outcome. |

## 7. Versioning

Every schema and this document carry `spec_version`. Changes are versioned migrations, never
silent edits (Invariant 2 depends on stable bytes). A change that alters canonical bytes bumps
the version and regenerates every affected golden hash in the same commit.
