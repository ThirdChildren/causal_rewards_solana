# reference/ — canonical serialization + assignment reference implementation

Small, auditable, dependency-free (Python 3.11+ stdlib only), zero network,
zero wall-clock, zero unseeded RNG. This is the working definition of the
PROPOSED canonical rules in [`../docs/canonical-serialization.md`](../docs/canonical-serialization.md)
until `protocol-architect` ratifies them into `specs/serialization.md`.

## Modules

- `canonical.py` — `canonical_json_bytes(obj)` (RFC 8785 subset; rejects numeric
  tokens), `sha256` / `sha256_hex`.
- `merkle.py` — domain-separated binary Merkle tree (`leaf_hash`, `node_hash`,
  `merkle_root`) with per-tree domain tags and odd-node promotion.
- `assignment.py` — `seed_commitment`, `cohort_prf`, `derive_assignment`,
  assignment leaf encoding.
- `generate_vectors.py` — regenerates `../../test-vectors/` deterministically.
- `verify_vectors.py` — the acceptance self-check: re-derives every vector from
  its declared inputs and asserts it matches the published expected values.

## Commands

```
python3 generate_vectors.py   # (re)write the golden vectors
python3 verify_vectors.py      # re-derive & check them; exit 0 = OK
```

Determinism check: run `generate_vectors.py` twice; the aggregate `sha256sum` of
`../../test-vectors/**/*.json` is byte-identical.

## Cross-language note

Python is the reference here for auditability. The M2/M3 verifier ships parity
implementations in TypeScript and on-chain Rust; all three must reproduce these
exact vectors. Any divergence is a release blocker filed against the owning agent.
