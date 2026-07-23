---
name: project-canonical-serializer
description: Simulator canonical.py deliberately diverges from the ratified reference on numbers; parity is only defined on number-free payloads. Do not stringify numbers.
metadata:
  type: project
---

`simulator/src/depin_sim/canonical.py` mirrors the ratified reference
`verifier-cli/reference/canonical.py` (serialization.md §2/§3/§4) byte-for-byte on the SHARED
value domain: strings, keys, bools, null, arrays, objects — NFC-normalized, keys sorted by
UTF-16 code unit, minimal escaping, raw UTF-8. Discrepancy #2 (was: `ensure_ascii=True`, no NFC)
closed 2026-07 by replacing the `json.dumps` path with a hand serializer matching the reference.

**Deliberate single-point divergence — do NOT "harmonize" it away.** The reference is a hashed
*protocol-artifact* serializer and forbids EVERY JSON number token (§2: numbers carried as decimal
strings; it raises `TypeError` on int/float). The simulator's content hash is an INTERNAL
determinism check, not an on-chain artifact, so it carries integer-scaled reals + counts as bare
**integer** number tokens (float-free via `scale_decimal`, FLOAT_SCALE=1e6). Consequently the two
encoders are byte-identical only on **number-free** payloads (which is exactly what the parity
fixtures and all `ser-*` golden vectors use).

**Why this matters / How to apply:** If a future task asks to make the simulator "fully §2
compliant" by encoding numbers as strings, that WILL change the committed ASCII baseline content
hash `31135b85f4c18e4022b58f7d0dbfa1ef018990b29990b331a0048104e165dc67` and break determinism
acceptance. Do not do it without an explicit hash-regeneration decision coordinated with
`protocol-architect` + `verifier-reproducibility-engineer`. The anti-drift oracle is
`simulator/tests/test_canonical.py`, which imports the reference and asserts byte parity on
non-ASCII fixtures + the `test-vectors/serialization/ser-*.json` golden bytes.
