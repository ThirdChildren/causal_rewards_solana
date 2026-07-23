---
name: ingestion-dedup-semantics
description: Where evidence deduplication happens (ingestion, not the Merkle tree) and why the replay content key is CJSON(full signed batch), not header_hash
metadata:
  type: project
---

**The evidence Merkle tree does NOT deduplicate.** Two *different* producers reporting the
same `(experiment_id, epoch_index, cohort_id)` are two distinct leaves and BOTH are admitted
— differing signatures ⇒ differing `CJSON(batch)` ⇒ differing `leaf_hash` ⇒ strict
monotonicity holds. Independent corroboration is evidence, not duplication. The tree rejects
only a byte-identical leaf (`DUPLICATE_EVIDENCE_LEAF`, adv-03).

**Why:** the tree must be a pure, order-total commitment over whatever was actually anchored.
Baking policy into it would make the root depend on a policy version.

**Real dedup lives at ingestion** (`evidence-service/src/crp_evidence/ingest.py`), three layers:
1. content hash — `SHA-256(CJSON(batch))` over the WHOLE signed batch ⇒ `REPLAYED_BATCH`
2. event nonce — `(experiment_id, epoch_index, cohort_id, producer_pubkey)` ⇒ `DUPLICATE_EVENT_NONCE`
3. correlation checks ⇒ **findings**, never rejections

**Non-obvious trap (cost me a test failure):** the replay content key must NOT be
`header_hash_hex`. `header_hash` covers the batch MINUS `batch_signature`, so two honest
producers signing an identical body for the same cell collide on it and the second gets
wrongly rejected as a replay. Using `SHA-256(CJSON(batch))` (signature included) also makes
one value serve three roles: replay key, CAS object address, and evidence leaf preimage hash
input.

**Order of checks matters:** recompute + compare `header_hash_hex` BEFORE verifying the
signature. Verifying first lets a producer sign a hash of something other than what it
submitted and still pass.

**Findings vs rejections:** silently dropping structurally-valid, correctly-signed but
suspicious data would itself be a selective-reporting attack surface, so it is admitted and
published next to the data (`evidence/findings.json`).

Related: [[merkle-evidence-scheme]], [[bundle-layout-and-parquet]].
