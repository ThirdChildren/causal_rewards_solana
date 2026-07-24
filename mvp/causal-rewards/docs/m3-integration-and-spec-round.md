# M3 integration seam + batched spec round (proposal)

**Status:** PROPOSAL. Nothing here is normative. `specs/` is unchanged. The items below are staged
for a single `protocol-architect` run (see §3) and a `causal-inference-engineer` adapter run (see
§1), both deferred until the session window clears (~3am Europe/Rome). This document exists so those
runs are fast execution of a decided plan, not open-ended design.

Owner: orchestrator. Written 2026-07-24, after the two M3 core components landed and were
independently verified (evidence-service `b15d4ef`, causal-engine `11de232`).

---

## 1. Bundle-seam ratification (RATIFIED by orchestrator; no agent needed)

The evidence-service audit-bundle assembler and the causal-engine artifact writers were designed
independently and their contracts did not interoperate. Both sides are internally correct and
gate-green; the break is purely at the assembly seam. Ratified reconciliation:

1. **`rewards.parquet` = the on-chain leaf set.** The bundle slot `rewards.parquet` carries exactly
   the ratified aggregate leaf set (§6.6): one row per recipient, ordered by `leaf_index` ascending
   contiguous from 0. This is what settlement claims against and what the verifier reproduces —
   the file the reward root commits.
2. **The engine's per-(cohort, recipient) Stage-2 detail table renames to `rewards_detail.parquet`.**
   It is supplementary auditability (the CRP-WS1 split), not the settlement source. It is NOT what
   the reward root commits.
3. **Leaf-set column encoding = `recipient_hex` (64 lowercase hex).** This matches the ratified
   reward test vectors (`test-vectors/reward/reward-0x*.json` all key `recipient_hex`) and the
   engine's current output. The assembler currently expects `recipient_pubkey` in **base58**; it
   takes the one-line tweak to (a) rename the required column to `recipient_hex` and (b) decode with
   `bytes.fromhex` instead of the base58 path. We change the side that does NOT reproduce goldens.
4. **`analysis.json` = the engine's richer schema is normative for content**, but MUST additionally
   carry a top-level `evidence_epoch_roots` (echoed from the roots the assembler built, ascending
   epoch order). The assembler validates that field equals the roots it computed and rejects on
   mismatch. Everything else the assembler needs (the primary result numbers) is already present
   under `primary_estimate` / `reward_summary`; the assembler's validator relaxes to those names
   rather than forcing a second `result{…_micro}` block.
5. **`analysis.json.sha256` (over its canonical bytes) is the `result_artifact_hash`.** Unchanged
   from backend's contract.

### 1.1 Preimage-invariance confirmation (REQUIRED gate, CONFIRMED)

The `recipient_pubkey`(base58) → `recipient_hex`(64-hex) change is **presentation only and does NOT
move any hash.** Proof, verified against source on 2026-07-24:

- The frozen leaf preimage (`verifier-cli/reference/reward.py`) is
  `SHA-256(0x00 ‖ "CRP:reward:v1" ‖ recipient ‖ amount_u64_be ‖ leaf_index_u64_be)` where
  `recipient` is **32 raw bytes** (length-checked; hex/base58 never enters the preimage).
- The engine computes `reward_leaf_hash(bytes.fromhex(recipient_hex), …)`.
- The assembler computes `reward_leaf_hash(base58_decode(recipient_pubkey), …)` and independently
  re-derives + compares `leaf_hash_hex`.
- base58(x) and hex(x) of the same 32-byte `x` decode to the same `x`, so the preimage, every
  `leaf_hash`, and the reward root are byte-identical. `reward-01 a9c35cf4`, `-02 ea943182`,
  `-03 b882c899` are unaffected.

**Because the two are decoupled, this is NOT a v1.2 migration item.** If any future change couples
the on-chain reward-root preimage to the Parquet column dtype, that coupling — not this rename —
becomes hash-moving and must move into the migration.

### 1.2 Adapter work (causal-inference-engineer, next turn)

