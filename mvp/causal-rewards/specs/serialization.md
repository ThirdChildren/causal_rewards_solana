# Canonical Serialization & Hashing (NORMATIVE — RATIFIED)

**Spec version:** 1.1.0
**Wire/hash contract version:** 1.1.0 — advanced from 1.0.0 by an **additive, hash-compatible**
minor revision (see §9 Revision history). Every pre-existing golden is **byte-identical** to 1.0:
manifest `74e0bb82…`, `reward_curve_hash` `14b0ec34…`, evidence example `901b08d5…`, and all 11
existing assignment roots (bernoulli / fixed_count). The manifest `spec_version` field stays
`"1.0.0"` and a v1.0.0 manifest hashes identically under 1.1. v1.1 only **pins previously-open
residuals** (reward `leaf_index` assignment, §6.6; switchback + matched_cluster seed→assignment
derivations, §7.4) and adds their new-but-additive byte layouts — it changes no byte of any existing
hashed artifact.
**Status:** RATIFIED. This is the single authoritative byte-level definition. No PROVISIONAL banner.
**Owner:** `protocol-architect` (ratifier). Ratified from the `verifier-reproducibility-engineer`
proposal (`verifier-cli/docs/canonical-serialization.md`) and its reference implementation
(`verifier-cli/reference/`). The reference implementation and the golden vectors under
`test-vectors/` are conformance oracles for this document; if they and this text ever disagree,
that is a bug to be escalated to `protocol-architect`, not silently reconciled in code.

This file is the single, authoritative definition of how any hashed protocol artifact is turned
into bytes before hashing. Every hash, Merkle leaf, Merkle root, and commitment in this protocol —
the manifest hash, the reward-curve hash, evidence roots, reward roots, the seed commitment, the
assignment root — is computed over bytes produced by **these** rules and no others. Independent
implementations that follow this file MUST produce identical bytes and therefore identical hashes
(Invariant 2, determinism/reproducibility).

## 1. Normative requirements (FIXED)

These correctness requirements are frozen. Sections 2–8 are the concrete algorithm that satisfies
them; the algorithm is what implementations reproduce.

1. **Deterministic canonical bytes.** For any given logical artifact there is exactly one valid
   byte string. Serialization is a total function; two conforming implementations produce
   byte-identical output.
2. **No floating-point anywhere in a hashed artifact.** IEEE-754 binary floats are FORBIDDEN in any
   field that enters a hash, and — stronger — **no JSON number token of any kind may appear in a
   hashed artifact** (§2). Every numeric quantity is carried as a decimal string. Nondeterministic
   float formatting, locale-dependent formatting, and rounding drift are thereby structurally
   impossible, and the one language-dependent corner of RFC 8785 (ES6 number canonicalization) is
   never invoked.
