# Manifest Golden Hash (FROZEN)

**Spec version:** 1.0.0
**Status:** FROZEN — computed with the RATIFIED canonical serialization (`serialization.md`).
**Artifact:** `specs/examples/manifest.example.json`

This is the golden hash `verifier-reproducibility-engineer` builds test vectors against. It is the
authoritative expected output for the canonical example manifest under the ratified serialization,
and reproducing it byte-for-byte is a conformance requirement (Invariant 2). Any change to the
serialization or the example regenerates these values in the same commit.

## Serialization + hash function used

Computed with the ratified algorithm in `serialization.md` (§2 numbers, §3 CJSON, §5 SHA-256):

1. Load the manifest JSON. Per §2, it contains **no JSON number tokens**: every numeric value is a
   canonical integer-scaled decimal string. A serializer conforming to §3.1 rejects any bare number,
   so a manifest carrying a number token cannot be hashed at all (Invariant 2, no floats).
2. `CJSON(manifest)`: object keys NFC-normalized and sorted ascending by UTF-16 code-unit; all keys
   ASCII; two-character-free separators `,` and `:`; no insignificant whitespace; UTF-8; strings
   minimally escaped (§4).
3. `manifest_hash = SHA-256(CJSON(manifest))`, lowercase hex.

The whitespace/indentation of the on-disk `.example.json` is irrelevant: the hash is over the
canonical byte string, not the file bytes.

## Values

```
canonical serialization : CJSON (serialization.md §2/§3, RATIFIED)
hash function           : SHA-256
CJSON byte length       : 3852
reward_curve_hash       : sha256:14b0ec34d3653a5857ceef10b9bdfee264a6865172c2b2cfb1d2405fae856d41
manifest_golden_sha256  : 74e0bb825013fcd4a2327b234a5f44c48cd709e7a3025cd30a3b26ace68f81b2
```

- `reward_curve_hash` = `SHA-256(CJSON(reward_policy.reward_curve))`, over the object
  `{"breakpoints":[["0","0"],["100000","20000000000"],["500000","80000000000"],["1000000","120000000000"]],"type":"piecewise_linear_monotonic"}`.
  It is embedded in the manifest (with the `sha256:` prefix) as a redundant commitment and therefore
  also participates in `manifest_golden_sha256`.
- `manifest_golden_sha256` = `SHA-256(CJSON(entire manifest))`, rendered as raw lowercase hex (no
  `sha256:` prefix), matching what `experiment-registry` stores as the frozen manifest hash.

## Reproduce

The reference implementation of the ratified serialization is
`verifier-cli/reference/canonical.py`. To reproduce:

```
cd verifier-cli/reference
python3 -c "import json, canonical; \
m=json.load(open('../../specs/examples/manifest.example.json')); \
print('reward_curve_hash', canonical.sha256_hex(canonical.canonical_json_bytes(m['reward_policy']['reward_curve']))); \
print('manifest_golden ', canonical.sha256_hex(canonical.canonical_json_bytes(m)))"
```

`canonical.canonical_json_bytes` raises on any `int`/`float`, so this only succeeds because the
example is fully number-free (§2). The output must equal the Values block above.

## Regeneration protocol (versioned migration only)

Any change to the byte format (`serialization.md`), the example, or the reward curve is a versioned
migration and MUST, in a single commit:

1. Update `serialization.md` and bump `spec_version` if the byte format changed.
2. Recompute `reward_curve_hash`; write it (with `sha256:` prefix) back into `manifest.example.json`.
3. Recompute `manifest_golden_sha256` over the updated manifest.
4. Update the Values block above.
5. Update `verifier-reproducibility-engineer`'s vectors and `protocol-architect` memory
   (`spec-versions`).
