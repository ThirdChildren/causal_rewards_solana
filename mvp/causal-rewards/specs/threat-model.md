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
| Keep the experiment in `Challenged` forever. | Finalization requires **both** `now ≥ challenge_window_end` **and** `open_challenges == 0` (`finalize_distribution`, `state-machine.md` tx9). A challenger cannot stall past the window by leaving a challenge open indefinitely: `resolve_challenge` (multisig) drives `open_challenges` to 0, and if the whole flow is abandoned, `abort_experiment` (multisig or the permissionless timeout `evaluation_deadline + abort_grace_seconds`) unwinds it and refunds open bonds. Neither a stuck challenge nor a coordinator walk-away can trap funds pre-`Final`. |
| Open a challenge, then let it be dismissed, to collapse the finalize window early for honest not-yet-opened challengers. | Fixed guard (finding M1): the removed `ever_challenged` short-circuit no longer exists. Finalize still requires `now ≥ challenge_window_end`, so a dismissed challenge (which only decrements `open_challenges`) cannot shorten the honest window. |
| Frivolous challenge to extract a settlement. | Resolution is adjudicated against a verifier CLI re-run, not negotiation; a correct evaluation cannot be overturned, so there is nothing to extract. |
| **(Inverse — coordinator/authority side.)** Coordinator dismisses a *valid* challenge to capture the honest challenger's forfeited bond. | **Residual — tracked, W2.** On `resolve_challenge`, a *dismissed* challenge's bond currently forfeits to `experiment.coordinator` (`state-machine.md` tx8). Because resolution is multisig-gated (C-MULTI) and the coordinator is typically aligned with the resolving multisig, this composes evaluator-tampering (§3.2) with authority-compromise (§4, key compromise) into an incentive to *wrongly dismiss* correct challenges and pocket the bond. **Current on-chain control: none** beyond off-chain detectability — an honest party's verifier CLI re-run still shows the challenge was correct, making the wrongful dismissal publicly visible (but not reversible or penalized on-chain). See §5 (W2) for the accepted-for-devnet decision and the M4 remediation. |

## 4. Residual risks (out of scope for on-chain enforcement)

- **No concentration bound and no waste bound (plain-language limit — read before wiring to live
  incentives).** The chain enforces the reward-curve **shape** deterministically: given the frozen
  `reward_curve` and the conservative per-cohort effects, every party recomputes the identical
  allocation (Invariant 2). It does **not** guarantee a **concentration bound** (a ceiling on how much
  of the budget a single cohort can absorb) nor a **waste bound** (a ceiling on how much budget can
  flow to cohorts that added no real value). Under a true null the protocol correctly pays ~0 *in
  aggregate relative to budget* and recovers the rest (Invariant 8), but a single chance cohort can
  still absorb a large share if the frozen curve values one cohort highly — that is a **calibration
  property of the chosen curve, not something the chain certifies.** The chain **cannot certify
  targeting** (that spend went to genuinely additional cohorts) without assuming the very causal truth
  it is forbidden to assume (Invariant 6 — the chain verifies process, not truth). A manifest author
  who wants a concentration ceiling can freeze a *saturating* `reward_curve` (a curve shape, needs no
  new field); the recommended default calibrated + saturating-cap curve is published guidance
  (`specs/multiplicity-recommendation.md` §4), not a protocol-enforced constant. **Integrators wiring
  this to real incentives must supply their own concentration/waste controls; the protocol does not.**
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

## 5. Deferred hardening items (tracked for M4)

These are *known* on-chain gaps surfaced by the M2 security re-review (verdict: GO with two
Warnings). They are **not** permanently out of scope like §4; they are disclosed here and tracked
for the M4 hardening milestone. Each is **accepted for the devnet, zero-value MVP** under
Invariant 7 (no mainnet, no token, no custody of real budgets), and each **MUST** be remediated
before any real-value deployment. No protocol behavior, schema, or hashed artifact changes as part
of this disclosure — the fixes land in M4.

### W2 — dismissed-challenge bond forfeits to the coordinator (collusion incentive)

- **Risk.** A *dismissed* challenge's bond is currently paid to `experiment.coordinator`
  (`state-machine.md` tx8 `resolve_challenge`). Challenge resolution is multisig-gated (C-MULTI),
  and in the reference topology the coordinator is typically aligned with the resolving multisig.
  This creates a direct incentive to dismiss *valid* challenges in order to capture honest
  challengers' bonds — a composition of evaluator-tampering (§3.2) and authority compromise
  (§4, key compromise). See the inverse row in §3.4.
- **Current on-chain control.** None beyond off-chain detectability: an independent verifier CLI
  re-run still demonstrates that the dismissed challenge was correct (C-DET, Invariant 6), making a
  wrongful dismissal publicly visible — but the on-chain resolution is neither reversed nor
  penalized, and the forfeited bond is not recoverable on-chain.
- **Decision.** Accepted for the devnet, zero-value MVP (Invariant 7): with no real bond value at
  stake the incentive has no economic bite. **MUST** be fixed before any real-value deployment.
- **Intended M4 remediation.** Route a dismissed challenge's bond to a **neutral sink** — either
  burn it, or send it to a config-level treasury that is **not** controlled by the coordinator —
  so that dismissing a challenge yields no gain to the resolving authority.

### W1 — permissionless abort can discard earned rewards from `Evaluating` (liveness inversion)

- **Risk.** The permissionless-timeout branch of `abort_experiment` (`state-machine.md` tx12)
  opens at `evaluation_deadline + ProtocolConfig.abort_grace_seconds`. `create_experiment` (tx1)
  does **not** currently enforce any relation between `abort_grace_seconds` and
  `challenge_window_seconds`. If `abort_grace_seconds` is not strictly larger than
  `challenge_window_seconds`, the timeout-abort branch can open *while a valid, ready-to-finalize
  evaluation is still inside its (legitimate) challenge window*. Any caller could then abort a
  sound experiment out of `Evaluating`, returning the vault to the coordinator and discarding the
  rewards the evaluation earned. This is a **liveness inversion (no theft):** no attacker is paid,
  but honest earned rewards can be destroyed and the flow forced to restart.
- **Current on-chain control.** None specific to this branch: tx12's timeout guard checks only
  `now > evaluation_deadline + abort_grace_seconds` and pre-`Final` status; it does not exclude a
  still-valid in-window evaluation, and tx1 does not constrain the grace/window relation.
- **Decision.** Accepted for the devnet, zero-value MVP (Invariant 7): experiments carry no
  real-value budget, so a spurious abort costs only re-execution. **MUST** be fixed before any
  real-value deployment.
- **Intended M4 remediation.** Enforce `abort_grace_seconds > challenge_window_seconds` as a
  precondition at `create_experiment`, **and/or** reject the permissionless timeout-abort branch
  when `status == Evaluating && evaluation_valid == true` (i.e., never let the timeout path discard
  a valid, unchallenged, ready-to-finalize evaluation). The multisig abort path is unaffected.
