"""Evidence Merkle trees reference implementation (serialization.md §6.5, RATIFIED v1.1).

Three §6.1-shaped trees, all using the §6.1 node formulas (0x00/0x01 prefixes, odd-node
promotion §6.3, 32-zero-byte empty root §6.4). Each has a fixed leaf preimage and a data-derived
TOTAL order (strict monotonicity ⇒ duplicates are a hard error). These are the OFF-CHAIN source
of truth; the singular on-chain EvidenceEpoch account-field mapping is a separate flagged item and
is NOT reconciled here.

  1. Evidence epoch tree — DOMAIN_TAG "CRP:evidence:v1".
     leaf preimage = CJSON(batch) (the full batch header, INCLUDING batch_signature).
     leaf_hash     = SHA-256( 0x00 || "CRP:evidence:v1" || CJSON(batch) ).
     SORT KEY: leaf_hash ascending. Byte-identical batch leaves collide on leaf_hash → hard error.

  2. Observation sub-commitment — leaf domain "obs" (root = observations_commitment.merkle_root_hex).
     observation_commitment_be32 = 32 raw bytes from payload_commitment_hex (^[0-9a-f]{64}$).
     leaf_hash = SHA-256( 0x00 || "obs" || observation_commitment_be32 ).
     SORT KEY: observation_commitment_be32 ascending. Duplicate commitment → hard error.

  3. Signer set sub-commitment — leaf domain "signer" (root = signer_set_commitment.merkle_root_hex).
     signer_pubkey_be32 = 32 raw bytes base58-decoded from signer_pubkey (Bitcoin/Solana alphabet).
     The decode MUST be EXACTLY 32 bytes; any other length is a HARD ERROR (§6.5 length pin).
     leaf_hash = SHA-256( 0x00 || "signer" || signer_pubkey_be32 ).
     SORT KEY: signer_pubkey_be32 ascending. Duplicate pubkey → hard error.

Common ordering rule (§6.5): ascending unsigned big-endian byte comparison over the tree's
fixed-width 32-byte sort key (matches sol_memcmp on-chain). No field parsing, no NFC, no
numeric-string comparison. Dependency-free (stdlib only); base58 is implemented locally.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

from canonical import canonical_json_bytes, sha256
from merkle import DOMAIN_EVIDENCE, LEAF_PREFIX, leaf_hash, merkle_root

__all__ = [
    "BASE58_ALPHABET",
    "DOMAIN_OBS",
    "DOMAIN_SIGNER",
    "b58decode",
    "b58encode",
    "signer_pubkey_be32",
    "epoch_tree",
    "observation_subtree",
    "signer_subtree",
]

# Bitcoin/Solana base58 alphabet (schema regex ^[1-9A-HJ-NP-Za-km-z]{32,44}$).
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_B58_INDEX = {c: i for i, c in enumerate(BASE58_ALPHABET)}

# Sub-commitment leaf domains (ASCII), inside the 0x00 leaf preimage (§6.1/§6.5 table).
DOMAIN_OBS = b"obs"
DOMAIN_SIGNER = b"signer"


def b58decode(s: str) -> bytes:
    """Decode a Bitcoin/Solana base58 string to raw bytes (no length assertion here)."""
    num = 0
    for ch in s:
        idx = _B58_INDEX.get(ch)
        if idx is None:
            raise ValueError("invalid base58 character: %r" % (ch,))
        num = num * 58 + idx
    body = num.to_bytes((num.bit_length() + 7) // 8, "big") if num > 0 else b""
    n_leading_ones = len(s) - len(s.lstrip("1"))
    return b"\x00" * n_leading_ones + body


def b58encode(b: bytes) -> str:
    """Encode raw bytes to a Bitcoin/Solana base58 string (fixture helper; inverse of b58decode)."""
    num = int.from_bytes(b, "big")
    out = ""
    while num > 0:
        num, rem = divmod(num, 58)
        out = BASE58_ALPHABET[rem] + out
    n_leading_zero = len(b) - len(b.lstrip(b"\x00"))
    return "1" * n_leading_zero + out


def signer_pubkey_be32(signer_pubkey: str) -> bytes:
    """Base58-decode a signer_pubkey and enforce the §6.5 EXACTLY-32-byte length pin (hard error)."""
    raw = b58decode(signer_pubkey)
    if len(raw) != 32:
        raise ValueError(
            "signer_pubkey MUST base58-decode to exactly 32 bytes, got %d: %r"
            % (len(raw), signer_pubkey)
        )
    return raw


def _sorted_subtree(
    keys: Sequence[bytes], domain: bytes
) -> Tuple[bytes, List[dict]]:
    """Build a sub-commitment tree over 32-byte keys, sorted ascending, strict monotonicity.

    Returns (root, ordered_leaf_records). Duplicate key → hard error (strict order totality).
    """
    for k in keys:
        if len(k) != 32:
            raise ValueError("sub-commitment key must be 32 bytes, got %d" % len(k))
    ordered = sorted(keys)
    for a, b in zip(ordered, ordered[1:]):
        if a == b:
            raise ValueError(
                "duplicate sub-commitment leaf (not strictly increasing): %s" % a.hex()
            )
    records = []
    for pos, k in enumerate(ordered):
        records.append(
            {
                "position": pos,
                "sort_key_be32_hex": k.hex(),
                "leaf_hash_hex": leaf_hash(domain, k).hex(),
            }
        )
    root = merkle_root(list(ordered), domain)
    return root, records


def observation_subtree(payload_commitment_hexes: Sequence[str]) -> Tuple[bytes, List[dict]]:
    """Observation sub-commitment root over per-observation content commitments (leaf domain 'obs')."""
    keys = []
    for h in payload_commitment_hexes:
        if len(h) != 64:
            raise ValueError("payload_commitment_hex must be 64 hex chars, got %d" % len(h))
        keys.append(bytes.fromhex(h))
    return _sorted_subtree(keys, DOMAIN_OBS)


def signer_subtree(signer_pubkeys_b58: Sequence[str]) -> Tuple[bytes, List[dict]]:
    """Signer-set sub-commitment root over 32-byte signer pubkeys (leaf domain 'signer').

    Each signer_pubkey MUST base58-decode to exactly 32 bytes (§6.5 length pin) else hard error.
    """
    keys = [signer_pubkey_be32(pk) for pk in signer_pubkeys_b58]
    return _sorted_subtree(keys, DOMAIN_SIGNER)


def epoch_tree(batches: Sequence[dict]) -> Tuple[bytes, List[dict]]:
    """Evidence epoch tree over signed batch headers (DOMAIN 'CRP:evidence:v1').

    Leaf = CJSON(batch) (whole header incl. batch_signature). Sort by leaf_hash ascending; a
    byte-identical batch appearing twice collides on leaf_hash → hard error (strict totality).
    Returns (root, ordered_leaf_records) with the CJSON bytes and leaf_hash of each batch.
    """
    entries = []
    for batch in batches:
        cb = canonical_json_bytes(batch)
        lh = sha256(LEAF_PREFIX + DOMAIN_EVIDENCE + cb)
        entries.append((lh, cb))
    entries.sort(key=lambda e: e[0])
    for a, b in zip(entries, entries[1:]):
        if a[0] == b[0]:
            raise ValueError(
                "duplicate evidence batch leaf (not strictly increasing leaf_hash): %s"
                % a[0].hex()
            )
    records = []
    for pos, (lh, cb) in enumerate(entries):
        records.append(
            {
                "position": pos,
                "leaf_canonical_bytes_len": str(len(cb)),
                "leaf_hash_hex": lh.hex(),
            }
        )
    root = merkle_root([cb for _lh, cb in entries], DOMAIN_EVIDENCE)
    return root, records
