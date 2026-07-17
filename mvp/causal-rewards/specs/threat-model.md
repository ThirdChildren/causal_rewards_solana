# Threat Model

**Spec version:** 1.0.0
**Status:** M1 frozen-READY (awaiting orchestrator freeze gate).

Scope: the MVP settlement + measurement layer on **devnet** (Invariant 7). The chain verifies
*process*, not the truth of the causal estimate (Invariant 6); this model covers integrity of the
process, not the external validity of the experiment's assumptions. The independent oracle is the
**verifier CLI**, which recomputes every root from an audit bundle with no network access and no
trust in the coordinator or evaluator.

## 1. Trust assumptions

- The Solana program logic and the verifier CLI are trusted (open-source, audited-shaped).
- Every human role — coordinator, evaluator, participant, challenger — is partially adversarial.
- The multisig is honest-majority up to its threshold `m` of `n`; no single signer is trusted.
- SHA-256 collision resistance and Ed25519 signature security hold.
- At least one honest party can run the verifier CLI and open a challenge within the window.

## 2. Controls (defensive primitives)

- **C-FREEZE — freeze-before-reveal (Invariant 1).** Manifest is hashed and frozen before the
  seed is revealed and before any outcome analysis. Structurally: the seed has no field in the
  manifest; `reveal_seed` is legal only after `freeze_experiment` → `publish_cohort_root`.
- **C-COMMIT — commitments.** Assignment-seed commitment; cohort/assignment root published
  before reveal; signer-set Merkle root; observations Merkle root; reward-curve hash; pinned
  analysis-container digest; result-artifact hash; finalized reward root.
- **C-DET — determinism (Invariant 2).** One canonical serialization, no floats in hashed
  artifacts, seed-only randomness, pinned container ⇒ any party reproduces every root.
- **C-BOND — challenge bond.** A challenge requires an escrowed bond, forfeited on a dismissed
  challenge; returned when upheld.
- **C-MULTI — multisig.** Freeze, challenge resolution, and finalization require `m`-of-`n`.
- **C-CONS — conservative payouts (Invariant 3).** Lower confidence bound, minimum-sample gate,
  overflow scaling ⇒ over-payment and noise-mining are bounded.
- **C-COHORT — cohort-level estimand (Invariant 4).** Valuation is per geo-cohort × time-block;
  device-level identities affect only the intra-cohort split, never a cohort's valuation.
- **C-MIN — data minimization (Invariant 5).** Only commitments/roots/counts on-chain; no
  telemetry/coordinates/personal data anywhere.

## 3. Adversaries and mitigations

### 3.1 Malicious coordinator
Goals: bias the assignment to favor cohorts it profits from; alter the plan after seeing
outcomes; fabricate evidence; leak/inject raw data.

| Attack | Mitigation |
| --- | --- |
| Choose the assignment seed after seeing which split maximizes reward. | C-FREEZE + C-COMMIT: seed is committed at freeze and the cohort root is published *before* `reveal_seed`. A revealed seed must open the commitment and reproduce the published root, so the seed is fixed before any outcome is knowable. |
| Edit the estimator, reward curve, minimum-sample, or windows after freeze. | Frozen immutability set (`state-machine.md` §3); `manifest_hash` on-chain; no admin path rewrites frozen records. Any divergence changes the hash and is rejected. |
| Publish a cohort root that does not match the frozen assignment method. | C-DET: anyone recomputes the assignment from frozen method + revealed seed and compares to `cohort_root`; mismatch is a challengeable, provable fault. |
| Fabricate observations or a signer set. | C-COMMIT: signer-set root commits to the contributing keys; observation leaves are individually signed (Ed25519) and committed under the observations root. Unsigned/forged leaves fail verification. |
| Put raw telemetry or coordinates on-chain, or leak them via artifacts. | C-MIN: `evidence.schema.json` has `additionalProperties:false` and no telemetry/coordinate field; even off-chain leaves carry only a payload commitment. |
| Stall — never reveal the seed or never post evidence. | Liveness-only power. Windows bound it: without `reveal_seed` + evidence the evaluator cannot submit and the flow cannot reach `Final`; budget is recovered via `close_experiment`. Coordinator gains nothing (no self-payout path). |

