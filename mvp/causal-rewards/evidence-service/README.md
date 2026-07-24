# evidence-service/ — off-chain evidence pipeline + audit-bundle assembler (M3)

Python 3.11+, typed, pinned deps. Owns the off-chain data plane:

```
signed batches ──► ingest ──► content-addressed store ──► Merkle roots ──► audit bundle
                 (verify,        (hash-named)              (§6.1–§6.6)      (mirrorable)
                  dedup)
```

Only hashes, roots, summaries and claim state ever go to Solana. Raw telemetry and exact
coordinates never enter this service at all — the frozen `evidence.schema.json` is a closed
object with no property that could hold them, and an unknown key is a hard rejection
(`DATA_MINIMIZATION_VIOLATION`), not a warning.

## Quick start

```bash
make setup                 # venv + pinned deps
make vectors               # HARD GATE: reproduce the ratified evidence golden roots
make test                  # full suite
make determinism           # fresh-process byte-identity gate
```

## There is exactly one encoder

Every canonical byte, leaf preimage, sort key and node hash comes from
`verifier-cli/reference/` (the ratified conformance oracle), imported by path in
`_ref.py`. This package defines **no second implementation** of any byte rule. Set
`CRP_REFERENCE_DIR` when running outside the repo tree. `provenance.json` records the SHA-256
of each reference module, so every bundle names the exact oracle bytes it was built against.

`specs/` wins over any implementation. `tests/test_schema_parity.py` reads
`specs/evidence.schema.json` and asserts the hand-written validator enforces exactly the
frozen property names, required lists, `const`s and regexes — a spec edit breaks the build
before behavior can silently diverge.

## Modules

| Module | Responsibility |
| --- | --- |
| `_ref.py` | path-import of the ratified reference (single encoder) |
| `errors.py` | typed hard errors + stable `RejectionCode` wire contract |
| `validate.py` | structural validation against the frozen evidence schema |
| `ed25519.py` | RFC-8032 verification (pure-Python reference + optional accelerated backend) |
| `ingest.py` | the trust boundary: recompute hash, verify signature, dedup |
| `anomalies.py` | findings (admitted-but-flagged), incl. Sybil-replication correlation checks |
| `roots.py` | participant / assignment / evidence roots with typed rejections |
| `cas.py` | content-addressed, hash-named, mirrorable object store |
| `parquet_writer.py` | byte-stable Parquet + parquet-independent logical hashes |
| `schedule.py` | expected epoch schedule + missingness (selective-reporting defense) |
| `contracts.py` | the `analysis.json` / `rewards.parquet` contract with `causal-inference-engineer` |
| `bundle.py` | audit-bundle assembly and verification |
| `provenance.py` | `provenance.json` without ever reading the clock |
| `cli.py` | `crp-evidence ingest \| roots \| vectors \| assemble \| verify` |

## Acceptance gate — ratified evidence golden roots

`make vectors` (and `tests/test_golden_vectors.py`) replay `test-vectors/evidence/`:

| Vector | Expected | Reproduced |
| --- | --- | --- |
| evidence-01 epoch (3 batches) | `a13e1cdc…deeb2` | yes |
| evidence-02 signer set (4 signers) | `e45697c8…d52e` | yes |
| evidence-03 observation set (4 commitments) | `1010891b…af56` | yes |
| evidence-04 empty tree (all three trees) | `0000…0000` | yes |
| evidence-05 signer not 32 bytes | reject `SIGNER_PUBKEY_NOT_32_BYTES` | yes |
| adv-03 replayed batch | reject `DUPLICATE_EVIDENCE_LEAF` | yes |

Leaf **order** and per-leaf hashes are asserted too, not just the roots. A golden is never
adjusted to match the implementation; a mismatch is reported upstream and stops the work.

The golden batch headers carry placeholder signature bytes (`aaaa…`) because they pin *tree*
bytes. The epoch tree is a pure function of `CJSON(batch)` and is independent of signature
validity, so root reproduction and signature policy are separable — the trust boundary is
tested independently with real RFC-8032 signatures.

## Ingestion: never trust a producer hash

```
header_hash = SHA-256( CJSON(batch \ {"batch_signature"}) )     # recomputed by us
```

Checked against the producer's `header_hash_hex` **before** the signature is verified —
verifying first would let a producer sign a hash of something other than what it submitted.
The ed25519 signature is then verified over those 32 recomputed bytes, with the base58
`signer_pubkey` decoded under the §6.5 **exactly-32-bytes** pin (the schema's `{32,44}`
regex constrains characters, not decoded length).

### Deduplication semantics (read before changing anything)

**The Merkle tree does not deduplicate.** Two *different* producers reporting the same
`(experiment_id, epoch_index, cohort_id)` are two **distinct leaves and both are admitted** —
their signatures differ, so their `CJSON(batch)` differs, so their `leaf_hash` differs, so
strict monotonicity is satisfied. Independent corroboration of a cohort-epoch is evidence,
not duplication. The tree rejects only a byte-identical leaf (`DUPLICATE_EVIDENCE_LEAF`).

