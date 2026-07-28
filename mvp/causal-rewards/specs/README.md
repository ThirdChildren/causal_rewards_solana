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

## Not ratified (proposals and open items — NOTHING here is in force)

- `v1.2-migration-proposal.md` — DRAFT. The **single** v1.2 package: S1 missingness (ready),
  S2 concentration/multiplicity remedy (**slot, content TBD**), S3 clarifications; plus the
  independent participant-leaf pin. Carries the exact computed golden cost of every candidate.
- `multiplicity-recommendation.md` — **WITHDRAWN-PENDING-DATA (2026-07-28)**. Its structural premise
  was wrong (it described allocation as a share of budget; allocation is absolute). Restructured to
  receive `causal-inference-engineer`'s four-way + floor-sweep + cap numbers. Do not cite its tables.
- `reward-policy.md` Appendix B — **Q-CURVE-1**: nothing constrains `reward_curve` outputs relative
  to `budget_base_units` or `cohort_count`. Open; candidates in the v1.2 proposal (S3/C3).
- `serialization.md` §6.5.2 — the epoch sub-root → singular on-chain field `combine()` mapping is
  spec-RESOLVED but **awaits `solana-program-engineer` confirmation** that evidence-registry/SDK post
  `combine(R)`/`combine(Q)` for `n ≥ 2`. Unconfirmed; not resolved unilaterally.
- `serialization.md` §6.2 — participant leaf/sort still stamped `PROVISIONAL-UNPINNED-6.2`.

**Status:** M1 frozen-READY. All serialization open items are ratified; `manifest.golden.md` carries
final (non-provisional) golden hashes; the four M1 design questions (student_t df, weight-formula
grammar, switchback carryover/washout, interference assumption) are resolved in-spec. Remaining step
is the orchestrator's freeze gate. Frozen spec is the M1 acceptance artifact and a hard dependency
for M2/M3. **Frozen goldens (unchanged, re-verified 2026-07-28):** manifest
`74e0bb82…0f81b2`, `reward_curve_hash` `sha256:14b0ec34…856d41`, evidence `901b08d5…fa75b`.

## License

Apache-2.0.
