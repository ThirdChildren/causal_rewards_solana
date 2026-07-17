---
name: interface-decisions
description: Cross-component interface and canonical-serialization decisions and any spec deviations.
metadata:
  type: project
---

# Interface & Serialization Decisions

**Canonical serialization/rounding owner:** `specs/` (protocol-architect ratifies). Verifier
independently implements and must reproduce the golden hash; discrepancies route back to
protocol-architect, spec updated *before* code.

**Why:** Manifest golden hash and every downstream root depend on one canonical byte
representation. Two independent serializers = divergent hashes = broken reproducibility
(invariant 2). Single source of truth prevents silent divergence.

**How to apply:** Any component that hashes or Merkle-roots data uses the canonical rules from
specs/. If an implementer needs a serialization change, route to protocol-architect first.

## Canonical serialization — PROPOSED by verifier (2026-07-17), ACCEPTED by orchestrator, PENDING architect ratification into specs/serialization.md

Verifier reference impl + vectors pass self-check (exit 0) and regenerate byte-identically. Proposal:
- Canonical JSON = strict RFC 8785 JCS subset: UTF-8, no whitespace, keys sorted by UTF-16 code-unit order + unique after NFC, arrays order-significant, NFC on all strings/keys, minimal escaping.
- **No JSON number tokens in any hashed artifact** — all numerics carried as strings (decimal ints; decimals as integer-scaled fixed-point, e.g. `_ppm` @1e6, money in lamports). Serializer raises on int/float. This is the decisive determinism lever (removes IEEE-754/ES6 number corner of JCS).
- Hash = SHA-256 throughout.
- Merkle: `leaf = SHA-256(0x00 || DOMAIN_TAG || canonical_leaf_bytes)`, `node = SHA-256(0x01 || left || right)`; per-tree ASCII tags; data-derived leaf ordering (not insertion); odd node promoted unchanged (avoids CVE-2012-2459); empty root = 32 zero bytes.
- Seed: `seed_commitment = SHA-256("CRP-seed-commit-v1" || seed)` frozen; revealed 32-byte seed drives length-prefixed PRF `SHA-256("CRP-assign-v1" || seed || u32be(len)||exp || u32be(len)||cohort)[:8]` → bernoulli or fixed_count design.

Docs: `verifier-cli/docs/canonical-serialization.md`; vectors in `test-vectors/{serialization,assignment}`.

## 9 decisions needing protocol-architect sign-off ([RATIFY] in doc §8) — forward when architect completes

1. UTF-16 key ordering + ASCII-only key constraint.
2. Per-field fixed-point scales + global rounding mode (HIGHEST divergence risk; loop in causal-inference-engineer).
3. Numeric-string validation regexes (forbid leading zeros / `-0`).
4. NFC normalization form.
5. SHA-256 as sole hash (vs Keccak-256) — note: on-chain program cost matters, check w/ solana-program-engineer at M2.
6. Leaf sort keys for participant/evidence/reward trees.
7. Odd-node promotion vs duplication.
8. Empty-tree root = 32 zero bytes.
9. Seed length 32B, domain tags, u32-BE PRF framing, design set (switchback/matched-cluster unpinned), whether assignment leaf binds experiment_id (verifier recommends NO).

**Owed cross-check:** after architect ratifies, verifier reproduces the manifest golden hash from canonical-bytes level (not architect's assumed field layout).

## Architect open questions needing causal-inference-engineer (batch into architect follow-up)

- Q2: `critical_value` under `student_t` may need a frozen `df` as first-class manifest field (determinism). Currently in design.parameters.
- Q3: `intra_cohort_split.weight_formula` is a constrained string with no formal grammar; engine + verifier must agree on a deterministic evaluable subset before M3.
- Q4: switchback/interference params (carryover/washout, interference assumption) not yet pinned in manifest — confirm whether must be frozen.
- RATIFY #2 (per-field fixed-point scales + rounding mode) also needs causal-eng — highest divergence risk.

## Sequencing decision (no SendMessage tool available — cannot resume agents with context)

Continuing an agent = fresh cold spawn. To avoid two cold architect spawns, HOLD architect follow-up until causal-inference-engineer returns, then spawn ONE consolidated protocol-architect task: ratify serialization.md (all 9 RATIFY items, using causal-eng's numeric-scale/df/weight-grammar decisions) → regenerate golden hashes → drop PROVISIONAL. Then verifier reproduces golden hash. Then freeze.

## Orchestrator directives for architect ratification (2026-07-17)

- RATIFY #2 scales/rounding: adopt verifier + causal-eng convergent choice — integer-scaled fixed-point, micro (1e6) default, round-half-to-even. Both impls already use it. Architect pins per-field scale table in serialization.md.
- Q2 (student_t df): ADD frozen `df` as first-class manifest field. Determinism requires the critical value be reproducible without recomputation. Directive.
- Q3 (weight_formula grammar): pin a NAMED restricted arithmetic grammar in reward-policy.md (weighted sum over declared non-negative quality attributes, normalized). Formal evaluator = M3; grammar spec must exist pre-freeze so the frozen string is unambiguous.
- Q4 (switchback/interference params): FREEZE carryover/washout + interference assumption as design.parameters (invariant 1 — part of pre-analysis plan). Directive.
- RATIFY #5 (SHA-256 vs Keccak): SHA-256 (verifier rec). Both have Solana syscalls; revisit compute-unit cost with solana-program-engineer at M2 but not a freeze blocker.

Simulator canonical.py + verifier reference already agree on micro/round-half-even → low reconciliation risk. sim assignment.py swap to canonical derivation deferred to M2/M3 (isolated).

## Resolved spec deviations

- 2026-07-17: serialization ratified into specs/serialization.md §2/§3 (verifier proposal adopted wholesale). Provisional golden hashes superseded; final = 74e0bb… / 14b0ec…. Verifier reference reproduces both. Manifest fully number-free (every numeric field type:string + canonical-integer regex) — this is what makes it hashable.
- Q2 resolved: analysis_plan.df added (required iff student_t, forbidden for normal_approx).
- Q3 resolved: weight_formula grammar = CRP-WS1 (normalized weighted sum over closed attribute vocab; products must be pre-declared compound attrs). Evaluator = M3.
- Q4 resolved: design.parameters.interference_assumption (enum) + carryover_blocks/washout_blocks (required for switchback). Sim ground-truth knobs explicitly banned from schema.

## Open, carried past M1 freeze (see project_state carried list)

- evidence artifact number-string migration + evidence Merkle leaf sort key (serialization.md §6.2) — before any evidence root.
- simulator canonical.py NFC/ensure_ascii reconciliation — before sim cross-checked golden hash.