Real dedup happens at **ingestion**, in three independent layers:

1. **Content hash** — `SHA-256(CJSON(batch))` over the whole *signed* batch. Seen twice ⇒
   `REPLAYED_BATCH`. Deliberately not `header_hash` (body only): two honest producers may sign
   an identical body, and collapsing those would destroy corroboration.
2. **Event nonce** — `(experiment_id, epoch_index, cohort_id, producer_pubkey)`. One producer
   gets one batch per cohort-epoch; a second, different one ⇒ `DUPLICATE_EVENT_NONCE`.
3. **Correlation checks** — cross-producer / cross-cell equality of committed roots. These
   produce **findings**, never rejections (see below).

Why no dedicated `nonce` field in the batch: `evidence.schema.json` is frozen and
`additionalProperties:false`; adding a field would be a hash-breaking schema change for
something the natural key already provides, and a producer-chosen nonce would be an
insertion-order proxy the tree is explicitly designed to avoid.

### Findings vs rejections

A **rejection** means unusable input: it never enters a tree and is listed in
`evidence/findings.json` under `rejected_submissions`. A **finding** means admissible but
suspicious (Sybil replication, reused observation roots, count divergence, missing scheduled
cells). Findings are published *next to* the data, because silently dropping suspicious data
would itself be a selective-reporting attack surface.

## Selective-reporting defense

`schedule.py` derives the expected epoch schedule from **frozen** manifest fields:

```
epoch_count   = estimand.time_block.block_count
block_seconds = estimand.time_block.block_seconds
epoch e       covers [windows.active_start + e*block_seconds, + block_seconds)
expected cells = epoch_count x <frozen cohort set>
```

and reports `missing_cells`, `empty_epochs`, `unscheduled_epochs`, and integer
`coverage_micro` in `evidence/missingness.json`. An empty epoch is a **legal** state
(root = 32 zero bytes, §6.4) and must still be anchored so absence is *committed*, not merely
unrecorded. The estimator consequence of a missing cell belongs to the frozen analysis plan,
not to this service.

## Determinism — two levels

**Level 1 (logical, unconditional).** Every table carries
`canonical_content_hash = SHA-256(CJSON(ordered columns + ordered rows))`, produced by the one
ratified encoder. Environment-independent; identical on any machine, Python or pyarrow. This
is the comparison of record.

**Level 2 (physical, within the pinned container).** Parquet bytes are byte-identical across
fresh processes with the pinned writer settings in `parquet_writer.PARQUET_WRITER_SETTINGS`
(`version=2.6`, `compression=zstd` level 3, `use_dictionary=False`, `write_statistics=False`,
fixed page/row-group/batch sizes, `data_page_version=2.0`). pyarrow embeds its own version in
the file's `created_by`, so a different pyarrow build changes level-2 bytes while leaving
level 1 untouched — which is exactly why level 1 exists.

Also load-bearing: **all columns are UTF-8 strings** (no ints, floats, timestamps, booleans,
categoricals or index column; numbers travel as canonical integer-scaled decimal strings per
§2), and **row order is the canonical Merkle leaf order**, supplied by the caller — the writer
never silently sorts, so a caller ordering bug is visible rather than masked.

`tests/test_determinism.py` builds the same bundle in two separate interpreters via
`subprocess` and asserts every file is byte-identical. An in-process loop would miss
hash-randomization and process-state leaks. `tests/test_frozen_bundle.py` pins a frozen input
fixture to frozen roots and bundle hashes — the candidate for promotion into `test-vectors/`
jointly with `verifier-reproducibility-engineer`:

```
manifest_hash          4aafcf1e0beb123af7c21d197bc1b959c87a10b653795539caabdfb1085b74eb
evidence epoch 0 root  25b60b5d19fd83fbda4f1ca836265e18a4cb3e1caca942ed2ed1e59dfd16d3e5
evidence epoch 1 root  06b8ec750c0c4f92fe812fcd3952a25eef6d237c0fdc6e80399aa3168313339d
assignment_root        a926f235c2d5ac82981dcf5fbca283b89a1c98d08506e43a40eca9ce0347e8f7
participant_root       b4683d9f6df64f1866445716b0513899d06e7005d36142ba429d90d32c89224a  [PROVISIONAL]
bundle_logical_hash    c39143c866da4733b454a6a4bcce9eec98fbb4c22c9428f692ca2c474bd16f40  [portable]
bundle_content_hash    064adccb0ea96d48c41ac9433fe6954d3a1f8404ef34c395bd917668bf71a529  [pyarrow 18.1.0]
```

## Audit bundle (`bundle_layout_version` 1.0.0)

