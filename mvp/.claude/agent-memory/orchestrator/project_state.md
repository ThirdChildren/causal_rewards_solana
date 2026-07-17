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

**CARRIED to M3 (not freeze blockers, but blockers before dependent work):**
- evidence.schema.json + example still use JSON integer tokens (10 fields) → ratified serializer rejects ints. MUST migrate to number-strings AND pin evidence Merkle leaf sort key (serialization.md §6.2 deferred) in same change before ANY evidence root is committed. Owner: protocol-architect + backend-data-engineer + verifier.
- simulator src/depin_sim/canonical.py latent divergence: uses ensure_ascii + no NFC. Byte-identical for ASCII only; diverges on non-ASCII (escaping, NFC, key order). Reconcile before simulator emits a cross-checked golden hash. Owner: causal-inference-engineer.
- serialization.md §6.2 evidence/reward Merkle leaf sort keys + switchback assignment-derivation rules still deferred → pin before M2/M3 code depends on them.

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