3. **Integer-scaled decimals.** Every real-valued quantity that must be hashed is represented as a
   signed or unsigned integer, as a decimal string, together with a fixed, documented decimal scale
   (§2.2 scale table). Rounding, when a computation must reduce precision to reach the stored scale,
   uses **round-half-to-even** (banker's rounding), applied exactly once, at the documented
   boundary (§2.4). This is the sole rounding rule in the protocol.
4. **Stable field ordering.** Object member order is deterministic and independent of authoring
   order: ascending by UTF-16 code-unit of the NFC-normalized key (§3.3).
5. **Fixed string/number encoding.** UTF-8, NFC-normalized, minimal escaping (§3.4, §5); numbers as
   canonical decimal strings (§2.1).
6. **Explicit hash + Merkle construction.** SHA-256 is the sole protocol hash. Merkle leaf/interior
   domain separation, per-tree domain tags, data-derived leaf ordering, the odd-node rule, and the
   empty-tree root are specified once here (§6) and reused by all trees.

## 2. Numbers — no JSON number tokens in any hashed artifact

**A hashed artifact contains NO JSON number tokens. Every numeric quantity is a JSON string.** The
canonical serializer MUST reject a bare numeric value (the reference implementation raises a
`TypeError` on any `int`/`float`, making the rule mechanical rather than a convention a producer
might forget).

### 2.1 Value-level canonical form of a numeric string

A numeric string is a decimal integer at the field's declared scale (§2.2):

- **Unsigned integers** MUST match `^(0|[1-9][0-9]*)$` — no leading zeros, no sign, zero is `"0"`.
- **Signed integers** MUST match `^(0|-?[1-9][0-9]*)$` — optional leading `-` for non-zero
  magnitudes only; `"-0"` is FORBIDDEN; no leading `+`; no leading zeros.
- No decimal point, no exponent, no thousands separators, no surrounding whitespace.

The serializer is **byte-faithful** to string contents: it does NOT strip leading zeros or re-sign
numeric strings. Producers therefore own value-level canonicalization and MUST emit already-canonical
numeric strings; schemas enforce the two regexes above per field so a validator rejects a
non-canonical value before it is ever hashed.

### 2.2 Per-field fixed-point scale table

The scale binds a stored integer to the real value it represents: `real = stored / scale`. Every
hashed numeric field belongs to exactly one class below. New fields MUST declare their class in the
schema and be added here in the same versioned change.

| Class | Scale (`stored / scale`) | Field-name convention | Fields (non-exhaustive) |
| --- | --- | --- | --- |
| **micro** | 1e6 | `*_micro` | `confidence_level_micro`, `critical_value_micro`, `treated_fraction_micro`, `quality_score_micro`, `uptime_micro`, `quality_score_micro_sum` (evidence) |
| **ppm** (assignment params) | 1e6 | `*_ppm` | `treat_fraction_ppm` |
| **base units** (money) | 1 (mint-native integer) | `*_base_units`, reward-curve outputs, reward leaves | `budget_base_units`, `challenge_bond_base_units`, reward-curve output axis, per-participant reward leaves |
| **count / seconds / index** | 1 | plain integer semantics | `created_at`, `cohort_count`, `block_seconds`, `block_count`, all `windows.*`, `minimum_sample.*`, `threshold`, `treatment_count`, `df`; evidence: `epoch_index`, `time_range.start`, `time_range.end`, `signer_count`, `leaf_count`, `accepted_count`, `rejected_count`, `distinct_signers`, `time_block_index` |
| **scale exponent** | 1 (the value *is* an exponent) | `effect_scale`, `weight_scale` | `effect_scale`, `weight_scale` (allowed range −12…0; a value `e` means the paired quantity is expressed at resolution `1e(e)`) |

Default statistical resolution is **micro (1e6)**; the simulator's float-free content hasher uses
the same `FLOAT_SCALE = 1_000_000`.

Money is already integral (native mint base units); it is stored at scale 1 and never rounded.

### 2.3 Numeric-string validation regexes (normative, per class)

- Unsigned classes (micro fractions in [0,1], ppm, counts, seconds, base units, `df`):
  `^(0|[1-9][0-9]*)$`.
- Signed classes (`effect_scale`, `weight_scale`, any effect/estimate stored off-manifest):
  `^(0|-?[1-9][0-9]*)$`.

Semantic bounds that cannot be expressed as a regex (e.g. `treated_fraction_micro ≤ 1000000`,
`-12 ≤ effect_scale ≤ 0`) are stated in each field's schema `description` and enforced by the
producing/validating code (causal engine, verifier). The schema still guarantees the value is a
canonical integer string and therefore float-free.

### 2.4 Rounding boundary

When a real computation (e.g. an effect estimate, a standard-error margin, a curve interpolation)
must be reduced to a stored integer scale, apply **round-half-to-even exactly once**, at the moment
the real value is converted to its scaled integer, and carry the integer thereafter. Downstream
integer arithmetic (floor-division budget splits, integer modulus in assignment) introduces no
further rounding. See `reward-policy.md` for where each rounding occurs in the reward pipeline.

## 3. Canonical JSON (`CJSON`)

The canonical form is a **strict subset of RFC 8785 (JSON Canonicalization Scheme, JCS)**, narrowed
to remove JCS's one language-dependent corner (number canonicalization — replaced by §2).

### 3.1 Accepted value types

`object`, `array`, `string`, the literals `true` / `false` / `null`. **Bare numbers are rejected**
(§2). The reference serializer accepts only `dict`, `list`/`tuple`, `str`, `bool`, `None`.

### 3.2 Encoding and whitespace

UTF-8, no BOM. No insignificant whitespace: the only structural bytes are `{` `}` `[` `]` and the
two-character-free separators `,` (between members/elements) and `:` (between key and value). No
spaces, newlines, or indentation anywhere.

### 3.3 Object keys

- Keys are strings; NFC-normalized (§3.5) before use.
- **Duplicate keys are a hard error** after NFC normalization (never last-wins).
- Members are ordered **ascending by UTF-16 code-unit sequence** of the NFC-normalized key, exactly
  as RFC 8785 specifies. Implementation note: sorting by the `UTF-16-BE` byte encoding of each key
  yields this order.
- **All object keys in hashed artifacts MUST be ASCII.** For ASCII keys, UTF-16 code-unit order,
  Unicode code-point order, and UTF-8 byte order coincide, so the UTF-16 choice can never diverge in
  practice. This is a schema constraint on every hashed artifact.

### 3.4 Arrays

Array element order is significant and preserved exactly as the producer supplies it (it is never
reordered by the serializer). Where a protocol artifact needs a canonical element order (e.g. Merkle
leaves, reward-curve breakpoints), that order is fixed by the artifact's own rule, and the producer
MUST supply elements already in that order.

### 3.5 Unicode normalization

All string **values and object keys** are normalized to **Unicode NFC** before serialization. NFC is
chosen (over NFD/NFKC/NFKD) because it is the most widely implemented default, is canonical-composed,
and is non-destructive — the compatibility (K) forms would fold characters and alter meaning. Without
a fixed normal form, the same visual/semantic string could hash to different bytes. Vector
`ser-02-unicode-nfc` demonstrates decomposed input (`cafe` + U+0301) producing precomposed bytes
(`c3 a9`).

## 4. String escaping (minimal, per RFC 8785)

- `U+0022` `"` → `\"`; `U+005C` `\` → `\\`.
- `U+0008` → `\b`, `U+0009` → `\t`, `U+000A` → `\n`, `U+000C` → `\f`, `U+000D` → `\r`.
- Any other control character in `U+0000`–`U+001F` → `\u00XX` with **lowercase** hex.
- Every other character (including `/`, and all non-ASCII) is emitted as its raw UTF-8 bytes —
  it is **not** `\u`-escaped.

Vector `ser-04-control-and-escapes` exercises this.

## 5. Hash function

**SHA-256** everywhere. 32-byte output. Rendered as 64 lowercase hex characters for display and in
audit-bundle text; raw 32 bytes are used inside Merkle and commitment computations. SHA-256 is the
protocol's sole hash — chosen for a cheap Solana runtime syscall, ubiquity in TS/Python, and direct
on-chain verifiability. No other hash function (Keccak-256, Blake3, …) is permitted in any hashed
artifact, commitment, or tree.

Definitions used below: `H(x) = SHA-256(x)`. Domain-separated hashes are `H(domain_tag_bytes ||
payload_bytes)` where `domain_tag_bytes` is an ASCII byte string fixed at the artifact's definition
site.

## 6. Merkle trees

A binary Merkle tree over an **ordered** list of canonical leaf byte strings, identical for every
tree type (assignment, participant, evidence, reward).

### 6.1 Node formulas (domain-separated by construction)

```
LEAF_PREFIX = 0x00
NODE_PREFIX = 0x01
leaf_hash(i) = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes(i) )
node_hash    = SHA-256( 0x01 || left_hash || right_hash )
```

The `0x00` / `0x01` prefixes make it impossible for a leaf preimage to be reinterpreted as an
interior node (second-preimage separation). `DOMAIN_TAG` is a distinct ASCII byte string per tree
type, so a leaf from one tree can never be replayed into another:

| Tree | `DOMAIN_TAG` (ASCII bytes) |
| --- | --- |
| participant | `CRP:participant:v1` |
| assignment | `CRP:assignment:v1` |
| evidence (epoch tree over batch headers) | `CRP:evidence:v1` |
| reward | `CRP:reward:v1` |

Two internal sub-commitment trees live *inside* an evidence batch header (their roots are the
`signer_set_commitment.merkle_root_hex` and `observations_commitment.merkle_root_hex` fields). They
use their own short leaf-domain tags, fixed by the `leaf_scheme` `const`s in `evidence.schema.json`
and pinned in §6.5; each still follows the §6.1 node formulas (`0x00`/`0x01` prefixes, promotion,
empty-tree sentinel):

| Sub-commitment | Leaf domain (ASCII, inside the `0x00` leaf preimage) |
| --- | --- |
| signer set | `signer` |
| observation set | `obs` |

### 6.2 Leaf ordering (data-derived, not insertion order)

Leaf order is a canonical sort key **derived from the leaf data**, so two producers holding the same
set always build the identical tree. Per tree type:

- **assignment:** sort by `cohort_id` ascending (UTF-16 code-unit of the NFC-normalized id).
- **evidence:** PINNED — see §6.5 (evidence epoch tree and its two sub-commitments).
- **participant:** sort key is pinned when the participant golden root lands (recommendation of
  record: participant id ascending, UTF-16 code-unit of the NFC-normalized id). MUST be fixed here
  before the first participant golden root is committed (M2).
- **reward:** PINNED — see §6.6 (reward leaf preimage + `leaf_index` ordering). Leaves are placed in
  `leaf_index` order: ascending, contiguous from 0 (tree position `p` ⇒ `leaf_index == p`). Duplicate
  or gapped `leaf_index` is a hard error. `leaf_index` is assigned by ranking the **aggregate-one-
  leaf-per-recipient** set ascending by `recipient` (unique key), then `amount_base_units` — fully
  pinned in v1.1 (RESIDUAL A closed, §6.6); no tie-break residual remains.

### 6.3 Odd-node handling

If a level has an odd number of nodes, the unpaired trailing node is **promoted unchanged** to the
next level — it is **not** duplicated. Duplicating the last node (Bitcoin-style) enables
CVE-2012-2459-class root collisions (distinct leaf sets producing the same root); promotion avoids
that class. The on-chain verifier MUST implement promotion identically.

### 6.4 Empty tree

The root of an empty tree is **32 zero bytes** — an unmistakable "nothing committed" sentinel (never
`SHA-256(DOMAIN_TAG)`).

### 6.5 Evidence trees (leaf form + ordering, PINNED)

Evidence involves three §6.1-shaped Merkle trees. All three use the §6.1 node formulas (prefixes,
promotion, empty-tree sentinel). Each is defined by (a) its leaf preimage and (b) a data-derived
**total order** with an explicit tie-break, so two producers holding the same set build byte-identical
trees and roots (Invariant 2). No new encoder is introduced — leaves are either canonical JSON bytes
(§3) or fixed-width raw byte fields.

**Common ordering rule (cheap on-chain and off-chain).** Within each tree the leaves are ordered
**ascending, byte-lexicographic, by the tree's declared sort key**. Because every candidate sort key
below is a fixed-width byte string (a 32-byte hash or a 32-byte pubkey/commitment), ordering is a
plain unsigned big-endian byte comparison — no field parsing, no NFC, no numeric-string comparison,
and it is identical in a Solana program (`sol_memcmp` over 32-byte arrays) and in an off-chain
pipeline. A verifier checks the committed leaf list is strictly monotonic under this key. This was
chosen over a semantic multi-field key (`cohort_id`, then `time_range.*`) precisely to avoid
numeric-string comparison of integer-string fields (`"10"` vs `"9"`), which is a cross-language
determinism footgun; the batch header still binds those semantic fields, so nothing auditability-wise
is lost.

**1. Evidence epoch tree — `DOMAIN_TAG = CRP:evidence:v1`.** Leaves are signed evidence *batch
headers*: one leaf per `evidence.schema.json` instance in the epoch.

```
canonical_leaf_bytes(batch) = CJSON(batch)      # the full batch object, INCLUDING batch_signature
leaf_hash(batch)            = SHA-256( 0x00 || "CRP:evidence:v1" || canonical_leaf_bytes(batch) )
```

Including `batch_signature` binds the producer signature into the leaf. **Sort key: `leaf_hash`
ascending.** Tie-break / totality: two leaves can share a `leaf_hash` only if they are byte-identical
batch objects; a producer MUST NOT place two byte-identical batch leaves in one epoch (hard error),
so the order is total. Rationale for hashing the whole header rather than sorting on a natural
scalar: a batch header is a composite object with no single monotonic identifier in the minimized
schema (adding a record-id would be surplus data and an insertion-order proxy, violating the
data-derived rule); `leaf_hash` is fully data-derived and needs no field parsing.

**2. Observation sub-commitment — leaf domain `obs`** (root = `observations_commitment.merkle_root_hex`).
Leaves are the per-observation content commitments (each the 32 raw bytes of a
`$defs.observation_leaf.payload_commitment_hex`):

```
observation_commitment_be32 = the 32 raw bytes decoded from payload_commitment_hex
leaf_hash                    = SHA-256( 0x00 || "obs" || observation_commitment_be32 )
```

**Sort key: `observation_commitment_be32` ascending** (the "sorted set" of content commitments).
Tie-break / totality: identical commitments are the same off-chain reading; a batch MUST NOT list a
content commitment twice (hard error), so the order is total. Unlike the base58 `signer_pubkey`
(item 3), the raw-byte derivation here needs no extra length pin: `payload_commitment_hex` is
schema-constrained to `^[0-9a-f]{64}$` (64 lowercase hex characters ≡ exactly 32 bytes), so the
decode is fixed-width by construction. The same holds for both `merkle_root_hex` fields
(`^[0-9a-f]{64}$`).

**3. Signer set sub-commitment — leaf domain `signer`** (root = `signer_set_commitment.merkle_root_hex`).
Leaves are the 32-byte ed25519 signer pubkeys (`signer_pubkey_be32` = the 32 raw bytes decoded from
the base58 `signer_pubkey`). The base58 variant is the Bitcoin/Solana alphabet
(`123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz`, as already implied by the schema
regex `^[1-9A-HJ-NP-Za-km-z]{32,44}$`), and `signer_pubkey` MUST base58-decode to EXACTLY 32 bytes;
any other decoded length (e.g. 31 or 33 bytes, which the `{32,44}`-*character* regex does not
exclude) is a hard error and the leaf is rejected. This length pin is mandatory because the sort
key is a fixed-width 32-byte comparison (`sol_memcmp` on-chain / big-endian byte compare off-chain,
per §6.5's common ordering rule): a non-32-byte `signer_pubkey_be32` would diverge on-chain vs
off-chain and would admit an invalid pubkey (Invariant 2).

```
leaf_hash = SHA-256( 0x00 || "signer" || signer_pubkey_be32 )
```

**Sort key: `signer_pubkey_be32` ascending** (the "sorted set of signer pubkeys" the schema
references; `signer_pubkey_be32` is exactly the 32-byte base58 decode required above — a leaf whose
`signer_pubkey` does not base58-decode to exactly 32 bytes is rejected before ordering). Tie-break /
totality: a pubkey is a set member; it MUST NOT appear twice (hard error), so the order is total.

`epoch_index` is fixed within one epoch tree; the epoch tree therefore commits exactly the batch
set of that epoch. The two sub-commitment roots are ordinary string fields inside each batch header,
so their determinism (via the ordering above) is what makes the enclosing evidence `leaf_hash`
deterministic in turn.

**Vector-readiness (RATIFIED v1.1, RESIDUAL C closed).** All three evidence trees are complete and
unambiguous for golden-vector construction: each has (a) a fixed leaf preimage, (b) a total,
data-derived sort key (`leaf_hash` / `observation_commitment_be32` / `signer_pubkey_be32`, all
32-byte unsigned big-endian compares), (c) an explicit tie-break (strict monotonicity ⇒ duplicates
are a hard error), and (d) the shared §6.1 node formulas + §6.3 promotion + §6.4 empty-tree
sentinel. Nothing in leaf construction, ordering, or root computation is left to producer choice, so
`verifier-reproducibility-engineer` can build byte-identical golden evidence roots (epoch, signer,
observation) for any batch set. No change to §6.5 bytes was needed in v1.1; this note only records
the confirmation. *(The adjacent question — how a multi-batch epoch's per-batch sub-roots map onto
the singular `EvidenceEpoch.signer_set_root` / `observations_root` account fields — was previously
flagged OUT OF SCOPE here; it is now RESOLVED in §6.5.2 below, additively and without changing any
§6.5 leaf byte.)*

#### 6.5.1 Evidence ingestion rejection codes (wire contract)

Evidence ingestion and bundle assembly raise **stable, machine-readable rejection codes**. These
codes ARE part of the wire contract: golden vectors name them, the SDKs surface them, and the
dashboard renders them. A code's string value is frozen; **adding** a code is an additive change,
**renaming** one is a breaking change. A *rejection* (this table) means the input is unusable and the
batch/tree/bundle is refused — distinct from a *finding* (admissible-but-suspicious, recorded in the
audit bundle, never a silent drop). Every code below rejects anything that would make two honest
verifiers disagree (Invariant 2) or that admits provably duplicated / inconsistent evidence.

| Code | Raised when |
| --- | --- |
| `SCHEMA_INVALID` | The batch/table fails `evidence.schema.json` (unknown field, wrong type, closed-schema violation) or a hex/commitment field is malformed. |
| `UNSUPPORTED_SPEC_VERSION` | The batch declares a `spec_version` this ingester does not implement. |
| `NON_CANONICAL_INTEGER_STRING` | A numeric-string field is not in §2.1 canonical form (leading zero, sign, whitespace). |
| `TIME_RANGE_INVALID` | A batch `time_range` is not a well-formed non-empty range: it violates `start ≤ end` (both are §2.2 second-scale unsigned integer strings), or otherwise fails the range constraints `evidence.schema.json` documents. Rejected because a malformed or inverted range corrupts the batch header that is hashed into the epoch leaf (§6.5 tree-1) and the on-chain `EvidenceEpoch.time_range`. |
| `AGGREGATE_SUMMARY_INCONSISTENT` | A batch's `aggregate_summary` integer counts do not agree with the committed member sets / declared sub-commitments — e.g. `distinct_signers` exceeds `signer_set_commitment.signer_count`, `accepted_count` + `rejected_count` is inconsistent with the observation set, or `quality_score_micro_sum` is not the declared sum. Rejected because these integers are anchored on-chain and consumed by the Stage-2 split (`reward-policy.md`); an internally inconsistent summary would let two verifiers derive different weights. |
| `SIGNER_PUBKEY_NOT_32_BYTES` | A `signer_pubkey` does not base58-decode to exactly 32 bytes (§6.5 tree-3 length pin). |
| `SIGNER_PUBKEY_INVALID_BASE58` | A `signer_pubkey` is not valid base58 in the Bitcoin/Solana alphabet. |
| `BATCH_HEADER_HASH_MISMATCH` | The recomputed batch-header hash ≠ the declared `batch_signature.header_hash_hex`. |
| `BATCH_SIGNATURE_INVALID` | The batch signature does not verify under the declared producer pubkey. |
| `UNSUPPORTED_SIGNATURE_ALGO` | The batch declares a signature algorithm the ingester does not support. |
| `REPLAYED_BATCH` | A byte-identical batch (or its content hash) was already anchored. |
| `DUPLICATE_EVENT_NONCE` | Two observations reuse an event nonce within the dedup scope. |
| `EXPERIMENT_ID_MISMATCH` | The batch `experiment_id` ≠ the experiment being assembled. |
| `EPOCH_INDEX_NOT_MONOTONIC` | Epoch indices are not strictly increasing / gap-free (mirrors the on-chain no-gap rule). |
| `EPOCH_OUT_OF_SCHEDULE` | A batch's epoch/time-range falls outside the frozen active window or schedule. |
| `DUPLICATE_EVIDENCE_LEAF` | Two byte-identical batch leaves in one epoch tree (breaks §6.5 tree-1 strict monotonicity). |
| `DUPLICATE_SIGNER_LEAF` | A signer pubkey appears twice in one signer sub-tree (§6.5 tree-3). |
| `DUPLICATE_OBSERVATION_LEAF` | A content commitment appears twice in one observation sub-tree (§6.5 tree-2). |
| `SUBTREE_ROOT_MISMATCH` | A recomputed signer/observation sub-root ≠ the declared `merkle_root_hex`. |
| `LEAF_COUNT_MISMATCH` | A declared `signer_count` / `leaf_count` ≠ the actual member-set size. |
| `BUNDLE_INCOMPLETE` | The bundle is missing a required file, or `analysis.json` and `rewards.parquet` are not supplied together. |
| `BUNDLE_CONTENT_ADDRESS_MISMATCH` | A file's recomputed content hash ≠ the hash `roots.json` names it by. |
| `DATA_MINIMIZATION_VIOLATION` | A table/field carries content forbidden by Invariant 5 (raw telemetry, coordinates, per-reading timestamps, personal data). |

`TIME_RANGE_INVALID` and `AGGREGATE_SUMMARY_INCONSISTENT` are documented here as first-class codes
in this round; both were already enforced at ingestion. `evidence.schema.json` expresses the
structural side of each constraint (types, patterns) but does not carry the codes — the codes are
this table's contract.

#### 6.5.2 Epoch sub-root → singular on-chain field mapping (RESOLVED)

The on-chain `EvidenceEpoch` account (evidence-registry) has **singular** `signer_set_root` and
`observations_root` fields (`[u8; 32]` each), but a multi-batch epoch has **one signer sub-root and
one observation sub-root per batch** (the `signer_set_commitment.merkle_root_hex` /
`observations_commitment.merkle_root_hex` inside each batch header). This section pins, normatively,
how the `n` per-batch sub-roots of an epoch combine into each singular on-chain field, such that the
value is **recomputable from the audit bundle with no re-ingestion of member sets**.

**Ordered per-batch sub-root lists.** For an epoch, order its batches by the **§6.5 tree-1 order**
(batch-header `leaf_hash` ascending) — exactly the order in which the bundle's `roots.json`
publishes `per_batch_signer_set_root_hex` and `per_batch_observations_root_hex`. Let the ordered raw
32-byte sub-roots be `R = [r_0, …, r_{n-1}]` (signer) and `Q = [q_0, …, q_{n-1}]` (observation).

**Combination rule (`combine`).** Each singular field is an accumulation over its ordered per-batch
sub-root list. The per-batch sub-roots are **already** domain-separated SHA-256 roots (of the
`signer` / `obs` sub-trees, §6.5), so they are treated as **already-hashed leaf-level nodes** and are
combined with the §6.1 **interior** node formula only (no additional `0x00` leaf hash):

```
combine(L):                       # L = ordered list of raw 32-byte sub-roots
  n == 0 → 32 zero bytes          # §6.4 empty-tree sentinel: "no batches anchored this epoch"
  n == 1 → L[0]                   # identity: the epoch commitment IS the sole batch's sub-root
  n >= 2 → treat L as one Merkle level of already-hashed nodes; pair with
           node_hash = SHA-256(0x01 || left || right) (§6.1), promote the unpaired
           trailing node unchanged at each level (§6.3), up to a single 32-byte root

