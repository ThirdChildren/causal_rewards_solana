---
name: m3-spec-round-and-v1.2-proposal
description: What the M3 spec round applied (non-hash) vs drafted (v1.2 proposal), and the computed v1.2 candidate golden hashes so they need not be recomputed
metadata:
  type: project
---

M3 spec round completed 2026-07-24 (builds on committed partial 06a2df7). Serialization wire/hash
contract stays **1.1.0**; manifest golden `74e0bb82…0f81b2` + evidence `901b08d5…fa75b` verified
UNCHANGED after all edits.

**Applied (non-hash, Part A):**
- `serialization.md` §9 "1.1.0 addendum" recording §6.5.1 rejection codes + §6.5.2 combine() mapping
  + §8.1 ruling + hac narrowing (all additive/prose).
- `serialization.md` §8.1 RULING: `bundle_logical_hash` (portable, over §2–§5-canonical commitment
  set) is NORMATIVE for the M3 reproduction gate; `bundle_content_hash` (exact Parquet bytes,
  pyarrow-version-scoped) is advisory only. Parquet not byte-stable across pyarrow.
- `manifest.schema.json` `standard_error_method` gained a `description` narrowing `hac` for switchback
  = "unrestricted clustering on the geo group", no frozen bandwidth field (resolves item 7 as doc,
  NOT a new field). Schema-only ⇒ example/golden untouched.
- `reward-policy.md` Appendix A (NON-NORMATIVE) summarizing the multiplicity recommendation.

**Drafted only, needs USER sign-off (`specs/v1.2-migration-proposal.md`):** all hash-moving; adopting
any = major bump 1.1.0→1.2.0 + manifest `spec_version` "1.0.0"→"1.2.0". Computed candidate goldens
(with spec_version bump included):
- **B1 participant pin** (CJSON({cohort_id,participant_id}), participant_id UTF-16/NFC asc): moves the
  participant/bundle root, NOT the manifest. Illustrative 2-leaf root `f32410c1…844018b`.
- **B2 missingness (items 3+6 folded)**: new required `evidence_schedule{epoch_count,epoch_seconds,
  expected_cohort_coverage,missingness_action}` + `design.parameters.missingness_policy` +
  cross-field equality. manifest → **`ac2b4bdc…`** (curve unchanged). Open sub-decision: coverage
  field needs `_micro` scale (§2.2) or rename; recommend collapsing missingness to ONE field.
- **B3 multiplicity+floor (Part C outcome)**: new `reward_policy.multiplicity_control{method,
  fdr_level_micro}` + conservative-effect floor as curve breakpoint `["f_s","0"]` (no new field, moves
  reward_curve). floored `reward_curve_hash` → **`sha256:0123783e…`**; full v1.2 (B2+B3) manifest →
  **`98490aa3…`**. spec_version-bump-alone reference = `78ed3f7a…`.

**Part C recommendation (`specs/multiplicity-recommendation.md`):** BH FDR (α=0.05) for the discovery
threshold + conservative-effect floor for the concentration channel. Structural ruling: a p-value
threshold bounds the fraction of PAID cohorts that are null, NOT the fraction of BUDGET (fixed budget
concentrates under a true null — s2 survivor still takes ~26% after count drops 2→1), so the curve
MUST carry part of the fix. Default stays `none` until sign-off. Per-cohort cap = opt-in, not default.

See [[golden-hashes]], [[spec-versions]].
