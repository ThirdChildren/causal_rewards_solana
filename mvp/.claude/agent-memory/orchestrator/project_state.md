---
name: project-state
description: Current milestone, per-component acceptance status, and milestone gating for Causal Rewards MVP.
metadata:
  type: project
---

# Causal Rewards Protocol MVP — State

**Current milestone:** M1 (Spec & benchmark, wk 1–4). Started 2026-07-17. ACCEPTANCE MET 2026-07-17 (all 4 freeze conditions verified by orchestrator). Awaiting user go-ahead to commit/tag the frozen spec and authorize M2.

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