EvidenceEpoch.signer_set_root   = combine(R)
EvidenceEpoch.observations_root = combine(Q)
```

Rationale and properties:

- **Identity for the single-batch epoch (the MVP-pilot common case): `n == 1 ⇒ field == the sole
  batch's sub-root`.** A coordinator posting a one-batch epoch anchors that batch's own
  `signer_set`/`observations` root verbatim — no re-hashing, matching the intuitive meaning and the
  existing single-batch posting behavior.
- **Second-preimage separation is preserved.** A per-batch sub-root has an `0x00`-prefixed preimage
  (`SHA-256(0x00 || "signer"|"obs" || …)`, §6.5); an accumulation node has an `0x01`-prefixed
  preimage (§6.1). The two prefixes can never collide, so a sub-root can never be reinterpreted as an
  accumulation node even though `combine` does not re-leaf-hash. Domain separation from other trees
  is inherited from the sub-roots themselves.
- **Recomputable from the bundle, no re-ingest.** `combine` consumes only the ordered per-batch
  sub-root lists already in `roots.json`; a verifier reproduces both singular fields without touching
  member sets. The epoch tree-1 root (`evidence_epoch_root_hex`) independently binds the same batch
  set transitively (each batch header, which contains both sub-roots, is a tree-1 leaf), so the
  singular fields and the epoch root are mutually consistent commitments to the same batches.