- Rename the Stage-2 detail file `rewards.parquet` → `rewards_detail.parquet`; emit the leaf set as
  the bundle's `rewards.parquet` with columns `(leaf_index, recipient_hex, amount_base_units,
  leaf_hash_hex)`.
- Add top-level `evidence_epoch_roots` to `analysis.json` (accepted as an input from the assembler /
  echoed through the in-process `assemble_bundle` handoff).
- Re-run determinism + reward-golden gates; the reward root MUST stay `a9c35cf4/ea943182/b882c899`.

### 1.3 Assembler work (backend-data-engineer, one line class)

- `REWARDS_COLUMNS` → `("leaf_index", "recipient_hex", "amount_base_units", "leaf_hash_hex")`.
- `_reward_root_from_table`: decode `recipient_hex` via `bytes.fromhex`.
- Relax the `analysis.json` validator to the engine's key schema; keep the `evidence_epoch_roots`
  equality check.

**The verifier CLI (task 3) stays HELD until §1.2 + §1.3 land and a bundle round-trips.**

---

## 2. False-positive / multiplicity study (routed to causal-inference-engineer + protocol-architect)

The frozen reward policy applies a one-sided 5% test **independently per cohort with no family-wise
correction**. On simulator `s2_null_effect` the engine paid ≈29.6% of budget to 2/60 cohorts under a
**true zero effect**. This is a disclosed property of the frozen policy, not an estimator bug.

**Do not decide a priori, and do not frame it as the binary {no correction vs Bonferroni}.** That
frame is wrong: Bonferroni over ~60 cohorts drives per-cohort α to ≈0.0008 and would crush power —
turning our #1 risk-register item (*most cohorts receive zero/uncertain value*) into the default
outcome.

**Structural point the architect must address, not just the threshold:** under a true null the fixed
budget does **not** shrink proportionally — it concentrates. True-zero cohorts get nothing, so a few
false positives absorb a disproportionate share of spend. A threshold correction mitigates but does
not remove this. The architect must also rule on whether the **reward curve or value_scale** should
carry part of the fix (e.g. a floor on conservative effect before any budget is deployed, or a
concavity that caps concentration), not only the p-value threshold.

**Leading candidate to evaluate: false-discovery-rate control (Benjamini–Hochberg).** FWER methods
control the probability of *any* error; here we allocate a *budget across many cohorts* and care
about the *proportion of spend wasted* — which is what FDR controls. BH is deterministic given the
p-values, so it is compatible with a frozen manifest.

### 2.1 Simulator study (causal-inference-engineer — deterministic, benchmark-report material)

Run all six scenarios × four regimes = 24 cells:

- Scenarios: the existing `s1..s6` (incl. `s2_null_effect`, `s3` low-power, `s4` interference,
  `s6` demand-shift confounding).
- Regimes: **none** (current), **Bonferroni**, **Šidák**, **Benjamini–Hochberg (FDR)**.

Report per cell:
1. share of budget paid to true-null cohorts (the waste metric),
2. share of true-positive cohorts correctly paid (the power metric),
3. total budget deployed vs recovered.

Seeded from the committed seed only; two fresh-process runs identical. This comparison is
benchmark-report material regardless of the final choice, so it is not wasted work.

### 2.2 Architect recommendation

`protocol-architect` writes its recommendation **against the §2.1 data**, covering both the
threshold regime and the structural (curve / value_scale) question. If it selects BH or a curve
change, that is a `reward-policy.md` change and — if it adds or changes a frozen manifest field
(e.g. an FDR level or a curve floor) — a hash-moving **v1.2 migration** (see §3).

---

## 3. Batched spec round (protocol-architect, deferred to ~3am)

Nine items. `HASH?` = does it move the manifest golden `74e0bb82…` and therefore require a
deliberate v1.2 migration. **Nothing here is applied until the architect run; ordering-conforming
edits to `specs/` only, one coherent commit, re-verify manifest + evidence hashes after.**

| # | Item | Source | HASH? | Acceptance check |
|---|------|--------|-------|------------------|
| 1 | §6.2 participant leaf form + sort key still UNPINNED. Backend implements the recommendation of record (`CJSON({"cohort_id","participant_id"})`, `participant_id` UTF-16 asc on NFC id) and stamps `PROVISIONAL-UNPINNED-6.2`. Pin it. | backend | **YES** (participant/bundle root moves on ratify; no on-chain verifiability claimed until then) | participant root reproduced by verifier from the bundle; frozen fixture re-pinned |
| 2 | `bundle_logical_hash` (portable, cross-machine) vs `bundle_content_hash` (exact bytes, pyarrow-version-scoped) — which is normative for the M3 gate. Parquet is not byte-stable across pyarrow versions (`created_by`). | backend | no (ruling only) | spec states which hash the M3 "independent reproduction" gate asserts; ties to item 4 |
| 3 | Add `manifest.evidence_schedule {epoch_count, epoch_seconds, expected_cohort_coverage, missingness_action}` + a frozen missingness policy. Manifest currently has no schedule; backend derives it from frozen fields. | backend | **YES** (new required manifest field) → v1.2 | schema validates; example manifest re-frozen; hash migration recorded |
| 4 | Add rejection codes `AGGREGATE_SUMMARY_INCONSISTENT` + `TIME_RANGE_INVALID` to the spec code table (backend enforces both; schema documents the constraints without codes). | backend | no | codes present in the spec table |
| 5 | Multi-batch epoch sub-roots → singular on-chain `EvidenceEpoch.{signer_set_root, observations_root}`. `roots.json` already publishes ordered per-batch lists + `notes.on_chain_epoch_field_mapping`. Decide the mapping. | pre-existing | no (off-chain unchanged; defines on-chain field) | mapping computable from the bundle with no re-ingest; solana-program-engineer confirms |
| 6 | `design.parameters.missingness_policy ∈ {ineligible, impute_cohort_mean}` as a REQUIRED frozen field (engine defaults to strictest `ineligible`). **Overlaps item 3 — reconcile as one missingness decision.** | engine | **YES** → v1.2 (fold with 3) | field required in schema; engine reads it instead of defaulting |
| 7 | `hac_bandwidth_blocks`: `standard_error_method` admits `hac` but nothing pins the bandwidth. Add the field, or document `hac` for `switchback` = "cluster on the geo group". | engine | maybe (if added as field) | spec pins bandwidth or the enum doc is narrowed |
| 8 | `reward-policy.md` Stage-1: state whether a design not `eligible_for_strong_causal_claim` may still settle rewards. Engine reads conservative = no positive payout, discovery-only `analysis.json`. | engine | no (prose) | Stage-1 states the rule explicitly |
| 9 | `reward-policy.md` Stage-1 "cohort c" ambiguity: `min_time_blocks` is per-cohort, which only makes sense if a Stage-1 cohort spans blocks. Engine reads Stage-1 `c` = geo-cohort (aggregating over its blocks); estimand unit stays geo-cohort × block. Reword. | engine | no (prose) | Stage-1 wording unambiguous |

Plus the **§2 multiplicity recommendation** as a tenth, data-gated item — but that one waits on the
§2.1 simulator study and may itself be a v1.2 migration.

**Grouping for the run:** items 4, 5, 8, 9 and the item-2 ruling are non-hash-moving and can land in
one commit immediately. Items 1, 3+6 (single missingness decision), 7-if-fielded, and any §2 outcome
are hash-moving and must be a deliberate, separately-recorded v1.2 manifest migration — never a
silent golden change.

---

## 4. Not on this path

- **M2 devnet deploy + 18/18 integration re-run** is still the single open M2 acceptance item.
  Needs a funded devnet keypair (wallet `yP8HDbBX5f1CP2YzbhHhQ6GT31zggaDiRmt5dDMVe2Q`, 0 SOL; CLI
  airdrop rate-limited; ~9–17 SOL for 4 programs). Owner: user. Unrelated to the M3 seam.