### 3.2 Malicious / colluding evaluator
Goals: produce a self-serving result; use analytic degrees of freedom; collude with the
coordinator to over-pay a cohort.

| Attack | Mitigation |
| --- | --- |
| Swap the estimator, SE method, confidence level, or reward policy to inflate payouts. | All frozen pre-reveal (immutability set). The submitted `analysis_container_digest` must echo the frozen one. |
| "Garden of forking paths" — try many analyses, report the favorable one. | C-FREEZE: the entire analysis plan is the pre-analysis plan, frozen before reveal. No post-hoc choices remain. |
| Submit a reward root that does not follow from the bundle. | C-DET + verifier CLI: the reward root is recomputed from the frozen plan + bundle; a non-reproducible root is upheld on challenge (C-BOND) and the evaluation invalidated (`resolve_challenge` → back to `Evaluating`). |
| Inflate a cohort's effect using noise. | C-CONS: one-sided lower bound `max(0, effect − critical_value·SE)`, minimum-sample gate, and ≤0 → zero. Pure noise does not clear the bound. |
| Collude with coordinator to over-pay beyond budget. | C-CONS overflow policy scales all allocations so total ≤ budget; C-MULTI gates finalization; a bad finalization is publicly visible and challengeable before it, and reproducibility makes collusion detectable. |

### 3.3 Sybil participant
Goals: split one device into many identities, or spin up cheap identities, to capture more reward.

| Attack | Mitigation |
| --- | --- |
| Register many identities to raise a cohort's *valuation*. | C-COHORT: valuation is at the geo-cohort × time-block level and derives from the measured causal effect on held-out error — not from headcount. Adding identities to a cohort does not raise that cohort's conservative effect. |
| Split a device across identities to grab a bigger slice. | Intra-cohort split is a *frozen* quality-weighted rule over evidence-derived weights (`intra_cohort_split.weight_formula`). Splitting the same underlying signal across identities divides the same weight; it does not create new accepted-observation quality. It can only redistribute *within* the cohort's fixed allocation, never increase it. |
| Flood low-quality observations to pad accepted counts. | Validation rejects them (`aggregate_summary.rejected_count`); weights use quality scores, not raw counts alone; and minimum-sample thresholds are on genuine accepted observations. |
| Register a device in a cohort it is not in, to ride a high-value cohort. | Signer-set commitment binds contributors to the cohort; a non-contributor has no signed leaf under that cohort's observations root and earns no weight. |

### 3.4 Griefing challenger
Goals: stall finality, harass the coordinator/evaluator, force repeated re-work.

| Attack | Mitigation |
| --- | --- |
| Open baseless challenges to pause finality. | C-BOND: each `open_challenge` escrows a bond ≥ `challenge_bond_base_units`, forfeited when the challenge is dismissed. Griefing has a per-attempt cost. |
| Spam many challenges. | Each is a separate `Challenge` with its own bond; cost scales linearly with attempts. C-MULTI resolves them; only an *upheld* (verifier-backed) challenge invalidates the evaluation. |
| Keep the experiment in `Challenged` forever. | Finalization is permitted once all challenges are resolved with none upheld, or the challenge window elapses (`finalize_distribution` guards). The window bounds indefinite stalling. |
| Frivolous challenge to extract a settlement. | Resolution is adjudicated against a verifier CLI re-run, not negotiation; a correct evaluation cannot be overturned, so there is nothing to extract. |

## 4. Residual risks (out of scope for on-chain enforcement)

- **External validity of the estimate.** The chain cannot certify that the design's assumptions
  (SUTVA/no interference, correct counterfactual, no unmodeled confounding) hold. `observational_replay`
  is explicitly barred from the strongest claim (`design.eligible_for_strong_causal_claim = false`);
  network-interference and switchback caveats are design-review concerns, not settlement concerns.
- **Off-chain data availability.** If the coordinator withholds the audit bundle, results cannot
  be reproduced or challenged; the mitigation is procedural (publish the bundle), backed by the
  fact that a withheld bundle blocks reaching `Final`.
- **Key compromise.** Compromise of a threshold of multisig signers, or of the coordinator key,
  is outside this model's protection; standard key hygiene applies. Devnet-only scope (Invariant 7)
  bounds the blast radius for the MVP.