- **The chain does not enforce the mapping.** `post_evidence_epoch` stores the posted 32-byte roots
  verbatim (it cannot cheaply recompute `combine`, since the sub-roots live off-chain). Correctness
  of the mapping is enforced off-chain by reproduction + the challenge process (Invariant 6), exactly
  as for `reward_root` (§6.6). A posted singular field that does not equal `combine(...)` of the
  bundle's ordered per-batch sub-roots is a bond-backed, upheld challenge.

> **`solana-program-engineer` confirmation requested (does not block this spec ruling).** The
> mapping is defined so the single-batch epoch stores a batch sub-root verbatim (no on-chain change
> for the common case) and multi-batch epochs store an off-chain-computed accumulation. Confirm the
> evidence-registry / SDK posts `combine(R)` / `combine(Q)` for `n ≥ 2` and that no on-chain
> recomputation is expected. No program edit is implied for single-batch epochs.

*Rejected alternative (recorded):* re-leaf-hashing each sub-root under a new `epoch-signer-set` /
`epoch-obs-set` domain tag would be uniform with §6.1 but would make the single-batch field
`SHA-256(0x00 || tag || r_0) ≠ r_0`, needlessly breaking the identity property for the dominant
single-batch case and diverging from existing posting behavior. The `combine` rule above is chosen
for that identity property; it is still fully domain-separated by the sub-roots' own `0x00` prefixes.

