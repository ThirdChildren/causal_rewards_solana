---
name: bundle-layout-and-parquet
description: Audit-bundle layout v1.0.0, the two-level determinism model, and the pinned Parquet writer settings that make bundle bytes stable — read before changing any serialization
metadata:
  type: project
---

Implemented in `causal-rewards/evidence-service/` (M3). Bundle layout version **1.0.0**.

**Two-level determinism (the core design decision).**
- *Level 1, logical, unconditional*: every table carries
  `canonical_content_hash = SHA-256(CJSON(ordered columns + ordered rows))` via the single
  ratified encoder. Environment-independent. `bundle_logical_hash` aggregates these (falling
  back to `sha256` for JSON files, which are already canonical bytes) — **this is the
  cross-machine reproducibility claim of record**.
- *Level 2, physical, container-scoped*: `bundle_content_hash` includes parquet FILE bytes.
  Stable across fresh processes within the pinned container; pyarrow embeds its version in
  `created_by`, so a different pyarrow legitimately moves this hash only.

**Why:** parquet is not byte-stable across library versions, but the CLAUDE.md audit-bundle
file set requires parquet. Committing to a logical hash keeps invariant 2 honest without
pretending parquet bytes are portable.

**Pinned parquet settings** (`parquet_writer.PARQUET_WRITER_SETTINGS`; changing any value
requires a `bundle_layout_version` bump): `version="2.6"`, `compression="zstd"`,
`compression_level=3`, `use_dictionary=False`, `write_statistics=False`,
`data_page_size=1048576`, `row_group_size=1048576`, `write_batch_size=1024`,
`data_page_version="2.0"`, `store_schema=True`. Plus: **all columns UTF-8 strings** (no ints,
floats, timestamps, booleans, index column — numbers travel as integer-scaled decimal strings
per §2) and **row order = the canonical Merkle leaf order supplied by the caller** (the writer
never sorts, so a caller ordering bug stays visible).

**provenance.json is EXCLUDED from both bundle hashes** because execution timestamp and
platform legitimately differ per run. It carries both hashes itself. Nothing in the package
reads the clock: `execution_timestamp` is a caller input / `SOURCE_DATE_EPOCH` / sentinel `"0"`.

**manifest.json in the bundle is the frozen EXPERIMENT manifest verbatim** (its SHA-256 is the
on-chain frozen hash). The bundle's own file index therefore lives in `roots.json`.

Frozen fixture golden values (tests/test_frozen_bundle.py): manifest `4aafcf1e…`, epoch-0
`25b60b5d…`, epoch-1 `06b8ec75…`, assignment `a926f235…`, participant `b4683d9f…`
(PROVISIONAL), bundle_logical `c39143c8…`, bundle_content `064adccb…` (pyarrow 18.1.0).

Related: [[merkle-evidence-scheme]], [[ingestion-dedup-semantics]], [[open-spec-items-m3]].
