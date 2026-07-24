---
name: project-state
description: Current milestone, per-component acceptance status, and milestone gating for Causal Rewards MVP.
metadata:
  type: project
---

# Causal Rewards Protocol MVP — State

**Current milestone:** M2 ACCEPTED-PENDING-DEPLOY (NOT done — see below) + M3 prerequisites started 2026-07-23.

**M2 ACCEPTED-PENDING-DEPLOY (scoped gating exception, user-approved 2026-07-23):** localnet 18/18 green (orchestrator ran scripts/localnet-test.sh directly — build+validator+deploy+ts-mocha, exit 0; solana 4.1.1 off-PATH at ~/.local/share/solana/install/active_release/bin). Single OPEN acceptance item = devnet deploy + 18/18 re-run; BLOCKER funded devnet keypair+RPC, OWNER user; ping at each session start until closed. LIMITS: M3 may proceed on spec/evidence/engine/compiler/verifier; NO M3 task may depend on deployed programs; NO M3 task complete on localnet-alone where devnet is the acceptance path; M3 cannot be accepted while M2 devnet item open. NOT "done". Full text in CONTEXT_HANDOFF.txt M2 ledger.

**M3 PREREQUISITES (must land before M3 impl that consumes them):**
- STEP 3 (architect, then verifier vectors): ratify (a) reward leaf_index tie-break when (recipient,amount) non-unique — SDK currently REJECTS, keep until ratified then all 3 impls agree; (b) switchback + matched-cluster assignment derivations (serialization.md §7.4 open) — deterministic + cross-impl vectored like the 11 cluster-randomized roots; (c) confirm evidence Merkle leaf sort key pinned (§6.5, done in discrepancy-1) + vectored before any evidence root. Bump spec version (v1.1/v1.2 migration), record new ratified hashes in handoff read-from-disk.
- STEP 4 (causal-eng): DONE + orchestrator-verified. canonical.py now matches ratified reference (raw UTF-8, NFC, UTF-16 key order, minimal §4 escaping, dup-key-after-NFC hard error). 60/60 tests incl 11 non-ASCII fixtures (decomposed Unicode, CJK, emoji, astral-vs-BMP UTF-16 order, parity vs ser-* goldens). ASCII baseline 31135b85… UNCHANGED. Documented divergence: sim keeps integer number tokens for its INTERNAL content hash (not on-chain); parity defined on number-free payloads. Committed in 26decfd. Discrepancy #2 CLOSED (pending independent verifier non-ASCII confirmation → folded into next verifier task).
- STEP 3 (architect): DONE + orchestrator-verified. Residual spec edits landed in commit 26decfd (the git-add-A sweep caught architect's FINAL state; git status clean for specs; manifest 74e0bb82/evidence 901b08d5 intact; verifier vectors green). RATIFIED: (A) reward leaf-set shape = aggregate-one-leaf-per-recipient; rank key recipient(BE32) asc then amount asc; recipient unique → no tie-break; zero-sum recipients omitted; §6.6 + reward-policy Stage-2. (B) switchback (phase=cohort_prf&1, arm=(index+phase)%2; forces treated_fraction 500000; carryover/washout are analysis-time only) + matched_cluster (k_s=round_he(frac·m_s/1e6) clamped, members ranked by (prf_u64(full cohort_id),member_index), first k_s treated); composite cohort_id grammar group|index for these 2 designs; §7.4. (C) evidence leaf key confirmed vector-ready §6.5. Wire/hash contract bumped 1.0.0→1.1.0 (additive, hash-compatible); serialization.md §9 revision history.
- FOLLOW-UPS from architect: (B-notes) switchback schedule policy + matching-quality → causal-eng CONFIRMATION, non-blocking (bytes pinned), fold into causal-eng M3 task. (C-adjacent) multi-batch epoch sub-roots → singular on-chain EvidenceEpoch.{signer_set_root,observations_root} mapping — resolve (architect + solana-program-engineer) before evidence roots post on-chain; does NOT block off-chain evidence-root vectors.
- P2+P4 verifier: DONE + orchestrator-verified (committed cc03032). verify_vectors.py exit 0, byte-stable. New ratified roots recorded in CONTEXT_HANDOFF read-from-disk: reward-01 a9c35cf4/02 ea943182/03 b882c899 (+ empty, dup-recipient hard error); assign-12 c7a4253f/13 35f6a7f6 (switchback)/14 e67ebfe9/15 a1116ebf (matched_cluster); evidence-01 a13e1cdc/02 e45697c8/03 1010891b (+empty, signer-not-32 hard error). Sim non-ASCII parity independently CONFIRMED → discrepancy #2 fully CLOSED. New reference modules reward.py + evidence.py; assignment.py extended.

**BUNDLE SEAM CLOSED + ROUND-TRIP VERIFIED 2026-07-24 (session 2, continued).** Both sides landed +
orchestrator-verified + committed: backend assembler tweak e16a9a2 (recipient_hex decode, relaxed
analysis.json validator keeping evidence_epoch_roots binding; 78 tests; evidence roots a13e1cdc/e45697c8/
1010891b UNCHANGED; no frozen bundle golden moved — pinned fixture is evidence-only); causal-eng adapter +
multiplicity study 2964128 (rewards.parquet = leaf set [leaf_index,recipient_hex,amount_base_units,
leaf_hash_hex], per-cohort → rewards_detail.parquet, analysis.json + top-level evidence_epoch_roots; 158
tests; reward roots a9c35cf4/ea943182/b882c899 unchanged; determinism holds).
END-TO-END ROUND-TRIP (orchestrator ran, both pkgs one interpreter): engine writes real rewards.parquet
bytes → crp_evidence assembler reads+validates+recomputes → reward-01 a9c35cf4 = golden. Seam proven
through real code both sides, not just shape-compatible. ⇒ VERIFIER CLI (M3 oracle) UNBLOCKED; dispatched.
MULTIPLICITY STUDY LANDED (docs/multiplicity-study.md, deterministic): 6 scenarios × 4 regimes. KEY
FINDING for architect: every correction cuts s2_null_effect false positives 2→1, yet the lone survivor
still absorbs ~26% of budget — a p-value threshold bounds the fraction of PAID cohorts that are null, NOT
the fraction of BUDGET (fixed budget concentrates under a true null). Fully closing needs a reward-curve/
value_scale floor (flagged, not decided). Default stays `none`; BH = leading threshold candidate. Data now
exists for the architect recommendation (docs §2.2).

**M3 CORE RE-DISPATCHED 2026-07-23 (session 2).** First dispatch (a71719f6/a330baac) died with the
session — NO output landed on disk (causal-engine/ was still README-only, no evidence-pipeline dir).
Baseline re-verified green at session start: manifest 74e0bb82…, verify_vectors.py exit 0 (serialization
+ assignment incl switchback/matched_cluster + reward + evidence + adversarial fixtures).
LESSON: async specialist agents do not survive session end; re-verify their output is ON DISK before
recording a dispatch as in-flight work.
M2 devnet item: user chose "do devnet later this session" — still OPEN, still the sole M2 gate item.

**backend-data-engineer M3 DELIVERED + ORCHESTRATOR-VERIFIED, committed b15d4ef (2026-07-23).**
New `evidence-service/` (ingestion, CAS, §6.5 roots, bundle assembler). Orchestrator independently
re-ran: `make vectors` exit 0 — evidence-01 a13e1cdc / -02 e45697c8 / -03 1010891b / empty 32-zero /
SIGNER_PUBKEY_NOT_32_BYTES all MATCH; `make determinism` 7 passed (separate interpreters);
full suite 78 passed; specs/ + test-vectors/ UNMODIFIED; no forked encoder (imports
verifier-cli/reference by path, zero json.dumps in src/).
Design decisions taken by the agent, ACCEPTED but flagged:
- Replay/dedup identity = SHA-256(CJSON(full signed batch)), NOT header_hash_hex. Correct: header
  hash excludes the signature, so two honest producers reporting the same cell would collide and the
  second be wrongly rejected (violates the ratified "two distinct leaves, both admitted" rule).
- TWO-LEVEL DETERMINISM: parquet is not byte-stable across pyarrow versions (`created_by` embeds it),
  so each table carries canonical_content_hash = SHA256(CJSON(rows)) and the bundle carries
  bundle_logical_hash (portable, cross-machine claim) + bundle_content_hash (exact bytes,
  container-scoped). NEEDS ARCHITECT RATIFICATION: which hash is normative decides what the M3
  verifier gate ("independent reproduction from the bundle") actually asserts.
- Golden epoch vectors carry placeholder signatures, so verify_signatures=False exists for vector
  replay and is stamped into provenance.json. Real RFC-8032 signature path tested separately.

**SPEC ITEMS QUEUED FOR protocol-architect (batch into ONE round with causal-eng's items):**
1. §6.2 participant leaf form + sort key still UNPINNED. Backend implemented the recommendation of
   record (CJSON({"cohort_id","participant_id"}), participant_id UTF-16 asc on NFC-normalized id) and
   stamps participant_root_status "PROVISIONAL-UNPINNED-6.2" in roots.json. Frozen participant/bundle
   hashes WILL MOVE when ratified. No on-chain verifiability claimed until then.
2. Ratify bundle_logical_hash vs bundle_content_hash normativity (see above).
3. No frozen missingness policy; manifest.schema.json has no evidence_schedule. Backend derives the
   schedule from frozen fields and states the derivation in evidence/missingness.json. Proposal: add
   manifest.evidence_schedule {epoch_count, epoch_seconds, expected_cohort_coverage, missingness_action}.
4. Add rejection codes AGGREGATE_SUMMARY_INCONSISTENT + TIME_RANGE_INVALID to the spec's code table
   (schema documents the constraints but names no codes; backend enforces both).
5. STILL OPEN (pre-existing): multi-batch epoch sub-roots → singular on-chain
   EvidenceEpoch.{signer_set_root,observations_root}. Backend did NOT decide it; roots.json publishes
   the full ordered per-batch lists + notes.on_chain_epoch_field_mapping, so any ratified mapping is
   computable from the bundle without re-ingesting.

**causal-inference-engineer M3 DELIVERED + ORCHESTRATOR-VERIFIED, committed 11de232 (2026-07-24).**
Agent DIED on session limit mid-README ("resets 3am Rome"), but code+tests+docs+Dockerfile+
container.lock all landed complete on disk; only the README was the stale stub (orchestrator finished
it, no agent burn). New `causal-engine/` (crp_engine pkg). Orchestrator independently re-ran in a
fresh venv: full suite 143 passed; test_reward_golden.py drives the REAL compiler (finalize_leaves)
against ../test-vectors/reward/ and reproduces reward-01 a9c35cf4 / -02 ea943182 / -03 b882c899 /
empty 00*32 / duplicate-recipient hard error; determinism 6 passed (separate interpreters);
Invariant-3 formula exact in reward_compiler.py (max(0, improvement - margin), min-sample+unidentified
force 0, integer round-half-even); specs/ + test-vectors/ + canonical.py + reward.py UNMODIFIED;
single encoder (imports verifier-cli/reference by path; only json.dumps in demo.py, off the hash path).

**⚠ M3 BUNDLE-SEAM MISMATCH (orchestrator-owned integration, NOT yet resolved) — verifier CLI stays HELD:**
The two agents designed the analysis.json + rewards.parquet contract INDEPENDENTLY and they do not
interoperate. Both sides are internally correct + gate-green; the break is purely at the assembly seam.
- rewards.parquet: evidence-service assembler expects ONE file = the on-chain LEAF SET, cols
  (leaf_index, recipient_pubkey, amount_base_units, leaf_hash_hex), and REFUSES to seal a non-conforming
  bundle. causal-engine emits TWO files: rewards.parquet = per-(cohort,recipient) Stage-2 DETAIL (cols
  cohort_id/recipient_hex/weight/…) + reward_leaves.parquet = the leaf set (col recipient_hex, NOT
  recipient_pubkey). So engine's "reward_leaves.parquet" ≈ backend's "rewards.parquet".
- analysis.json: assembler validates a top-level `evidence_epoch_roots` (must == roots it built) + a
  `result{effect_micro,standard_error_micro,conservative_effect_micro,…}` block + `missingness_handling`;
  its sha256 IS the result_artifact_hash. Engine emits richer `primary_estimate{…_s}` + `reward_summary
  {reward_root_hex}` + `cohorts[]` + `excluded_records`, NO top-level evidence_epoch_roots, different key
  names, missingness under design.missingness_policy + excluded_records. Assembler would REJECT it.
- WHY NOT hand-merged now: editing either side's byte-stable parquet/JSON output could shift their frozen
  determinism goldens (143/78 green) — must be done by the owning agent, and the analysis.json normative
  key schema decides what the M3 verifier gate ("reproduce result hash from the bundle") asserts → needs
  ratification, not an orchestrator guess.
  **RATIFIED 2026-07-24 (user-approved, no agent; full text docs/m3-integration-and-spec-round.md §1;
  committed 3c7b8ef):** bundle `rewards.parquet` = the LEAF SET; engine's per-cohort table →
  `rewards_detail.parquet`; leaf-set column = `recipient_hex` (64-hex — matches the reward-0x goldens +
  engine; change the side that does NOT reproduce goldens, i.e. backend's assembler: rename
  recipient_pubkey→recipient_hex + decode bytes.fromhex not base58, one line class). analysis.json =
  engine's richer schema normative for CONTENT + ADD top-level evidence_epoch_roots (assembler validates
  == roots it built); assembler validator relaxes to engine key names. PREIMAGE-INVARIANCE CONFIRMED
  against source (reward.py): §6.6 preimage consumes 32 RAW bytes; hex/base58 both decode to the same
  bytes → reward roots a9c35cf4/ea943182/b882c899 byte-identical → presentation only, NOT a v1.2
  migration. Adapter = causal-eng next turn (§1.2); assembler tweak = backend (§1.3). This is the gate to
  un-HOLD + build the verifier CLI (task 3, the M3 acceptance oracle).

**SPEC ITEMS QUEUED FOR protocol-architect (ONE batched round; 9 items total):**
From backend (4): §6.2 participant leaf/sort key still UNPINNED (backend stamps PROVISIONAL-UNPINNED-6.2,
those hashes WILL MOVE on ratify); bundle_logical_hash vs bundle_content_hash normativity (decides what
the M3 gate asserts, ties to the analysis.json question above); add manifest.evidence_schedule
{epoch_count,epoch_seconds,expected_cohort_coverage,missingness_action} + frozen missingness policy;
add rejection codes AGGREGATE_SUMMARY_INCONSISTENT + TIME_RANGE_INVALID.
Plus pre-existing: multi-batch epoch sub-roots → singular on-chain EvidenceEpoch.{signer_set_root,
observations_root} (roots.json already publishes ordered per-batch lists + notes.on_chain_epoch_field_mapping).
From causal-engine (docs/modeling-notes.md §6, 5 items): (1) add design.parameters.missingness_policy
∈{ineligible,impute_cohort_mean} as REQUIRED frozen field (engine defaults to strictest=ineligible) —
OVERLAPS backend's missingness item, reconcile as one; (2) add/clarify hac_bandwidth_blocks; (3)
reward-policy.md Stage-1: state whether a design not eligible_for_strong_causal_claim may still settle
(engine reads conservative = no positive payout, discovery-only analysis.json); (4) reword Stage-1
"cohort c" ambiguity (geo-cohort vs geo×block); (5) ⚠ NO cross-cohort MULTIPLICITY control — one-sided 5%
applied independently per cohort → true-null network of N cohorts pays ~5% of them; on sim s2_null_effect
engine paid ≈29.6% of budget to 2/60 cohorts under TRUE zero effect. DISCLOSED design property, not an
estimator bug.
**USER WIDENED THE FRAME 2026-07-24 (do NOT use the binary {none vs Bonferroni}; full text docs
m3-integration-and-spec-round.md §2):** Bonferroni over ~60 cohorts → per-cohort α≈0.0008, crushes power,
turns our #1 risk-register item (most cohorts get zero/uncertain value) into the DEFAULT. Leading candidate
= FDR / Benjamini-Hochberg — FWER controls prob of ANY error, but we allocate a BUDGET across many cohorts
and care about the PROPORTION OF SPEND WASTED = what FDR controls; BH deterministic → frozen-manifest
compatible. STRUCTURAL point architect must also rule (not just threshold): under a true null the fixed
budget CONCENTRATES (does not shrink proportionally) — true-zero cohorts get nothing so a few false
positives absorb disproportionate spend; a threshold fix mitigates but does not remove this → decide
whether the reward CURVE / value_scale carries part of the fix. DATA-GATED: causal-eng runs 6 scenarios ×
4 regimes (none/Bonferroni/Šidák/BH) reporting per regime {share of budget to true-null cohorts, share of
true-positive cohorts correctly paid, total deployed vs recovered}; architect writes recommendation
AGAINST that data. Benchmark-report material regardless of choice. Any adopted correction that adds/changes
a frozen manifest field = hash-moving v1.2.

**ALL M3 PREREQUISITES (P1-P4) LANDED + VERIFIED. M3 CORE DISPATCH (original 2026-07-23):**
- backend-data-engineer (a71719f6): evidence pipeline (ingestion, dedup, content-addressed batches, §6.5 evidence roots — must reproduce evidence-0x goldens) + full audit bundle assembler (byte-stable Parquet). Owns bundle structure + participants/assignment/evidence parquet + roots.json + provenance. Off-chain only; on-chain EvidenceEpoch mapping deferred.
- causal-inference-engineer (a330baac): estimators (cluster-robust SE) + balance/min-sample/sensitivity + reward compiler (Stage-1 conservative LCB max(0,effect-crit*se), no payout under min-sample or <=0; Stage-2 CRP-WS1 split; aggregate-per-recipient leaf-set — must reproduce reward-0x goldens) + analysis.json + rewards.parquet + container digest. Also confirms 2 switchback/matched modeling notes.
- verifier CLI (task 3): HELD until backend bundle format + causal-eng analysis.json/rewards.parquet defined.
- C-adjacent evidence-account mapping (architect + solana-program-engineer): TRACKED, resolve before evidence roots post on-chain; not blocking off-chain M3.

**M3 GATE:** clean machine, no network, reproduce result hash + every reward leaf from published bundle; TS & Python verifiers agree; adversarial fixtures rejected. AND M2 devnet item closed (M3 cannot be accepted while open).

**M2 (historical):** Started 2026-07-20.

**Spec freeze:** git tag `spec-v1-frozen` (annotated, records ratified hashes) at commit 0954bf4eca51e956b642cd50eb2ea225fac98cae, pushed to origin/main. Tag = spec RELEASE discipline; spec changes after = versioned migrations (v1.1/v2), never silent. DISTINCT from freeze-before-reveal runtime invariant. Discrepancy #1 RESOLVED pre-tag (evidence schema conformant + §6.5 leaf sort keys + signer_pubkey len-32); signed off by architect+verifier+backend.

**M2 acceptance gate:** devnet deploy + local integration tests (happy + adversarial) + deterministic assignment vectors agreeing across on-chain program / TS SDK / verifier reference. Every program + claim-logic change routed through security-reviewer before "done".

**M2 component status:**
- verifier assignment vectors + adversarial fixtures: DELIVERED 2026-07-20, ACCEPTED. 11 assignment vectors (roots unchanged for 01-03; added boundary p0/p1e6, count 0/n, n=1 base case, UTF-16 lexical trap assign-09, 16-cohort balanced, 7-cohort odd promotion) + 6 adversarial fixtures in test-vectors/adversarial/ (adv-01 invalid-seed-reveal SEED_COMMITMENT_MISMATCH, adv-02 EPOCH_INDEX_NOT_MONOTONIC, adv-03 DUPLICATE_EVIDENCE_LEAF, adv-04 STALE_EVALUATION_STATE_MISMATCH, adv-05 CONTAINER_DIGEST_MISMATCH, adv-06 NULLIFIER_ALREADY_USED). verify_vectors.py exit 0 (orchestrator ran). These define M2 gate: programs must reproduce roots + reject all 6 fixtures.
- solana-program-engineer: DELIVERED 2026-07-20, committed ff4521a. 4 programs (experiment-registry incl CPI status transitions + set_paused, evidence-registry, settlement, challenge) + crp-crypto shared crate. Orchestrator VERIFIED crp-crypto: cargo test -p crp-crypto 8/8 — reproduces golden seed commitment/PRFs/assignment roots 01-03, Merkle promotion, proof roundtrip. Agent reported anchor build exit 0 + 12 ts integration tests (happy+adversarial) green — NOT independently re-run (needs validator); MUST re-run at devnet acceptance gate. IDLs in idl/ (stable). Freeze-before-reveal structural (no raw-seed field; reveal recomputes commitment, rejects SeedCommitmentMismatch). Single-use claim via ClaimReceipt PDA init. Fees zero, devnet guard, CPI-authority PDAs, multisig.
  DEPLOY NUANCE: default SBPFv0; fresh local test-validator force-activates SIMD-0500 (localnet-test.sh deactivates it); if devnet activates SIMD-0500 switch to --arch v3.
  ON-CHAIN TEST GAP (follow-up): crp-crypto host tests cover only assign-01..03; add 04..11 boundary vectors. Integration covers the 6 adversarial cases per agent.
- reward Merkle leaf preimage: RATIFIED serialization.md §6.6 (committed bcb4cdf). Program's provisional layout accepted AS-IS — sha256(0x00||"CRP:reward:v1"||recipient32||amount_u64BE||leaf_index_u64BE), 48-byte content; leaves ordered by leaf_index ascending contiguous-from-0, dup/gap=hard error; NO experiment_id binding (per-experiment Distribution root + nullifier makes cross-experiment replay impossible). No code rework. RESIDUAL (M3): leaf_index tie-break sub-key pending reward-policy leaf-set-shape decision — before first reward golden root; does NOT affect preimage/SDK. CLEANUP: stale "PROVISIONAL" doc comment in crates/crp-crypto/src/lib.rs — fold into security-review fix pass.
- security-reviewer: DELIVERED 2026-07-20 — **NO-GO, M2 not done**. Core PASS (freeze-reveal, single-use claim, Merkle, checked math, authority/multisig, data-min, devnet). Findings (detail in .claude/agent-memory/security-reviewer/m2-findings.md):
  * H1 (settlement close_experiment:224, gated Final only): budget stranded in all pre-Final states, no abort/timeout recovery. Contradicts threat-model §3.1. FIX: add multisig/timeout-gated recovery → coordinator from pre-Final. Owner: solana-program-engineer.
  * H2 (experiment-registry resolve_upheld:311 + challenge resolve:89): upholding one of multiple concurrent challenges sets status=Evaluating, strands other open challenges' bonds + blocks mark_final (needs open_challenges==0) forever. CODE diverged from state-machine.md tx8 (multi-challenge Challenged→Challenged branch). FIX: resolve_upheld → Evaluating only when post-decrement open_challenges==0, else stay Challenged; add multi-challenge tests. Owner: solana-program-engineer.
  * M1 (mark_final:348 window short-circuit via ever_challenged): a dismissed early challenge collapses the honest challenge window. MATCHES frozen state-machine.md tx9 → needs SPEC decision (v1.1 migration). Owner: protocol-architect.
  * M2 reward-leaf provisional: RESOLVED (§6.6 ratified as-is).
  * M3 (settlement:99-129): total_allocated_base_units not cryptographically bound to reward-leaf sum, only ≤budget. Bounded (vault=budget, unclaimed→coordinator). Consistent w/ Inv 6 (chain verifies process not truth). DOCUMENT; verifier/challenge is real guardrail.
  * L1 no on-chain batch-sig verify (acceptable, data-min); L2 single-key emergency pause (acceptable scope); INFO manifest_hash/cluster are attestations.
- FIX PLAN: architect first decides M1 window rule (v1.1) + documents M3; THEN ONE solana-program-engineer pass = H1 + H2 + M1 + multi-challenge tests + stale crp-crypto PROVISIONAL comment cleanup (minimize expensive program rounds). THEN security-reviewer RE-REVIEW (DoD: no unresolved High).

**2026-07-21 SESSION-LIMIT INTERRUPTIONS (reset 9:20pm Rome):**
- Architect spec-fix run FAILED mid-edit — left an uncommitted, coherent but INCOMPLETE state-machine.md header only: declares state-machine version 1.1.0 with wire/hash contract 1.0.0 UNCHANGED (manifest golden untouched), announces new `abort_experiment` (12 instructions), says tx6/8/9 tightened. Body edits NOT done. RE-DISPATCHED architect (a49a278d) to complete tasks 1-4 building on that header. Do NOT commit state-machine.md until body matches header.
- SDK run FAILED mid-build — left uncommitted partial in sdk/typescript/src/: crypto/ (canonical, merkle, assignment, reward, index), idl/ (json+ts), pda.ts, programs.ts, errors.ts. NO instruction clients, NO tests, NO index yet. Left on disk (uncommitted, unverified). COMPLETE AFTER program fix so IDL is final (H1 adds abort_experiment instruction → IDL gains it → SDK wraps it). Fresh SDK agent builds on the partial + must reproduce all 11 assignment roots.
- VERSIONING NOTE: v1.1 = state-machine/protocol-behavior only; wire/hash contract stays 1.0.0; manifest spec_version field stays "1.0.0"; golden hashes unchanged. spec-v1-frozen tag stays; v1.1 tracked in state-machine §5 revision history.

**v1.1 spec COMPLETE + committed 69a271e (2026-07-21).** Orchestrator verified manifest+evidence hashes intact (only prose files state-machine.md/reward-policy.md/threat-model.md changed). Ratified fixes: tx9 finalize guard = Evaluating AND now>=challenge_window_end AND open_challenges==0 AND evaluation_valid AND multisig (ever_challenged REMOVED); tx8 open_challenges u32 sole gate, per-bond release order-independent; tx12 abort_experiment (Frozen/Active/Evaluating/Challenged → Closed{aborted}, multisig OR timeout evaluation_deadline+abort_grace_seconds, vault→coordinator, refund open bonds, blocked once claims exist); new fields Experiment.{challenge_window_end,open_challenges,evaluation_valid,aborted} + ProtocolConfig.abort_grace_seconds; M3 documented in reward-policy.

**ORCHESTRATOR DECISION (bond forfeit):** dismissed-challenge bond → experiment.coordinator (per v1.1 tx8) accepted for devnet MVP (no real value, invariant 7). FLAGGED for security re-review: coordinator/multisig could collude to dismiss valid challenges + pocket bonds; if this ever nears real value, move to a neutral sink (burn/treasury). Architect offered to adjudicate if we prefer neutral now.

**solana-program-engineer FIX PASS DONE, committed c0bbb0f (2026-07-21).** H1/H2/M1 closed per v1.1. Orchestrator verified: crp-crypto 8/8, manifest+evidence goldens intact, NO salt regression (state-machine.md line 45 is the correct salt-free wording — program agent's flag was false alarm). Agent reports anchor build 0 + anchor test 18/18 (incl 4 new: concurrent-challenge order-independence, uphold-with-pending reaches Final, dismissed doesn't shortcut window, abort returns vault/refunds/rejected-from-Final+timeout case). New instr mark_aborted/abort_experiment/refund_bond; Challenge.resolution 3=REFUNDED; removed evaluation_present/evaluation_invalidated/ever_challenged. IDLs republished. NOTE: 18/18 anchor tests NOT independently re-run (needs validator) — re-run at devnet gate.

**NOW RUNNING (parallel):**
- security-reviewer RE-REVIEW (afb51e4c): changed instructions, confirm H1/H2/M1 closed, new regressions, bond-forfeit collusion recommendation.
- sdk-engineer COMPLETION (a1d54f6d): finish SDK against REPUBLISHED IDLs (re-copy current idl/*.json — gained abort_experiment/refund_bond/mark_aborted + new fields), reproduce all 11 assignment roots (gate), clients for 12 instr + fetchers + claim helper + example + tests. Builds on crashed-run partial in sdk/typescript/src/.

**security-reviewer RE-REVIEW: GO (conditional on devnet gate). H1/H2/M1 all CLOSED with file:line evidence.** Two new Warnings, NOT GO-blockers for devnet MVP:
- W1 (liveness): permissionless-timeout abort_experiment can preempt a finalizable evaluation; abort_grace_seconds not validated vs challenge_window_seconds. Fix: require grace>window at create AND/OR reject timeout-abort when evaluation_valid. TRACKED for M4 hardening (owner solana-program-engineer). Devnet-acceptable (no theft).
- W2 (economic): dismissed-bond→coordinator collusion incentive. Neutral sink (burn/treasury) before real value. TRACKED for M4 (architect specs sink + program implements). Devnet MVP keeps coordinator-forfeit, DISCLOSED in threat-model §3.4.
Orchestrator dispatched architect (doc-only) to add threat-model §3.4 collusion row + W1 note now (honest risk disclosure). W1 code + W2 sink deferred to M4 hardening (in CONTEXT_HANDOFF discrepancy table rows 3-4).

**sdk-engineer COMPLETE, committed e5161e1 (2026-07-21).** Orchestrator VERIFIED: npm test 59 passing, all 11 assignment roots reproduce (seed commitment + prf + leaf bytes/hash) + §6.6 reward leaf; typecheck/build clean. 12+3 clients, 8 fetchers, claim + assignment-root helpers, example. errors.ts derived from IDL errors[] (drift-proof). Full SDK tracked (25 files). NOTE: earlier git add -A commits swept the crashed-run SDK partials into unrelated commits (c0bbb0f/22b060c) — messy history, final state complete/correct.

**THREE-WAY CROSS-IMPL AGREEMENT VERIFIED (core M2 acceptance criterion — MET):** verifier reference (verify_vectors.py exit 0) == on-chain crp-crypto (cargo test 8/8) == TS SDK (npm test 59, 11/11 roots). All reproduce the 11 golden assignment roots + §6.6 reward leaf.

**M2 STATUS: CODE-COMPLETE, security GO. ONLY remaining gate item = devnet deploy + 18/18 integration re-run — needs funded devnet keypair + network (user credentials). Asked user how to proceed.**

Two SDK-noted M-later residuals (non-blocking): reward leaf_index tie-break when (recipient,amount) non-unique (reward-policy M3 residual; assignLeafIndices rejects rather than guessing); switchback/matched-cluster assignment derivations (§7.4 M2 open item).
- sdk-engineer: RUNNING (a0b7e100) — TS SDK against IDLs; must reproduce all 11 assignment roots + §6.6 reward leaf (third leg of the cross-impl agreement). Python mirror deferred.

**Salt erratum confirmed needed:** program agent independently flagged the same stale salt in state-machine.md — already fixed (commit 1268cbc). Good corroboration.

**SPEC ERRATUM (in flight, architect ab7b47f):** state-machine.md §2 tx4 had STALE salted seed-commitment prose contradicting ratified serialization.md §7.2 (salt-free SHA-256("CRP-seed-commit-v1"||seed)). Doc erratum only — behavior unchanged. Architect fixing prose; MUST NOT touch manifest/hashed files (bumping manifest spec_version would break golden 74e0bb…). Tag spec-v1-frozen stays at 0954bf4; erratum is a later main commit, noted in handoff.

**M1 (historical):** Started 2026-07-17. ACCEPTANCE MET 2026-07-20 (all 4 freeze conditions verified by orchestrator).

**FINAL golden hashes (ratified, non-provisional):** manifest_golden_sha256 = 74e0bb825013fcd4a2327b234a5f44c48cd709e7a3025cd30a3b26ace68f81b2 (CJSON byte_len 3852); reward_curve_hash = sha256:14b0ec34d3653a5857ceef10b9bdfee264a6865172c2b2cfb1d2405fae856d41. Dead provisional hashes: 6d39…67ed / 838f…dfca. Orchestrator independently reproduced 74e0bb… via verifier-cli/reference/canonical.py.

**M1 acceptance gate — ALL CLEARED:** (1) reproducible baseline sim ✅ 31135b85…; (2) schemas validate + state machine complete ✅; (3) serialization ratified §3 + golden regenerated ✅; (4) verifier reproduces final golden hash ✅ 74e0bb….

**Recovery doc:** `/CONTEXT_HANDOFF.txt` at repo root — the cold-start recovery document. Keep it updated at end of every milestone and whenever a ratified hash / frozen artifact / carried discrepancy changes. Treat as deliverable.

**Freeze tag spec-v1-frozen:** NOT yet placed. Gated on discrepancy #1 fix + verifier confirm. Tag = spec RELEASE discipline, DISTINCT from freeze-before-reveal runtime invariant — do not conflate.

**Discrepancy #1 (evidence schema): ARCHITECT FIX DONE + orchestrator-verified. Awaiting verifier + backend sign-off, THEN tag.** Architect migrated all 10 evidence numeric fields to number-strings, pinned evidence leaf sort key in serialization.md §6.5 (3 trees: evidence-epoch CRP:evidence:v1 / obs / signer; each ascending by 32-byte byte-lexicographic key: leaf_hash/content-commitment/pubkey; dup=hard error; sol_memcmp on-chain). Orchestrator verified: 0 integer tokens, evidence example validates, serializer accepts (1040 bytes sha256 901b08d5e9aee2cb9861baed18051a9c9b9feeb444502c64b99163d2e51fa75b), manifest golden UNCHANGED 74e0bb…. Reward-tree leaf order still DEFERRED to M3 (reward-compiler output not yet specced); participant-tree order pending M2. Confirm round: verifier (a1f5d9b4…) serializer/determinism STILL RUNNING; backend (a3bf7169…) SIGNED OFF with ONE BLOCKING CONDITION.

**Backend blocking condition (route to architect before tag):** §6.5 must add normative sentence — `signer_pubkey` MUST base58-decode to exactly 32 bytes; any other decoded length = hard error. Reason: base58 regex `{32,44}` chars does NOT pin decoded byte length; variable-length off-chain compare vs fixed 32-byte on-chain sol_memcmp can diverge (invariant 2 gap). One-line clarification, not a redesign. The two hex-derived keys (leaf_hash, content commitment = 64 lowercase hex) are already exactly 32 bytes — fine.

**Backend non-blocking M3 notes (recorded, do NOT gate tag):** (a) signed batch is a pipeline INPUT not regenerated — pin signature bytes in golden vectors (verifier); (b) pipeline must recompute+verify header_hash_hex + batch_signature on ingest, never trust producer-supplied hash; (c) same (experiment_id,epoch_index,cohort_id) from two producers = two distinct leaves, both admitted — dedup/selective-reporting handled at ingestion (event-nonce + correlation), tree does NOT dedup; (d) empty epoch tree = 32-zero root must reconcile with missingness policy; (e) audit-bundle Parquet rows written in canonical leaf-sort order; semantic (cohort,time) exposed only as secondary off-chain index. Header-hash = SHA256(CJSON(batch minus batch_signature)); epoch leaf = CJSON(full batch incl signature) — non-circular.

**Verifier (a1f5d9b4) CONFIRMED PASS all 3 items** — independently reproduced evidence CJSON 1040 bytes sha256 901b08d5… (matches backend + orchestrator), §6.5 leaf order = deterministic total order, nothing blocks M3 golden roots. Verifier ALSO flagged the signer_pubkey base58/len-32 point but called it non-blocking (says decoded-bytes sort key has no real nondeterminism; will enforce len==32 in verifier regardless).

**DECISION: treat signer_pubkey len-32 as BLOCKING (one-line spec fix before tag).** Two independent reviewers flagged it; on-chain sol_memcmp fixed 32-byte vs variable off-chain decode = real divergence risk + invalid-pubkey admission. Cheap insurance. Routed to architect (task pending).

**PLAN:** architect adds §6.5 sentence (name base58 variant = Bitcoin/Solana alphabet; signer_pubkey MUST base58-decode to exactly 32 bytes else hard error). Then orchestrator re-verifies (validate + serializer + manifest unchanged), THEN commit + tag spec-v1-frozen, THEN fire M2.

**Discrepancy #2 (simulator canonical.py NFC/ensure_ascii): CARRIED, owner causal-inference-engineer, fix before sim emits any cross-checked golden hash (M3).**

**Still deferred in serialization.md:** reward-tree leaf sort key (may depend on M3 reward-compiler output); switchback assignment-derivation rules.

**Why:** Grant-scoped 20-week MVP (~95k USDC). Scope discipline is a feature. Devnet only.

**How to apply:** No M2 implementation (`solana-program-engineer`, `sdk-engineer`) until M1
acceptance passes: frozen public spec + reproducible baseline simulator run. Frozen spec is a
hard dependency for M2 and M3.

## Acceptance status per component

- specs/ (protocol-architect): DELIVERED 2026-07-17 as frozen-CANDIDATE, ACCEPTED (not frozen). Orchestrator verified: both schemas validate examples; 11 instr + 8 accounts covered; invariants enforced structurally (devnet const, geo_cohort_time_block const, seed_commitment-only, additionalProperties:false, conservative formula exact). Provisional manifest golden = 6d3957a4f47ad2da5ecdcc96af1bba7d9d7e456ec917debb6db773e5830967ed; reward_curve_hash sha256:838f01dc... serialization.md §3 byte-algo = STUB pending ratify.
- simulator/ + benchmark plan (causal-inference-engineer): DELIVERED 2026-07-17, ACCEPTED. Orchestrator ran `make determinism` + 2 fresh-process hashes: baseline = 31135b85f4c18e4022b58f7d0dbfa1ef018990b29990b331a0048104e165dc67 identical; 41 tests pass. depin_sim pkg in src/ (needs `pip install -e .` for CLI). canonical.py uses micro (1e6) scale + round-half-to-even (matches verifier proposal). assignment.py isolates seed→treatment (placeholder ALPHA_DERIVATION, swappable). 6 scenarios + s4b guardband. KEY FINDINGS: s3 low-power → causal correctly pays ~nothing (only 47/160 cohort-blocks meet min-sample); s4 interference attenuates naive effect (guardband recovers, drops half units); s6 demand-shift confounding FLIPS naive sign (+0.041 true vs -0.032 naive) → observational-replay is discovery-only. Null/low-power = valid publishable outcomes (invariant 8).
- test-vectors/ + canonical serialization (verifier-reproducibility-engineer): DELIVERED 2026-07-17, ACCEPTED — proposal doc + reference impl + serialization/assignment vectors; orchestrator ran self-check (exit 0) + byte-identical regeneration. 9 [RATIFY] items pending architect. Owed: reproduce manifest golden hash post-ratification.
- programs/, sdk/, causal-engine/ estimators, backend, dashboard: NOT STARTED (gated).

## M1 acceptance gate

Frozen spec + reproducible baseline run. Verifier must reproduce the manifest golden hash and
the first assignment root before M1 is declared done.