### 6.6 Reward tree (leaf form + ordering, RATIFIED)

The reward tree is a §6.1-shaped Merkle tree over one leaf per reward entry produced by the Stage-2
reward compiler (`reward-policy.md`). Its root is the `reward_root` that `finalize_distribution`
locks and `claim_reward` proves against. Like the evidence sub-commitments (§6.5), a reward leaf is
a **fixed-width raw-byte structure, NOT CJSON**: §2 (no JSON number tokens) and §3 (CJSON) do **not**
apply to it; the §6.1 node formulas (`0x00`/`0x01` prefixes, promotion §6.3, empty-tree sentinel
§6.4) do. `DOMAIN_TAG = CRP:reward:v1` (ASCII, §6.1 table).

**Leaf preimage (RATIFIED, fixed width).** Field order, widths, and endianness are fixed exactly as
below:

```
recipient          : 32 raw bytes  — the recipient's ed25519 Solana pubkey (its native 32-byte form)
amount_base_units  :  8 bytes, u64 BIG-ENDIAN — mint-native base units (money, scale 1, §2.2)
leaf_index         :  8 bytes, u64 BIG-ENDIAN — the leaf's 0-based tree position / nullifier key

reward_leaf_content = recipient || amount_base_units_be || leaf_index_be          # exactly 48 bytes
leaf_hash           = SHA-256( 0x00 || "CRP:reward:v1" || reward_leaf_content )    # preimage 1+13+48 = 62 bytes
```

Big-endian is chosen for `amount_base_units` and `leaf_index` to match the rest of this spec (§7.3
PRF, §7.2 seed) and to guarantee cross-language hash determinism (Invariant 2). This is a raw-byte
leaf, so the money value is carried as an 8-byte integer, not a decimal string — the §2 "no JSON
number token" rule governs only CJSON artifacts and is not in scope here (mirroring the raw 32-byte
`obs`/`signer` leaves of §6.5). Because the content is a constant 48 bytes at fixed offsets, the
map `(recipient, amount_base_units, leaf_index) → leaf_hash` is injective, and the `0x00` leaf prefix
plus the `CRP:reward:v1` domain tag give the §6.1 second-preimage / cross-tree separation with no
length-ambiguity (there is nothing variable-length to misparse). This ratifies the settlement
program's provisional layout **unchanged** (`crates/crp-crypto`: `reward_leaf_content` /
`reward_leaf_hash`; `programs/settlement` `claim_reward`).

**Ordering (resolves the §6.2 reward deferral).** Leaves are placed in the tree by `leaf_index`:
**ascending and contiguous from 0** — the leaf at tree position `p` has `leaf_index == p`, with no
gaps. All normative:

- **Duplicate `leaf_index`** in one reward tree is a **hard error**. It both breaks the total order
  and collides the per-experiment `ClaimReceipt` nullifier PDA `[b"claim", experiment,
  leaf_index_le]`, which would render one of the colliding leaves permanently unclaimable.
- **A gap** (any missing index in `0..N-1`) is a **hard error**; `leaf_index` values are exactly the
  integers `0 … N-1` for an `N`-leaf tree.
- The **empty reward tree** (`N = 0`, e.g. a fully-null distribution under `reward-policy.md`
  Stage-1 step 4) has root = 32 zero bytes (§6.4). `finalize_distribution` then locks a zero root and
  the whole budget is recoverable.

Because position `== leaf_index`, `build_proof`/`verify_proof` (§6.1) address a leaf directly by its
`leaf_index`, which is also the exact value `claim_reward` takes and the nullifier key — one integer
identifies the leaf end-to-end.

**`leaf_index` assignment (data-derived; RATIFIED v1.1, RESIDUAL A closed).** For the tree to be
reproducible (Invariant 2), `leaf_index` MUST be a deterministic, **data-derived total ranking** of
the compiler's final reward-leaf set — never insertion order, wall-clock, or unseeded iteration (the
same anti-insertion-order rule as §6.2).

*Leaf-set shape (PINNED): aggregate-one-leaf-per-recipient.* The Stage-2 compiler
(`reward-policy.md`) produces a per-`(recipient, cohort)` amount `leaf_i(c)` (a recipient is
identified by the 32-byte ed25519 signer pubkey that signed its observations, which is exactly the
reward `recipient`). The reward leaf set is the **aggregate over cohorts**: for each distinct
recipient `R`, one leaf `(R, amount_base_units = Σ_c leaf_i(c))`, and **recipients whose aggregate
sum is 0 are omitted** (a zero leaf is unclaimable value and wastes a `leaf_index` / nullifier PDA).
Aggregation is integer addition of already-final amounts — it introduces no rounding (§2.4) and
preserves the budget guarantee exactly (`Σ_R amount(R) = Σ_c Σ_i leaf_i(c) ≤ Σ_c budget_c ≤ B`,
`reward-policy.md`). It is a settlement-representation choice fully downstream of the frozen Stage-2
split: it alters no effect estimate, weight, or split ratio (Invariant 4 is already satisfied at
Stage 1) and it minimizes on-chain footprint — one leaf, one claim, one nullifier per recipient
(Invariant 5). This is fixed in `reward-policy.md` Stage 2 and pinned here.

*Rank key (PINNED): ascending by `recipient`* (unsigned big-endian 32-byte compare, i.e.
`sol_memcmp` order), *then ascending by `amount_base_units`*; `leaf_index` is the 0-based rank under
this key. **No further tie-break is needed and none exists:** the aggregate-per-recipient shape makes
`recipient` a **unique primary key** across the leaf set (two leaves cannot share a 32-byte
`recipient` — that would be the same recipient, already merged by aggregation), so `recipient` alone
totally orders the leaves. `amount_base_units` is retained as the pinned secondary key for defensive
consistency but is never decisive. Because `recipient` is unique, **a leaf set containing two leaves
with the same `recipient` is a hard error** (a compiler bug); the SDK's existing *reject-on-
ambiguity* is therefore the correct, still-required defensive behavior — after v1.1 it can only fire
on a malformed compiler output, never on a legitimate ambiguous tie.

