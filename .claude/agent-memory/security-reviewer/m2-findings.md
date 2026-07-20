---
name: m2-findings
description: Living findings log for the M2 Solana programs review (experiment-registry, evidence-registry, settlement, challenge, crp-crypto)
metadata:
  type: project
---

# M2 Programs Security Findings Log

First full review: 2026-07-20 (spec-v1-frozen). Reviewer = security-reviewer. Read-only.
Programs at `mvp/causal-rewards/programs/*` + `crates/crp-crypto`.

**Why:** M2 acceptance (devnet deploy + integration tests + assignment vectors). Milestone
cannot be "done" while a Critical/High is open. SDK is meant to be built against these next.
**How to apply:** consult before any re-review; do not re-litigate resolved items; verify
each open item against current code (grep the instruction) before re-reporting.

## OPEN findings (status as of 2026-07-20)

- **H1 — Pre-Final budget stranding (settlement).** Only recovery instruction is
  `close_experiment`, gated on `status == Final`. No abort/cancel/timeout for
  Draft/Frozen/Active/Evaluating/Challenged. If coordinator never reveals or evaluator never
  submits (or multisig never finalizes), the funded vault is permanently locked. Directly
  contradicts threat-model §3.1 ("budget is recovered via close_experiment" for the stall case).
  Fix: add multisig/timeout recovery reachable from pre-Final states. Devnet + self-funded
  reduces blast radius but the promised mitigation does not exist.
- **H2 — Multi-challenge upheld strands pending challenges + blocks finality (challenge +
  registry).** `resolve_upheld` unconditionally sets status=Evaluating and decrements
  open_challenges by 1, ignoring other still-open challenges. With ≥2 simultaneous challenges
  (expected per threat-model §3.4), upholding one leaves status=Evaluating with open_challenges>0;
  the other Challenge is now unresolvable (resolve requires status==Challenged), its bond is
  locked in bond_vault forever, and `mark_final` (needs open_challenges==0) can never fire →
  finality blocked indefinitely. Spec transition 8 intends Challenged→Challenged when others
  pending; code diverges. Fix: only go to Evaluating when the decrement reaches 0, else stay
  Challenged; ensure every opened challenge remains resolvable and its bond releasable.
  UNTESTED — integration tests only cover single dismissed challenge.

## MEDIUM / LOW / INFO (open, non-blocking)

- **M1 — `ever_challenged` short-circuits the challenge window (registry `mark_final` L348-351).**
  `now >= challenge_window_end || ever_challenged`. One early opened+dismissed challenge lets
  finalize proceed immediately, collapsing the window for all not-yet-opened honest challenges.
  Matches frozen spec transition 9 wording, so fixing needs a protocol-architect spec change.
- **M2 — Reward-leaf determinism boundary (crp-crypto L189-206 + settlement claim).** On-chain
  claim hard-depends on the PROVISIONAL 48-byte BE preimage `recipient||amount_be||index_be`.
  serialization.md §6.2 defers reward leaf identity/ordering to M3. If M3 ratifies a different
  preimage, settlement claim verification must change → SDK claim path may need rework. Flagged,
  not blocking (ratification in flight).
- **M3 — total_allocated not bound to reward_root (settlement finalize).**
  `total_allocated_base_units` is caller-supplied and only checked ≤ budget; not cryptographically
  tied to the committed leaves. Over/under accounting possible, but vault balance = budget caps
  real payout and unclaimed returns to coordinator, so no funds are created. Relies on
  verifier+challenge (consistent with Inv 6). Note only.
- **L1 — post_evidence_epoch does not verify batch signature on-chain** (spec transition 5 says
  "batch signature valid"); only stores `producer` pubkey. Signature checked off-chain by verifier.
- **L2 — Single-key emergency pause** (ProtocolConfig.admin). Admin can pause indefinitely (grief);
  no auto-expiry / not multisig. Acceptable as emergency-pause-only per CLAUDE.md; consider hardening.
- **INFO — manifest_hash / cluster guard are attestations, not on-chain-verifiable.** manifest bytes
  never on-chain; `cluster` is a stored flag, not a real network check. Inherent; multisig + verifier
  cover it.

## PASS (verified this round)

- Freeze-before-reveal structural encoding (Inv 1): reveal gated on Active+cohort_published+seed
  unset + commitment recompute; publish gated on Frozen+seed unset; frozen fields never rewritten.
- Single-use claims: ClaimReceipt PDA `init` on seed [claim, experiment, leaf_index]; no cross-exp
  collision (experiment in seed + per-exp reward_root + per-exp vault). recipient bound in leaf + signer.
- Merkle: 0x00 leaf / 0x01 node domain separation, promotion (not duplication), per-tree domain tags,
  empty=32 zero bytes. Second-preimage (node-as-leaf) blocked. Matches serialization.md §6.
- Checked math + hard-zero fees (fee_bps==0 asserted, never applied).
- CPI authority: satellite status writes gated by seeds::program CPI-authority PDA signer; status
  only writable by registry. Multisig m-of-n distinct-signer count enforced on freeze/finalize/resolve.
- Data minimization (Inv 5): only hashes/roots/counts/coarse labels/pubkeys on-chain.

## Threat-case coverage matrix (control verified? / test present?)

| Threat | Control found | Adversarial test |
| --- | --- | --- |
| Post-result rule change | freeze immutability set, no rewrite path | partial (re-freeze/re-publish rejected) |
| Assignment manipulation (seed choice) | publish-before-reveal + on-chain commitment recompute | reveal-mismatch rejected |
| Duplicate/replayed evidence | epoch PDA init + monotonic prev-epoch | duplicate epoch rejected |
| Reward-root substitution | dist.reward_root read from bound Evaluation PDA | no direct test |
| Claim replay / double-claim | ClaimReceipt init nullifier | double-claim + forged-amount rejected |
| Evaluator tampering | container digest echo + verifier/challenge | none on-chain (by design) |
| Authority compromise | multisig; single-key pause (L2) | freeze-below-threshold rejected |
| Griefing / indefinite challenge | bonds + window | ONLY single dismissed challenge; H2 multi-upheld UNTESTED |
| Fund stranding | close_experiment (Final only) — GAP H1 | none |
