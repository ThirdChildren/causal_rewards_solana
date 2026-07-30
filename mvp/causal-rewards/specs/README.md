# specs/ — Protocol specification (source of truth)

Owned by `protocol-architect`. **`specs/` wins over any individual implementation.** If an
implementation needs a spec change, propose it here and update the spec *before* the code —
never silently diverge.

## Contents (M1)

- `protocol.md` — narrative spec: lifecycle, actors, trust model, on-chain vs off-chain,
  and the invariant-enforcement map (all 8 invariants → where enforced).
- `manifest.schema.json` — experiment manifest = the pre-analysis plan (JSON Schema 2020-12).
- `examples/manifest.example.json` — canonical, schema-valid manifest instance.
- `manifest.golden.md` — FROZEN golden hash of the canonical manifest + the exact
  serialization/hash used.
- `evidence.schema.json` — signed evidence batch (commitments/roots/counts only, no telemetry).
- `examples/evidence.example.json` — canonical, schema-valid evidence instance.
- `state-machine.md` — `Draft → Frozen → Active → Evaluating → Challenged → Final → Closed`;
  all 11 instructions + 8 accounts, guards, and the immutability set frozen at `Frozen`.
- `threat-model.md` — adversaries (coordinator, evaluator, Sybil, griefer) × controls.
- `reward-policy.md` — two-stage allocation (cohort conservative effect → frozen
  quality-weighted intra-cohort split) with exact integer formulas.
- `serialization.md` — canonical serialization rules (NORMATIVE, RATIFIED): the full byte-level
  algorithm (numbers-as-strings, CJSON, SHA-256, Merkle, seed commit/reveal) an independent
  implementation reproduces exactly.

## v1.2 (approved scope: frozen missingness ONLY, 2026-07-30)

- `v1.2-migration-proposal.md` — S1 (frozen `design.parameters.missingness_policy`, **collapsed
  single-field form**) is APPROVED and LANDING as a specs-only staged commit; S2 retired (no spec
  field), S3 deferred out of scope, B1 independent. **The manifest golden moves `74e0bb82…` →
  `ba632e8a…`** by this landing; `reward_curve_hash` and evidence golden are unchanged. Cross-impl
  fan-out (engine/verifier/SDK/vectors) is sequenced as a separate task.
- `multiplicity-recommendation.md` — §4 **APPROVED AS GUIDANCE** (calibrated + saturating-cap default
  curve, each experiment freezes its own). Not a spec change: moves no frozen field, no spec golden
  (Reading B). Concrete curve numbers pending the Condition-1 finalized curve.

## Not ratified (open items — NOTHING here is in force)
- `reward-policy.md` Appendix B — **Q-CURVE-1**: nothing constrains `reward_curve` outputs relative
  to `budget_base_units` or `cohort_count`. Open; candidates in the v1.2 proposal (S3/C3).
- `serialization.md` §6.5.2 — the epoch sub-root → singular on-chain field `combine()` mapping is
  spec-RESOLVED but **awaits `solana-program-engineer` confirmation** that evidence-registry/SDK post
  `combine(R)`/`combine(Q)` for `n ≥ 2`. Unconfirmed; not resolved unilaterally.
- `serialization.md` §6.2 — participant leaf/sort still stamped `PROVISIONAL-UNPINNED-6.2`.

**Status:** M1 spec set complete; v1.2 missingness migration LANDING (specs-only). All serialization
open items are ratified; the four M1 design questions (student_t df, weight-formula grammar,
switchback carryover/washout, interference assumption) are resolved in-spec. **Current goldens
(v1.2):** manifest **`ba632e8a…9b2f69fb`** (moved from `74e0bb82…` by the missingness field +
version bump), `reward_curve_hash` `sha256:14b0ec34…856d41` (unchanged), evidence `901b08d5…fa75b`
(unchanged). Implementations still reproducing `74e0bb82…` are intentionally desynced until the
cross-impl fan-out task runs.

## License

Apache-2.0.