This closes the residual without touching the leaf *preimage* (fully pinned above); it only fixes how
the compiler *numbers* leaves. §6.6 owns the byte layout and the index-based tree order; the compiler
(`reward-policy.md`) owns the leaf *values* `(recipient, amount_base_units)` and the aggregate shape.
*(A future variant that instead committed one leaf per `(recipient × cohort)` for on-chain
per-cohort transparency would need a tie-break sub-key — the natural one being the stratum/`cohort_id`
— and would be a versioned migration (§9), not the pinned v1.1 shape.)*

**experiment binding (DECIDED): the reward leaf does NOT bind `experiment_id`.** This follows the
§7.5 assignment-leaf precedent, for the same reason and with the same safety argument. The
`reward_root` is committed in the per-experiment `Distribution` PDA (`[b"distribution", experiment]`),
`claim_reward` verifies the leaf's Merkle proof against *that* experiment's finalized root, and the
`ClaimReceipt` nullifier is per-experiment. Cross-experiment replay is therefore structurally
impossible: to draw experiment Y's vault, `verify_proof(reward_leaf_hash(R,A,i), proof, Y.reward_root)`
must hold, which requires leaf `(R,A,i)` to be a member of Y's committed tree. If it is **not** in Y's
tree, no proof exists and the claim fails; if it **is** in Y's tree, then `R` is genuinely owed `A`
under Y and claiming is legitimate (single-use per Y via the nullifier). No proof valid under
experiment X ever yields funds from experiment Y for a leaf absent from Y's tree — so the same
`(recipient, amount, leaf_index)` triple appearing in two experiments' trees is two independent
entitlements, not a replay. Binding `experiment_id` into the leaf would add 32 bytes to every
preimage and every on-chain claim to buy a property already guaranteed by the Distribution-account
binding plus the proof-against-root check, so it is deliberately omitted (exactly as §7.5 omits it
from the assignment leaf).

**Endianness note (do not "harmonize").** The leaf preimage encodes `amount_base_units` and
`leaf_index` **big-endian** (hashed-artifact determinism, above). The `ClaimReceipt` nullifier PDA
seed encodes `leaf_index` **little-endian** (`leaf_index.to_le_bytes()`, the Solana/Anchor idiom for
address derivation — a PDA seed is not a hashed protocol artifact). These two encodings of the same
`leaf_index` are intentionally different and independent; neither may be changed to match the other.

## 7. Seed commitment & assignment derivation

Two distinct steps, structurally enforcing freeze-before-reveal (Invariant 1). The manifest freezes
`seed_commitment(seed)`; the seed is revealed later via `reveal_seed`; verification then (1) checks
the commitment and (2) derives the assignment. Both are pure functions of committed/revealed inputs —
no wall-clock, no unseeded RNG, no float.

### 7.1 Seed

The assignment seed is a **32-byte** value, surfaced as 64-char lowercase hex in the reveal payload
and audit bundle. The seed itself MUST NOT appear in the manifest (the manifest schema has no field
to hold it).

### 7.2 Commitment

```
SEED_COMMIT_DOMAIN = b"CRP-seed-commit-v1"      # ASCII bytes
seed_commitment    = SHA-256( SEED_COMMIT_DOMAIN || seed )   # seed is the raw 32 bytes
```

There is **no separate salt**: a 32-byte high-entropy seed is itself the hiding randomness, and the
domain tag provides separation. This exactly matches the verifier reference (`assignment.py:
seed_commitment`). The manifest's `assignment.seed_commitment.scheme` const records this construction.

### 7.3 Per-cohort PRF (unambiguous, length-prefixed)

```
ASSIGN_PRF_DOMAIN = b"CRP-assign-v1"            # ASCII bytes
msg     = ASSIGN_PRF_DOMAIN
        || seed                                   (32 bytes)
        || u32be(len(experiment_id_utf8)) || experiment_id_utf8
        || u32be(len(cohort_id_utf8))     || cohort_id_utf8
prf_u64 = big-endian uint64 of SHA-256(msg)[0:8]
```

`u32be(n)` is the 4-byte big-endian encoding of a length that MUST fit in `u32`. Length-prefixing the
variable-length ids prevents any two `(experiment_id, cohort_id)` pairs from colliding via naive
concatenation. `prf_u64` is an auditable intermediate published in the assignment table but is **not**
part of any leaf preimage (it is a deterministic function of the committed/revealed inputs).

### 7.4 Designs (integer arithmetic only)

- **bernoulli** — params `{"treat_fraction_ppm": "<uint string>"}`, `0 ≤ treat_fraction_ppm ≤
  1000000`: cohort is `treatment` iff `(prf_u64 mod 1_000_000) < treat_fraction_ppm`. Independent per
  cohort; expected (not exact) balance. Integer modulus only.
- **fixed_count** — params `{"treatment_count": "<uint string>"}`, `0 ≤ treatment_count ≤ n_cohorts`:
  sort cohorts by `(prf_u64, cohort_id)` ascending; the first `k` are `treatment`. Exact balance;
  `cohort_id` breaks `prf_u64` ties.

**Derivation selector (manifest → derivation name).** The derivation is selected by the manifest's
`treatment.assignment_method`, mapped to the derivation names used here and in the reference
implementation:

| `treatment.assignment_method` | `design.template` | §7.4 derivation |
| --- | --- | --- |
| `bernoulli` | `cluster_randomized` | **bernoulli** (above) |
| `complete_randomization` | `cluster_randomized` | **fixed_count** (above) |
| `switchback_schedule` | `switchback` | **switchback** (below) |
| `matched_pair` | `matched_cluster` | **matched_cluster** (below) |

(`observational_replay` is a design template, not eligible for the strong causal claim, and defines
no randomized seed→assignment derivation: its "assignment" is the observed inclusion history, not a
seed-derived one, so it has no assignment root of this kind.)

**Composite cohort-id grammar (switchback and matched_cluster ONLY).** `bernoulli` and `fixed_count`
treat `cohort_id` as an opaque string. The two derivations below instead require structure in the
id, so — for these two designs and ONLY these two — every `cohort_id` in the cohort set MUST match:

```
composite_cohort_id := group "|" index
"|"    := U+007C, appearing EXACTLY once in the id
group  := one or more characters, none of which is "|"
          (the geo-cohort id for switchback; the matched-stratum id for matched_cluster)
index  := canonical unsigned integer string (§2.1 form, ^(0|[1-9][0-9]*)$ — no leading zeros)
          (the period_index for switchback; the within-stratum member_index for matched_cluster)
```

Parsing splits on the single `|`. A `cohort_id` (under these two designs) with zero or more than one
`|`, an empty `group`, or a non-canonical `index` is a **hard error**, rejected before derivation.
The assignment leaf (§7.5) still carries the FULL composite `cohort_id` unchanged, and assignment
leaves still sort by the full `cohort_id` (§6.2): the grammar governs only how a derivation reads
structure out of the id, never the leaf form or the leaf ordering.

