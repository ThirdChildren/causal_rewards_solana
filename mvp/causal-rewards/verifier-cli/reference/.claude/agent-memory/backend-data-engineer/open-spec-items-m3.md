---
name: open-spec-items-m3
description: Spec gaps hit while building the M3 evidence pipeline — participant leaf unpinned, no manifest missingness policy, multi-batch epoch to singular on-chain fields
metadata:
  type: project
---

Three items were NOT decided by backend-data-engineer; each is disclosed in the artifact
itself so a bundle never over-claims.

1. **Participant leaf form + sort key are UNPINNED.** `serialization.md` §6.2 says they are
   fixed "when the participant golden root lands" and offers a recommendation of record. The
   evidence service implements exactly that recommendation — leaf
   `CJSON({"cohort_id", "participant_id"})` under `CRP:participant:v1`, order `participant_id`
   ascending by UTF-16 code unit of the NFC-normalized id — and stamps every value
   `participant_root_status: "PROVISIONAL-UNPINNED-6.2"` in `roots.json`.
   **How to apply:** do not claim on-chain verifiability of the participant root, and expect
   the frozen participant/bundle hashes to move, until protocol-architect ratifies §6.2.

2. **No frozen missingness policy in `manifest.schema.json`.** The schedule is DERIVED from
   frozen fields (`estimand.time_block.block_count` / `.block_seconds`,
   `windows.active_start`, plus the published cohort set). Sound but implicit.
   **Proposal filed:** explicit `manifest.evidence_schedule { epoch_count, epoch_seconds,
   expected_cohort_coverage, missingness_action }`.

3. **Multi-batch epoch → singular on-chain `EvidenceEpoch.{signer_set_root,
   observations_root}`.** Owned by protocol-architect + solana-program-engineer. The bundle
   publishes the full ordered per-batch sub-root lists under
   `roots.json → roots.evidence_epochs[].per_batch_*` so any ratified mapping is computable
   from the bundle without re-ingesting.

**Why these are disclosed rather than resolved:** `specs/` wins over any implementation; an
implementation that silently invents a rule creates a divergence that only surfaces at
on-chain verification time.

Related: [[merkle-evidence-scheme]], [[bundle-layout-and-parquet]].
