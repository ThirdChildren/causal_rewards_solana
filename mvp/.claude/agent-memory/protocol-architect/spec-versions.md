---
name: spec-versions
description: Current spec/schema versions, golden hashes, and M1 freeze status for the Causal Rewards Protocol specs
metadata:
  type: project
---

M1 spec set drafted under `causal-rewards/specs/`. All at `spec_version`/`manifest_version` **1.0.0**.

**Why:** M1 acceptance = frozen public spec; it is a hard dependency for M2 (programs/SDK) and M3.

**How to apply:** read the actual spec files before editing; versions bump only via versioned
migration (never silent edit), and any byte-format change regenerates every golden hash in the
same commit.

Files: `protocol.md`, `manifest.schema.json`, `evidence.schema.json`, `state-machine.md`,
`threat-model.md`, `reward-policy.md`, `serialization.md`, `examples/manifest.example.json`,
`examples/evidence.example.json`, `manifest.golden.md`.

Status: **M1 frozen-READY, NOT yet frozen.** Freeze is the orchestrator's gate. `serialization.md`
is RATIFIED (no PROVISIONAL banner); all four M1 open questions resolved in-spec.

FINAL golden hashes (ratified CJSON per `serialization.md` §2/§3 = numbers-as-strings + SHA-256;
reproduced by `verifier-cli/reference/canonical.py`; CJSON byte length 3852):
- reward_curve_hash: `sha256:14b0ec34d3653a5857ceef10b9bdfee264a6865172c2b2cfb1d2405fae856d41`
- manifest_golden_sha256: `74e0bb825013fcd4a2327b234a5f44c48cd709e7a3025cd30a3b26ace68f81b2`

(Superseded PROVISIONAL hashes were `sha256:838f...dfca` / `6d39...67ed`, computed with bare integer
tokens; regenerated because the ratified serializer forbids number tokens entirely.)

Both schema examples validate (jsonschema Draft202012). Manifest AND evidence examples are now fully
number-free and round-trip through the verifier reference serializer without raising (evidence CJSON =
1040 bytes, sha256 901b08d5...; migrated 2026-07-20, no golden root committed for it yet). Evidence
Merkle leaf sort keys pinned in serialization.md §6.5. See [[open-questions]] for remaining (M2/M3)
items and [[resolved-decisions]] for rationale.