- **switchback** — a **regional randomized-phase switchback**. Each unit is `(group, index) =
  (geo_cohort, period_index)`. Randomization is **one phase bit per geo-cohort**, applied by
  alternation across periods. Reuses the §7.3 PRF verbatim, keyed on the `group` substring alone:

  ```
  phase(group)      = cohort_prf(seed, experiment_id, group) & 1     # low bit of prf_u64; ∈ {0,1}
  arm(group, index) = "treatment"  iff  ((index + phase(group)) mod 2) == 1
                    = "control"     otherwise
  ```

  Integer arithmetic only (a PRF low bit, an integer add, a mod 2). `phase(group)` is computed once
  per distinct `group`; every unit sharing that `group` uses the same phase and the arm alternates
  every period — a balanced switchback (≈50% treated time per geo; exactly balanced when a geo's
  period count is even). Because alternation is structurally 50/50, `treated_fraction_micro` MUST be
  `"500000"` for a switchback manifest (enforced by the causal engine); the derivation itself does
  **not** read `treated_fraction_micro`. `carryover_blocks` / `washout_blocks` are ANALYSIS-time
  discard parameters (which blocks within a period are dropped to neutralize carryover) and do NOT
  enter this derivation — they are frozen in the manifest for the pre-analysis plan and consumed by
  the estimator, not here. `arm` is defined for any `index ≥ 0`; a geo's period indices need not be
  contiguous (the arm is a pure function of `(group, index)` regardless).

  *Modeling note (for `causal-inference-engineer` confirmation; does NOT block vectoring — the bytes
  are pinned).* Per-geo randomized phase + deterministic alternation (chosen over independent-per-
  period randomization or a single system-wide schedule) matches the frozen `interference_assumption
  = partial_interference_within_cohort` and the per-geo-cohort × time-block estimand (regional
  switchback; cf. Bojinov–Simchi-Levi–Zhao and Hu–Wager). It is pinned here so the derivation is
  byte-deterministic now; changing the schedule policy is a versioned migration (§9), not a silent
  edit, and would only then require regenerating switchback vectors.

