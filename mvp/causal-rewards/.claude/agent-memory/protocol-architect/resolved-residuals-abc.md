---
name: resolved-residuals-abc
description: How the three M3-prerequisite residuals (reward leaf-set shape, switchback/matched_cluster derivations, evidence sort key) were resolved in serialization v1.1
metadata:
  type: project
---

Three spec residuals ratified in `serialization.md` v1.1 (2026-07-23) as M3 prerequisites, before any
M3 code or golden vector depends on them. **Why:** they were open items blocking verifier golden
vectors for reward + switchback/matched_cluster + evidence roots. **How to apply:** these are now
PINNED contracts — crp-crypto / TS SDK / Python verifier must all agree.

**RESIDUAL A — reward `leaf_index` tie-break (serialization §6.6, reward-policy Stage 2).** Resolved
by pinning the **leaf-set shape = aggregate-one-leaf-per-recipient**: sum a recipient's per-cohort
Stage-2 amounts into one leaf, drop zero-sum recipients. `recipient` (32-byte pubkey) is then a
unique key ⇒ rank key (`recipient` asc, then `amount_base_units` asc) is a total order with NO
tie-break. Duplicate recipient = hard error; SDK reject-on-ambiguity kept as defensive guard.
Resolvable without causal-eng (pure settlement-representation decision downstream of frozen Stage-2;
alters no effect/weight/ratio; preserves budget guarantee via integer sums).

**RESIDUAL B — switchback + matched_cluster derivations (serialization §7.4).** Both reuse the §7.3
PRF (no new primitive), integer-only. Selector = `treatment.assignment_method`. Composite cohort-id
grammar `group"|"index` (these two designs only; single U+007C, canonical uint index).
- **switchback** (assignment_method `switchback_schedule`): per-geo phase bit
  `phase(group)=cohort_prf(seed,exp,group)&1`; `arm=treatment iff ((index+phase) mod 2)==1`.
  Alternation ⇒ requires `treated_fraction_micro="500000"`. carryover/washout are analysis-time only.
- **matched_cluster** (assignment_method `matched_pair`): per-stratum `k_s =
  round_he(treated_fraction_micro*m_s/1e6)` clamped [0,m_s], members ranked by (prf_u64(full id),
  member_index) asc, first k_s treated. Matched pair m=2, frac 500000 ⇒ k=1.
- Two modeling notes flagged for causal-inference-engineer CONFIRMATION (schedule policy; matching
  quality) but they do NOT block vectoring — bytes are pinned; any change would be a versioned migration.

**RESIDUAL C — evidence Merkle leaf sort keys (serialization §6.5).** Confirmed already PINNED &
complete (no byte change): epoch tree sorts by `leaf_hash` asc; obs sub-tree by
`observation_commitment_be32` asc; signer sub-tree by `signer_pubkey_be32` asc (base58 MUST decode to
exactly 32 bytes). All 32-byte unsigned BE compares, strict-monotonic ⇒ dup=hard error. Added a
vector-readiness confirmation note. Adjacent OUT-OF-SCOPE open item noted but NOT fixed: how a
multi-batch epoch's per-batch sub-roots map onto the singular `EvidenceEpoch.signer_set_root` /
`observations_root` on-chain account fields (owned by evidence-registry/state-machine, not the leaf
sort rule).

Next: verifier-reproducibility-engineer produces golden vectors against these. See [[spec-versions]],
[[golden-hashes]].
