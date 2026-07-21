---
name: project-state
description: Current milestone, per-component acceptance status, and milestone gating for Causal Rewards MVP.
metadata:
  type: project
---

# Causal Rewards Protocol MVP — State

**Current milestone:** M2 (Programs & SDK, wk 5–9). Started 2026-07-20. M1 ACCEPTED + spec FROZEN.

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

**M2 GATE remaining:** SDK 11-root cross-impl agreement (sdk-engineer a1d54f6d running) + devnet deploy & 18/18 integration re-run at gate. Security = GO.
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