- **matched_cluster** — within each frozen matched stratum, a fixed number of members are treated,
  chosen by the §7.3 PRF. Each unit is `(group, index) = (stratum_id, member_index)`. The stratum
  membership (which cohorts share a `group`, and each stratum's size `m_s`) is the coordinator's
  frozen matching, carried in the cohort-id set and committed by `cohort_root` — it is a pre-analysis
  input (Invariant 1), not a manifest field. Reuses the §7.3 PRF keyed on the FULL composite
  `cohort_id`:

  ```
  for each stratum s (the set of units sharing one `group`):
    m_s = |members of s|
    k_s = round_he( treated_fraction_micro * m_s / 1_000_000 ), clamped to [0, m_s]   # §2.4 rule
    rank members ascending by (prf_u64(FULL cohort_id), index)     # `index` breaks prf ties,
                                                                   # exactly as fixed_count uses cohort_id
    first k_s ranked members -> "treatment";  the rest -> "control"
  ```

  Exact within-stratum balance. `k_s` is computed by integer arithmetic implementing round-half-to-
  even (§2.4) on the exact rational `treated_fraction_micro·m_s / 1e6`: with `N = treated_fraction_micro·m_s`,
  `D = 1_000_000`, `q = N // D`, `r = N mod D` — take `q` if `2r < D`, `q+1` if `2r > D`, and if
  `2r == D` take `q` when `q` is even else `q+1`; then clamp to `[0, m_s]`. For the canonical matched
  **pair** (`m_s = 2`, `treated_fraction_micro = "500000"`): `k_s = round_he(1.0) = 1` — exactly one
  of each pair treated. Every stratum is processed independently; the per-cohort arm is fully
  determined, and `member_index` deterministically breaks any `prf_u64` tie inside a stratum.

  *Modeling note (for `causal-inference-engineer` confirmation; does NOT block vectoring).* The
  QUALITY of the matching (whether stratum members are balanced on baseline covariates) is a design-
  validity question owned by the causal design, not a determinism question — this derivation is
  deterministic for ANY frozen stratification. Pinned here is only the byte-level rule that turns a
  frozen stratification + seed into arms.

All four randomized `(design.template, assignment_method)` pairings the manifest admits now have a
pinned, reproducible seed→assignment derivation using only §7.3 (no new primitive), only integer
arithmetic, and no wall-clock / unseeded RNG / float (Invariant 2). `verifier-reproducibility-
engineer` can commit golden assignment roots for switchback and matched_cluster exactly as for the
existing 11. This is orthogonal to freezing switchback *design parameters* in the manifest
(carryover/washout/interference), already done (see `manifest.schema.json` `design.parameters`).

### 7.5 Assignment leaf

```
leaf_object = { "arm": <"treatment"|"control">, "cohort_id": <string> }
leaf_bytes  = CJSON(leaf_object)
```

Serialized under §3, the two ASCII keys sort as `arm` before `cohort_id`. The leaf binds only the
committed decision (`arm`, `cohort_id`); it does **not** bind `experiment_id` (the assignment root is
already committed under a specific experiment on-chain, so binding it again would only make on-chain
verification costlier) and does **not** bind `prf_u64` (a derived intermediate).

## 8. Conformance

An implementation conforms to this document iff, for every input in `test-vectors/`, it reproduces:
the canonical UTF-8 bytes (`ser-*`), the seed commitment, each per-cohort `prf_u64`, each canonical
leaf's bytes and hash, and the assignment Merkle root (`assign-*`) — including, under v1.1, the
switchback and matched_cluster assignment roots (§7.4) and the reward and evidence Merkle roots
(§6.6, §6.5). The reference implementation in `verifier-cli/reference/` is the executable form of
§2–§7 and generates/checks those vectors. The manifest golden hash (`manifest.golden.md`) is
reproduced by feeding the canonical example manifest through this exact serializer — no assumed field
layout, only §2–§5 applied to the JSON value.

### 8.1 Bundle content-addressing and the M3 reproduction gate (RULING)

The audit bundle (`protocol.md` §4: `manifest.json`, `participants.parquet`, `assignment.parquet`,
`evidence/*.parquet`, `analysis.json`, `rewards.parquet`, `roots.json`, `provenance.json`) can be
addressed two ways, and the assembler computes both:

- **`bundle_content_hash`** — a hash over the **exact file bytes** of the bundle. It is
  **NOT byte-stable across environments**: Apache Parquet embeds a `created_by` string and admits
  encoder/compression variation, so two conforming producers on different `pyarrow` versions emit
  byte-different Parquet for identical logical tables. `bundle_content_hash` therefore depends on the
  container encoder, not only on the protocol content.
- **`bundle_logical_hash`** — a hash over the bundle's **canonical logical commitment set**: the
  ordered set of protocol roots and canonical-artifact hashes the protocol actually commits
  (the manifest hash; the participant, assignment, evidence epoch/signer/observation roots; the
  per-batch sub-root lists; the `result_artifact_hash` = `SHA-256` over `analysis.json`'s canonical
  bytes; the `reward_root`). Concretely `bundle_logical_hash = SHA-256(CJSON(L))`, where `L` is the
  `roots.json` logical object serialized under §2–§5 (stable ASCII-key ordering, string-encoded
  values, no Parquet bytes). It is **portable and cross-machine**: it is invariant to `pyarrow`
  version, compression, and row-group layout because it never hashes Parquet bytes — only the
  §2–§5-canonical projection of the committed roots.

**RULING (normative).** `bundle_logical_hash` is the **normative** object for the M3 acceptance gate
("independent reproduction from the bundle"). The gate is satisfied iff an independent party, from the
bundle and with zero network access (`protocol.md` §5), **recomputes every entry of the logical
commitment set `L` from the underlying tables and each equals the corresponding on-chain
commitment** — equivalently, recomputes `bundle_logical_hash` and it matches. Reproducibility
(Invariant 2) is a property of the protocol's committed roots, not of the Parquet container, so
requiring byte-identical Parquet across environments would make honest reproduction spuriously fail
while adding no integrity the roots do not already provide.

`bundle_content_hash` is **advisory only**: it is retained for exact-byte provenance, caching, and
dedup within a single producer environment, and it MUST NOT gate M3 acceptance or a challenge outcome.
A `bundle_content_hash` mismatch under an equal `bundle_logical_hash` is a container-encoding
difference (a *finding* at most, per §6.5.1's rejection-vs-finding distinction), never a reproduction
failure. Note the individual `BUNDLE_CONTENT_ADDRESS_MISMATCH` code (§6.5.1) still applies to a file
whose recomputed content hash disagrees with the hash `roots.json` names it by *within one bundle* —
that is per-file integrity inside a fixed environment, distinct from cross-environment byte-stability
of the whole bundle addressed here.

## 9. Revision history

The wire/hash contract version and this document's version advance together (both `serialization.md`
is wholly the wire/hash contract). A change that alters no byte of any existing hashed artifact is an
**additive minor**; a change that alters a golden is a **major** and a manifest `spec_version` bump.

### 1.1.0 addendum — evidence ingestion codes + epoch sub-root mapping (additive, hash-compatible)

Recorded in the M3 spec round (2026-07-24). **The wire/hash contract version stays 1.1.0**: every
change here is additive and alters **no byte** of any existing hashed artifact — manifest golden
`74e0bb82…`, `reward_curve_hash` `14b0ec34…`, evidence example `901b08d5…`, and all 11 `assign-*`
roots are byte-identical. The manifest `spec_version` field stays `"1.0.0"`. No schema field,
example, or golden changed.

- **§6.5.1 evidence-ingestion rejection codes (additive to the wire contract).** The rejection-code
  table is part of the wire contract (golden vectors name the codes, SDKs surface them, the dashboard
  renders them). **Adding** a code is an additive change; **renaming** one would be breaking. This
  round documents two already-enforced codes as first-class entries — `TIME_RANGE_INVALID` (malformed
  or inverted batch `time_range`) and `AGGREGATE_SUMMARY_INCONSISTENT` (`aggregate_summary` integer
  counts disagree with the committed member sets / declared sub-commitments) — alongside the existing
  codes. `evidence.schema.json` expresses the structural side (types, patterns); the codes are this
  table's contract, not the schema's, so `evidence.example.json` is unchanged and its golden is
  undisturbed.
- **§6.5.2 epoch sub-root → singular on-chain field mapping (additive; defines an on-chain field,
  changes no hashed off-chain byte).** Pins how a multi-batch epoch's `n` per-batch signer/observation
  sub-roots combine into the singular `EvidenceEpoch.{signer_set_root, observations_root}` account
  fields via `combine(L)`: `n==0 →` 32 zero bytes (§6.4), `n==1 →` the sole batch's sub-root verbatim
  (identity — the dominant single-batch pilot case is unchanged on-chain), `n≥2 →` the sub-roots
  treated as one Merkle level of already-hashed nodes combined with the §6.1 interior formula
  (`0x01`) + §6.3 promotion. Second-preimage separation is preserved (sub-roots carry the `0x00`
  leaf prefix, accumulation nodes the `0x01` prefix). Recomputable from `roots.json`'s ordered
  per-batch sub-root lists with no re-ingest. This defines the meaning of an on-chain field; it
  introduces no new off-chain hashed artifact and moves no existing one.
- **§8.1 bundle content-addressing ruling (prose ruling, no hashed byte).** Ruled `bundle_logical_hash`
  (portable, cross-machine, over the §2–§5-canonical commitment set) NORMATIVE for the M3
  reproduction gate; `bundle_content_hash` (exact Parquet bytes, `pyarrow`-version-scoped) advisory
  only. Parquet is not byte-stable across `pyarrow` versions, so the gate asserts the committed
  roots, not the container bytes. Moves no artifact.
- **`hac` SE-method narrowing (schema description only).** Narrowed the `standard_error_method`
  enum documentation in `manifest.schema.json` so `hac` for `switchback` means "unrestricted
  clustering on the geo group" with no frozen bandwidth field — resolving the former
  `hac_bandwidth_blocks` open item as documentation, not a new frozen field. Schema `description`
  only; `manifest.example.json` uses `cluster_robust` and is unchanged, so the manifest golden is
  undisturbed.

### 1.1.0 — residual closure (additive, hash-compatible)

- **Wire/hash contract: additive, hash-compatible.** No byte of any existing hashed artifact changed.
  Manifest golden `74e0bb82…`, `reward_curve_hash` `14b0ec34…`, evidence example `901b08d5…`, and all
  11 existing `assign-*` roots are **byte-identical** to 1.0. The manifest `spec_version` field stays
  `"1.0.0"`; a v1.0.0 manifest is valid and hashes identically under 1.1. No manifest/evidence schema
  field, example, or `spec_version` changed. Only previously-open residuals are pinned; the new byte
  layouts they define are additive (they produce artifacts that did not exist under 1.0).
- **RESIDUAL A — reward `leaf_index` assignment closed (§6.6, `reward-policy.md` Stage 2).** Reward
  leaf-set shape is pinned as **aggregate-one-leaf-per-recipient** (sum a recipient's per-cohort
  Stage-2 amounts into a single leaf; drop zero-sum recipients). This makes `recipient` a unique
  primary key, so the pinned rank key (`recipient` asc, then `amount_base_units` asc) is a total order
  with **no tie-break needed**; a duplicate `recipient` is a hard error, and the SDK's reject-on-
  ambiguity remains the correct defensive guard. Resolves the former "(recipient, amount) not unique"
  residual structurally, from the already-frozen Stage-2 split, with no causal-modeling change.
- **RESIDUAL B — switchback + matched_cluster seed→assignment derivations pinned (§7.4).** Added a
  derivation-selector map (`assignment_method` → derivation), a composite `group"|"index` cohort-id
  grammar (switchback/matched_cluster only), the **switchback** derivation (per-geo phase bit via the
  §7.3 PRF + parity alternation across periods; `treated_fraction_micro` must be `"500000"`;
  carryover/washout are analysis-time, not assignment-time), and the **matched_cluster** derivation
  (per-stratum `k_s = round_he(treated_fraction_micro·m_s/1e6)` treated, ranked by §7.3 PRF then
  `member_index`). Both reuse §7.3 (no new primitive), integer-only, float-free. Two modeling notes
  are flagged for `causal-inference-engineer` confirmation; they do NOT block vectoring because the
  bytes are pinned (any later schedule/matching-policy change is a versioned migration).
- **RESIDUAL C — evidence Merkle leaf sort keys confirmed complete (§6.5).** No byte change; recorded
  a vector-readiness confirmation that all three evidence trees (epoch, signer, observation) have a
  total, data-derived sort key with explicit tie-break, ready for golden evidence-root vectors.

### 1.0.0 — initial ratified serialization

Canonical CJSON (§2–§5), SHA-256 Merkle construction (§6), seed commitment + bernoulli/fixed_count
assignment derivation (§7), reward leaf preimage (§6.6) and evidence trees (§6.5) pinned; manifest,
reward-curve, evidence, and 11 assignment golden vectors committed.
