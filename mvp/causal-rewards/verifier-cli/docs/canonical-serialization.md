# Canonical Serialization & Hashing — PROPOSAL

Status: **PROPOSAL by `verifier-reproducibility-engineer`.** Not yet ratified.
`protocol-architect` ratifies this into `specs/serialization.md`; until then the
reference implementation in `../reference/` and the golden vectors in
`../../test-vectors/` are the working definition every downstream implementation
should build against.

This document defines, at the byte level, how any value that is hashed, committed
on-chain, or Merkle-ized is turned into bytes. It exists to satisfy invariant 2
(determinism/reproducibility): given the same inputs, an independent party in any
language on any machine must produce identical bytes, hashes, and roots. Every
choice below that needs protocol-architect sign-off is tagged **[RATIFY]**.

An independent engineer should be able to implement this from the text alone and
reproduce every byte in the golden vectors. If any part is ambiguous, that is a
bug in this document — escalate to `protocol-architect`.

---

## 0. Scope

Applies to every **hashed artifact**: the frozen manifest, participant set,
assignment table, evidence batches, analysis-result artifact, and reward leaves —
anything whose hash or Merkle root is committed on-chain or appears in an audit
bundle's `roots.json`.

It does **not** govern human-facing/transport JSON (dashboards, RPC payloads,
the pretty-printed vector files themselves). Those may be formatted freely; only
the canonical form is ever hashed.

---

## 1. Canonical JSON

The canonical form is a **strict subset of RFC 8785 (JSON Canonicalization
Scheme, JCS)**, deliberately narrowed to remove JCS's one language-dependent
corner (number canonicalization — see §2).

Recommended and justified because JCS is an IETF RFC with existing
implementations in multiple languages, giving cross-language agreement "for free"
for the structural parts (ordering, escaping, whitespace).

### 1.1 Rules

1. **Encoding:** UTF-8, no BOM.
2. **Whitespace:** none. No spaces, newlines, or indentation between tokens.
3. **Object key ordering:** ascending by **UTF-16 code-unit** sequence, exactly as
   RFC 8785 specifies. (Implementation note: comparing the `UTF-16-BE` byte
   encodings of two keys yields this order.) For the ASCII keys used throughout
   this protocol this is identical to code-point and byte order.
4. **Object keys are unique** after NFC normalization (§3). Duplicate keys are a
   hard error, not last-wins.
5. **Array order is significant** and preserved as given by the producer.
6. **Strings:** minimal escaping (§4), NFC-normalized (§3).
7. **Booleans / null:** the literals `true`, `false`, `null`.
8. **Numbers:** **forbidden as JSON number tokens** — see §2. The canonical
   serializer must reject any bare numeric value.

### 1.2 [RATIFY] Object key ordering basis

RFC 8785 mandates UTF-16 code-unit order. An alternative is Unicode code-point
order (equivalently UTF-8 byte order), which differs only for keys containing
characters outside the Basic Multilingual Plane (U+10000+). **Recommendation:**
adopt RFC 8785 UTF-16 ordering as written, AND additionally constrain all object
keys in hashed artifacts to ASCII, so the distinction can never arise in
practice. Needs sign-off that ASCII-only keys is an acceptable schema constraint.

---

## 2. Numbers — no IEEE-754 in any hashed artifact

**Decision (strongest determinism lever): a hashed artifact contains NO JSON
number tokens. Every numeric quantity is carried as a JSON string.**

Rationale: RFC 8785 canonicalizes numbers via the ES6 `Number` (IEEE-754 double)
algorithm. That path is (a) lossy beyond 2^53, (b) subtle to reproduce
identically across languages, and (c) exactly the "float nondeterminism" invariant
2 forbids. By forbidding number tokens entirely we never invoke it. The reference
serializer enforces this mechanically: it **raises** on any `int`/`float` input,
so the rule is not merely a convention a producer might forget.

### 2.1 Representation

- **Integers:** decimal string, e.g. `"1000000000"`. Canonical form has no sign
  for zero (`"0"`, never `"-0"`), no leading `+`. Leading zeros are **not**
  normalized away by the serializer — `"007"` serializes as the 3-char string
  `007`; if a producer means the integer 7 it must emit `"7"`. (Producers own
  value-level canonicalization; the serializer only guarantees byte-faithful
  string encoding. See §2.3.)
