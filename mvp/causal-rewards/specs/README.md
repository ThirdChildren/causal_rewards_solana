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

**Status:** M1 frozen-READY. All serialization open items are ratified; `manifest.golden.md` carries
final (non-provisional) golden hashes; the four M1 design questions (student_t df, weight-formula
grammar, switchback carryover/washout, interference assumption) are resolved in-spec. Remaining step
is the orchestrator's freeze gate. Frozen spec is the M1 acceptance artifact and a hard dependency
for M2/M3.

## License

Apache-2.0.
