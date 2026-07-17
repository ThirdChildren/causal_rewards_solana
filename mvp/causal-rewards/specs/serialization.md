# Canonical Serialization & Hashing (NORMATIVE — RATIFIED)

**Spec version:** 1.0.0
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
| **micro** | 1e6 | `*_micro` | `confidence_level_micro`, `critical_value_micro`, `treated_fraction_micro`, `quality_score_micro`, `uptime_micro` |
| **ppm** (assignment params) | 1e6 | `*_ppm` | `treat_fraction_ppm` |
| **base units** (money) | 1 (mint-native integer) | `*_base_units`, reward-curve outputs, reward leaves | `budget_base_units`, `challenge_bond_base_units`, reward-curve output axis, per-participant reward leaves |
| **count / seconds / index** | 1 | plain integer semantics | `created_at`, `cohort_count`, `block_seconds`, `block_count`, all `windows.*`, `minimum_sample.*`, `threshold`, `treatment_count`, `df` |
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
| evidence | `CRP:evidence:v1` |
| reward | `CRP:reward:v1` |

### 6.2 Leaf ordering (data-derived, not insertion order)

Leaf order is a canonical sort key **derived from the leaf data**, so two producers holding the same
set always build the identical tree. Per tree type:

- **assignment:** sort by `cohort_id` ascending (UTF-16 code-unit of the NFC-normalized id).
- **participant / evidence / reward:** sort key is pinned when each schema lands (recommendation of
  record: participant → participant id; reward → recipient/leaf id; evidence → batch sequence then
  record id). These MUST be fixed here before their first golden root is committed (M2/M3).

### 6.3 Odd-node handling

If a level has an odd number of nodes, the unpaired trailing node is **promoted unchanged** to the
next level — it is **not** duplicated. Duplicating the last node (Bitcoin-style) enables
CVE-2012-2459-class root collisions (distinct leaf sets producing the same root); promotion avoids
that class. The on-chain verifier MUST implement promotion identically.

### 6.4 Empty tree

The root of an empty tree is **32 zero bytes** — an unmistakable "nothing committed" sentinel (never
`SHA-256(DOMAIN_TAG)`).

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

These two derivations cover cluster-randomized (bernoulli) and matched/balanced (fixed_count). The
switchback and matched-cluster templates require their own derivation rules; those MUST be pinned
here before their first assignment root is committed (open item for M2, jointly with
`causal-inference-engineer`). This is orthogonal to freezing switchback *design parameters* in the
manifest (carryover/washout/interference), which is done now (see `manifest.schema.json`
`design.parameters`).

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
leaf's bytes and hash, and the assignment Merkle root (`assign-*`). The reference implementation in
`verifier-cli/reference/` is the executable form of §2–§7 and generates/checks those vectors. The
manifest golden hash (`manifest.golden.md`) is reproduced by feeding the canonical example manifest
through this exact serializer — no assumed field layout, only §2–§5 applied to the JSON value.