- **Decimals / reals:** **integer-scaled fixed-point**, carried as the scaled
  integer string. Each field declares its scale in the schema. Conventions used
  by the vectors:
  - `*_ppm` — parts per million (scale 1e6). `0.5` → `"500000"`; `-0.125` →
    `"-125000"`.
  - `*_lamports` — native Solana integer unit (scale defined by the token's
    decimals); already integral.
- **No floats anywhere.** Effects, standard errors, critical values, reward
  weights, and reward amounts are all fixed-point integers at a declared scale.

### 2.2 [RATIFY] Per-field scales

The set of scales and their field bindings (which fields are `_ppm`, which reward
quantities use which integer unit, rounding mode when producers convert a real
computation to fixed-point) must be pinned in `specs/serialization.md` and the
manifest schema. **Recommendation:** ppm (1e6) for statistical quantities;
lamports/native integer for money; document the rounding mode (round-half-even
vs truncate-toward-zero) **once, globally** — this is the single most likely
source of a cross-implementation divergence in the causal engine and reward
compiler, so it must be explicit. Needs protocol-architect + causal-inference-
engineer sign-off.

### 2.3 [RATIFY] Value-level canonicalization boundary

The serializer treats strings faithfully (it does not strip leading zeros or
re-sign numeric strings). Therefore producers must emit already-canonical numeric
strings. **Recommendation:** the manifest schema constrains numeric-string fields
with a regex (e.g. `^-?(0|[1-9][0-9]*)$` for signed integers, forbidding leading
zeros and `-0`) so the schema validator catches non-canonical values before they
are hashed. Needs sign-off on the exact regex per field.

---

## 3. Unicode normalization

All string **values and object keys** are normalized to **Unicode NFC** before
serialization. Justification: the same visual/semantic string can be encoded as
composed or decomposed code points; without a fixed normal form two producers
could hash "identical" data to different bytes. Vector `ser-02-unicode-nfc`
demonstrates decomposed input (`cafe` + U+0301) producing the precomposed bytes
(`c3 a9`).

**[RATIFY]** NFC (vs NFD/NFKC/NFKD). Recommendation: **NFC** — the most widely
implemented default, canonical-composed, non-destructive (unlike the K forms
which fold compatibility characters and would alter meaning). Needs sign-off.

---

## 4. String escaping

Minimal escaping, per RFC 8785:

- `U+0022` `"` → `\"`
- `U+005C` `\` → `\\`
- `U+0008` → `\b`, `U+0009` → `\t`, `U+000A` → `\n`, `U+000C` → `\f`,
  `U+000D` → `\r`
- Any other control character `U+0000`–`U+001F` → `\u00XX` (lowercase hex)
- Every other character (including `/`, and all non-ASCII) is emitted as its raw
  UTF-8 bytes — **not** `\u`-escaped.

Vector `ser-04-control-and-escapes` exercises this.

---

## 5. Hash function

**SHA-256** everywhere. 32-byte output. Displayed as lowercase hex; hashed/tree
operations use the raw 32 bytes.

**[RATIFY]** SHA-256 vs the Solana-ergonomic alternatives. Recommendation:
**SHA-256** — available as a cheap syscall in the Solana runtime, ubiquitous in
TS/Python, and the natural match for on-chain verification. Keccak-256 is the
other candidate (EVM-familiar) but offers no advantage here. Needs sign-off so
the on-chain program, engine, and both SDKs commit to one function.

---

## 6. Merkle trees

Binary Merkle tree over an **ordered** list of canonical leaf byte strings.

### 6.1 Node formulas (domain-separated by construction)

```
leaf_hash(i) = SHA-256( 0x00 || DOMAIN_TAG || canonical_leaf_bytes(i) )
node_hash    = SHA-256( 0x01 || left_hash || right_hash )
```

- The `0x00` / `0x01` prefixes make it impossible for a leaf preimage to be
  reinterpreted as an internal node (second-preimage protection).
- `DOMAIN_TAG` is a distinct ASCII byte string per tree type, so a leaf from one
  tree can never be replayed into another:
  - participant: `CRP:participant:v1`
  - assignment:  `CRP:assignment:v1`
  - evidence:    `CRP:evidence:v1`
  - reward:      `CRP:reward:v1`

### 6.2 Leaf ordering

Leaf order is **not** the producer's insertion order — it is a canonical sort key
derived from the leaf data, so two producers with the same set always build the
same tree. Per tree type:

- **assignment:** sort by `cohort_id` ascending (UTF-16 code-unit).
- participant / evidence / reward: **[RATIFY]** each needs its sort key pinned
  when those schemas land (recommendation: participant → participant id;
  reward → recipient/leaf id; evidence → batch sequence then record id).

### 6.3 Odd-node handling

If a level has an odd number of nodes, the unpaired trailing node is **promoted
unchanged** to the next level (it is **not** duplicated).

**[RATIFY]** Rationale: Bitcoin-style duplicate-the-last-node enables
CVE-2012-2459-class root collisions (distinct leaf sets → same root). Promotion
avoids that class. Alternative hardening is to prefix each leaf with the total
leaf count. Recommendation: **promotion**; needs sign-off since the on-chain
verifier must implement the identical rule.

### 6.4 Empty tree

Root of an empty tree = **32 zero bytes**. **[RATIFY]** (alternative:
`SHA-256(DOMAIN_TAG)`). Recommendation: 32 zero bytes for an unmistakable
"nothing committed" sentinel; needs sign-off.

---

## 7. Seed commitment & assignment derivation

Two distinct steps, reflecting freeze-before-reveal (invariant 1). The **manifest
freezes `seed_commitment(seed)`**; the seed is revealed later; verification then
(1) checks the commitment and (2) derives the assignment.

### 7.1 Seed

32-byte value. **[RATIFY]** length/type (recommendation: 32 bytes, surfaced as
64-char lowercase hex in the manifest/bundle).

### 7.2 Commitment

```
seed_commitment = SHA-256( "CRP-seed-commit-v1" || seed )       # domain is ASCII bytes
```

### 7.3 Per-cohort PRF (unambiguous, length-prefixed)

```
msg     = "CRP-assign-v1"
        || seed                                 (32 bytes)
        || u32be(len(experiment_id_utf8)) || experiment_id_utf8
        || u32be(len(cohort_id_utf8))     || cohort_id_utf8