```
manifest.json                    frozen experiment manifest, VERBATIM canonical bytes
participants.parquet             participant set, participant-leaf order      [PROVISIONAL root]
assignment.parquet               cohort -> arm, cohort_id UTF-16 ascending
evidence/
  epoch-<NNNNNN>.parquet         one table per epoch, rows in leaf_hash ascending order
  findings.json                  correlation findings + rejected submissions
  missingness.json               expected schedule vs anchored coverage
analysis.json                    OWNED BY causal-inference-engineer (contracts.py)
rewards.parquet                  OWNED BY causal-inference-engineer (contracts.py)
roots.json                       every Merkle root + the file index
provenance.json                  source commit, container digest, package versions, timestamp
```

`manifest.json` is the frozen **experiment** manifest byte-for-byte, because its SHA-256 is
what `freeze_experiment` anchored on-chain. The bundle's own file index therefore lives in
`roots.json`, not in a second "manifest".

### Hashes

| Name | Definition |
| --- | --- |
| `manifest_hash` | `SHA-256(CJSON(manifest))` — matches the on-chain frozen hash |
| per-file `sha256` | over the exact stored bytes |
| per-table `canonical_content_hash` | `SHA-256(CJSON(logical rows))`, environment-independent |
| `bundle_content_hash` | `SHA-256(CJSON({relpath: {sha256, canonical_content_hash}}))` over every bundle file **except** `provenance.json` — physical identity, container-scoped |
| `bundle_logical_hash` | `SHA-256(CJSON({relpath: canonical_content_hash or sha256}))` over the same set — **environment-independent; this is the cross-machine reproducibility claim** |

`provenance.json` is excluded because it legitimately varies between two runs of identical
inputs (execution timestamp, platform). It carries `bundle_content_hash` itself, so the chain
of custody is complete without making the content hash time-dependent. **Nothing in this
package reads the clock**: `execution_timestamp` is a caller input (`--execution-timestamp`,
or `SOURCE_DATE_EPOCH`, else the visible sentinel `"0"`).

### Data availability

A bundle is a directory of immutable files plus a `roots.json` index naming each by hash.
Copy it anywhere — S3, IPFS, Arweave, a tarball — and `crp-evidence verify <dir>` on the copy
proves it is the same bundle. Nothing resolves through a hosted endpoint, so no mirror is
privileged. `cas.ContentAddressedStore` gives the same property to individual batch objects:
the stored bytes of a batch **are** its evidence-leaf preimage, so a verifier can rebuild an
epoch tree straight from the store without re-serializing anything.

## Contract with `causal-inference-engineer`

`analysis.json` and `rewards.parquet` are produced by the causal engine, not here. The full
contract (filenames, location, required keys, column names, ordering, validation) is in
`src/crp_evidence/contracts.py`. Summary:

* `analysis.json` — CJSON bytes via the same encoder, **no JSON number tokens** (integer-scaled
  decimal strings). Must declare `evidence_epoch_roots` in ascending epoch order; the
  assembler cross-checks them against the roots it built and rejects a mismatch. Its
  `sha256` **is** the `result_artifact_hash` that `submit_evaluation` anchors.
* `rewards.parquet` — written with `parquet_writer.write_table`; columns
  `(leaf_index, recipient_hex, amount_base_units, leaf_hash_hex)`, all strings (`recipient_hex`
  is 64 lowercase hex, hex-decoding to exactly 32 bytes), rows in
  §6.6 leaf order (`leaf_index` ascending, contiguous from 0), one leaf per **recipient**
  (aggregated over cohorts, zero-sum recipients omitted). The assembler recomputes the reward
  root with `verifier-cli/reference/reward.py` and rejects a mismatch.

Supplying one without the other is a hard error. A bundle sealed with neither is legal and
marked `completeness: "evidence-only"` — enough to anchor evidence epochs, not enough for
`finalize_distribution`.

## Open items (NOT decided here)

1. **Multi-batch epoch → singular on-chain fields.** `EvidenceEpoch.{signer_set_root,
   observations_root}` are singular while a multi-batch epoch has one sub-root per batch. This
   mapping is owned by `protocol-architect` + `solana-program-engineer`. The bundle publishes
   the full ordered per-batch lists (`roots.json → roots.evidence_epochs[].per_batch_*`) so
   whichever mapping is ratified is computable from the bundle without re-ingesting, and
   discloses the open question in `roots.json → notes.on_chain_epoch_field_mapping`.
2. **Participant leaf form + sort key are UNPINNED** (`serialization.md` §6.2 says they are
   fixed "when the participant golden root lands"). This service implements the spec's
   recommendation of record — leaf `CJSON({"cohort_id", "participant_id"})`, order
   `participant_id` ascending by UTF-16 code unit of the NFC-normalized id — and labels every
   value `participant_root_status: "PROVISIONAL-UNPINNED-6.2"`. A bundle carrying it is **not**
   claimed to be on-chain-verifiable for the participant root until §6.2 is ratified.
3. **No frozen missingness policy in the manifest schema.** `schedule.py` derives the schedule
   from frozen fields, which is sound but implicit. Proposed to `protocol-architect`: an
   explicit `manifest.evidence_schedule { epoch_count, epoch_seconds,
   expected_cohort_coverage, missingness_action }`.

## Licensing

Apache-2.0 (protocol code).
