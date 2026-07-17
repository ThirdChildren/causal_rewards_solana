# verifier-cli/ — Independent reproducibility oracle

Recomputes **every root** (assignment / evidence / analysis / reward) from an audit bundle
with **zero network access** and **no trust** in coordinator or evaluator.

## Audit bundle inputs

`manifest.json`, `participants.parquet`, `assignment.parquet`, `evidence/*.parquet`,
`analysis.json`, `rewards.parquet`, `roots.json`, `provenance.json` (source commit, container
digest, package versions, execution timestamp).

## Owns

Canonical serialization/rounding rules and the deterministic test-vector suite. These rules
are defined **up front** so every downstream implementation builds against them from day one.

**Status:** stub. Canonical serialization rules + first assignment vectors are early M1 work;
full CLI lands in M3.

## License

Apache-2.0.