prf_u64 = big-endian uint64 of SHA-256(msg)[0:8]
```

Length-prefixing the variable-length ids prevents any two `(experiment_id,
cohort_id)` pairs from colliding via naive concatenation.

**[RATIFY]** Domain-tag strings, the u32-BE length framing, and "first 8 bytes as
the PRF" all need sign-off (an on-chain reveal-check must reproduce them).

### 7.4 Designs

- **bernoulli** — params `{"treat_fraction_ppm": "<int>"}`: cohort is `treatment`
  iff `(prf_u64 mod 1_000_000) < treat_fraction_ppm`. Independent per cohort;
  expected — not exact — balance. Integer modulus only (no float).
- **fixed_count** — params `{"treatment_count": "<int>"}`: sort cohorts by
  `(prf_u64, cohort_id)` ascending; first `k` are `treatment`. Exact balance;
  `cohort_id` breaks prf ties.

**[RATIFY]** These two designs cover cluster-randomized (bernoulli) and
matched/balanced (fixed_count). Switchback and matched-cluster templates
(per CLAUDE.md) will need their own derivation rules pinned before M2; filed for
protocol-architect + causal-inference-engineer.

### 7.5 Assignment leaf

```
leaf_object = { "arm": <"treatment"|"control">, "cohort_id": <string> }
leaf_bytes  = canonical_json_bytes(leaf_object)
```

`prf_u64` is an auditable intermediate (published in the assignment table) but is
**not** part of the leaf preimage, since it is a deterministic function of
`(seed, experiment_id, cohort_id)`. **[RATIFY]** whether the leaf should also bind
`experiment_id` (recommendation: no — the assignment root is already committed
under a specific experiment on-chain; keeping the leaf minimal keeps on-chain
verification cheap).

---

## 8. Open items for protocol-architect (checklist)

- [ ] §1.2 UTF-16 key ordering + ASCII-only key constraint
- [ ] §2.2 per-field fixed-point scales + global rounding mode
- [ ] §2.3 numeric-string validation regexes
- [ ] §3 NFC as the normalization form
- [ ] §5 SHA-256 as the one hash function
- [ ] §6.2 leaf sort keys for participant/evidence/reward trees
- [ ] §6.3 promotion (vs duplication) for odd nodes
- [ ] §6.4 empty-tree root = 32 zero bytes
- [ ] §7 seed length, domain tags, PRF framing, design set, leaf fields

Once ratified into `specs/serialization.md`, this engineer will independently
reproduce the provisional manifest golden hash from the canonical-bytes level
(not from an assumed field layout) as the cross-check.
