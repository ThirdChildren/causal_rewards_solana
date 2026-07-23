"""Merkle root construction — participant / assignment / evidence.

Every root here is produced by the RATIFIED reference implementation in
``verifier-cli/reference/`` (imported through ``_ref``), never by a second encoder. This
module adds exactly three things on top of the reference:

1. **Typed rejection codes.** The reference raises plain ``ValueError``; the service must
   emit the stable codes named by the golden vectors (``SIGNER_PUBKEY_NOT_32_BYTES``,
   ``DUPLICATE_EVIDENCE_LEAF``, …). Duplicate detection is therefore performed here, with a
   code, *before* delegating to the reference (which would also catch it, uncoded).
2. **Ordered leaf tables**, so the audit bundle's Parquet rows can be written in exactly the
   canonical leaf-sort order (byte-stability, see ``parquet_writer.py``).
3. **Cross-checks** of producer-supplied sub-commitment roots against recomputed ones.

Ordering, leaf preimages, node formulas, promotion and the empty-tree sentinel all come from
``specs/serialization.md`` §6.1–§6.5 via the reference. Nothing is re-derived here.

DEDUPLICATION SEMANTICS (normative for this service — read before "fixing" anything)
-----------------------------------------------------------------------------------
The evidence epoch tree does **NOT** deduplicate by semantic identity. Two batches sharing
``(experiment_id, epoch_index, cohort_id)`` but produced by two different collectors are two
DISTINCT leaves and BOTH are admitted: their ``batch_signature`` differs, so their
``CJSON(batch)`` differs, so their ``leaf_hash`` differs, so the strict-monotonicity check
passes. This is deliberate — independent corroboration of the same cohort-epoch is evidence,
not duplication, and the tree must commit whatever was actually anchored.

The only thing the tree rejects is a BYTE-IDENTICAL leaf (same ``leaf_hash``), i.e. the same
signed batch replayed into one epoch (``DUPLICATE_EVIDENCE_LEAF``, adv-03).

Real deduplication — replay, double-reporting, Sybil replication — is enforced at INGESTION
(``ingest.py``): event nonce ``(experiment_id, epoch_index, cohort_id, producer_pubkey)``,
content hash (``header_hash_hex``), and cross-producer correlation checks. Catching it there
and not in the tree is what lets the tree stay a pure, order-total commitment function.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from . import _ref
from .errors import EvidenceRejected, RejectionCode

__all__ = [
    "PARTICIPANT_LEAF_STATUS",
    "EMPTY_ROOT_HEX",
    "signer_pubkey_be32",
    "signer_set_root",
    "observations_root",
    "evidence_epoch_root",
    "assignment_root",
    "participant_root",
    "verify_batch_subcommitments",
    "EvidenceEpochRoots",
]

EMPTY_ROOT_HEX = "00" * 32

# serialization.md §6.2 leaves the PARTICIPANT sort key unpinned ("recommendation of record:
# participant id ascending, UTF-16 code-unit of the NFC-normalized id"). This service
# implements exactly that recommendation and labels every participant root PROVISIONAL until
# protocol-architect pins §6.2. See README.md "Open spec items".
PARTICIPANT_LEAF_STATUS = "PROVISIONAL-UNPINNED-6.2"


# ---------------------------------------------------------------- signer / observation keys


def signer_pubkey_be32(signer_pubkey: str) -> bytes:
    """Base58-decode a ``signer_pubkey`` to EXACTLY 32 bytes (§6.5 length pin) or hard-error.

    The schema regex ``^[1-9A-HJ-NP-Za-km-z]{32,44}$`` constrains CHARACTERS, not decoded
    length: a 44-character base58 string can decode to 31, 32 or 33 bytes. A non-32-byte key
    would break the fixed-width ``sol_memcmp`` sort premise and diverge on-chain vs off-chain,
    so it is rejected before ordering (golden vector evidence-05).
    """
    try:
        raw = _ref.evidence.b58decode(signer_pubkey)
    except ValueError as exc:
        raise EvidenceRejected(
            RejectionCode.SIGNER_PUBKEY_INVALID_BASE58,
            "signer_pubkey is not valid Bitcoin/Solana base58: %s" % (exc,),
            signer_pubkey=signer_pubkey,
        ) from exc
    if len(raw) != 32:
        raise EvidenceRejected(
            RejectionCode.SIGNER_PUBKEY_NOT_32_BYTES,
            "signer_pubkey MUST base58-decode to exactly 32 bytes, got %d" % len(raw),
            signer_pubkey=signer_pubkey,
            decoded_length=len(raw),
        )
    return raw


def _check_strictly_increasing(keys: Sequence[bytes], code: str, what: str) -> None:
    ordered = sorted(keys)
    for a, b in zip(ordered, ordered[1:]):
        if a == b:
            raise EvidenceRejected(
                code,
                "duplicate %s leaf (leaf order must be strictly increasing): %s" % (what, a.hex()),
                sort_key_hex=a.hex(),
            )


# ---------------------------------------------------------------------- sub-commitments


def signer_set_root(signer_pubkeys_b58: Sequence[str]) -> tuple[str, list[dict[str, Any]]]:
    """Signer-set sub-commitment root (leaf domain ``signer``). Returns (root_hex, leaves)."""
    keys = [signer_pubkey_be32(pk) for pk in signer_pubkeys_b58]
    _check_strictly_increasing(keys, RejectionCode.DUPLICATE_SIGNER_LEAF, "signer")
    root, records = _ref.evidence.signer_subtree(list(signer_pubkeys_b58))
    by_key = {signer_pubkey_be32(pk): pk for pk in signer_pubkeys_b58}
    for rec in records:
        rec["signer_pubkey"] = by_key[bytes.fromhex(rec["sort_key_be32_hex"])]
    return root.hex(), records


def observations_root(payload_commitment_hexes: Sequence[str]) -> tuple[str, list[dict[str, Any]]]:
    """Observation sub-commitment root (leaf domain ``obs``). Returns (root_hex, leaves)."""
    keys: list[bytes] = []
    for h in payload_commitment_hexes:
        if len(h) != 64:
            raise EvidenceRejected(
                RejectionCode.SCHEMA_INVALID,
                "payload_commitment_hex must be 64 lowercase hex chars, got %d" % len(h),
                value=h,
            )
        try:
            keys.append(bytes.fromhex(h))
        except ValueError as exc:
            raise EvidenceRejected(
                RejectionCode.SCHEMA_INVALID, "payload_commitment_hex is not hex: %r" % (h,)
            ) from exc
    _check_strictly_increasing(keys, RejectionCode.DUPLICATE_OBSERVATION_LEAF, "observation")
    root, records = _ref.evidence.observation_subtree(list(payload_commitment_hexes))
    return root.hex(), records


# --------------------------------------------------------------------- evidence epoch tree


@dataclass(frozen=True)
class EvidenceEpochRoots:
    """Result of building one epoch's evidence commitment set.

    ``epoch_root_hex`` is the §6.5 tree-1 root over the epoch's signed batch headers.

    ``per_batch_signer_root_hex`` / ``per_batch_observations_root_hex`` are the sub-roots
    carried INSIDE each batch header, in canonical leaf order. NOTE (flagged, not decided
    here): the on-chain ``EvidenceEpoch`` account has SINGULAR ``signer_set_root`` and
    ``observations_root`` fields, so a multi-batch epoch needs a mapping from these per-batch
    sub-roots to those singular fields. That mapping is owned by protocol-architect +
    solana-program-engineer and is deliberately NOT invented here — this service publishes
    the full per-batch lists (and the epoch root, which already binds them transitively) so
    whichever mapping is ratified can be computed from the bundle without re-ingesting.
    """

    epoch_index: str
    epoch_root_hex: str
    batch_count: int
    ordered_leaves: tuple[Mapping[str, Any], ...]
    per_batch_signer_root_hex: tuple[str, ...]
    per_batch_observations_root_hex: tuple[str, ...]


def evidence_epoch_root(batches: Sequence[Mapping[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Evidence epoch root over signed batch headers (DOMAIN ``CRP:evidence:v1``).

    Leaf = ``CJSON(batch)`` INCLUDING ``batch_signature``; sort key = ``leaf_hash`` ascending.
    Empty batch list → ``EMPTY_ROOT_HEX`` (§6.4) — the "no batches anchored this epoch"
    sentinel the missingness policy consumes (``schedule.py``).
    """
    leaf_hashes: list[bytes] = []
    for batch in batches:
        cb = _ref.canonical_json_bytes(batch)
        leaf_hashes.append(
            _ref.sha256(_ref.merkle.LEAF_PREFIX + _ref.merkle.DOMAIN_EVIDENCE + cb)
        )
    _check_strictly_increasing(leaf_hashes, RejectionCode.DUPLICATE_EVIDENCE_LEAF, "evidence batch")

    root, records = _ref.evidence.epoch_tree(list(batches))

    # Attach the semantic fields for the bundle's evidence table, keyed by leaf_hash so the
    # attachment cannot reorder anything.
    by_hash: dict[str, Mapping[str, Any]] = {}
    for batch, lh in zip(batches, leaf_hashes):
        by_hash[lh.hex()] = batch
    for rec in records:
        b = by_hash[rec["leaf_hash_hex"]]
        rec["experiment_id"] = b["experiment_id"]
        rec["epoch_index"] = b["epoch_index"]
        rec["cohort_id"] = b["cohort_id"]
        rec["time_range_start"] = b["time_range"]["start"]
        rec["time_range_end"] = b["time_range"]["end"]
        rec["signer_set_root_hex"] = b["signer_set_commitment"]["merkle_root_hex"]
        rec["signer_count"] = b["signer_set_commitment"]["signer_count"]
        rec["observations_root_hex"] = b["observations_commitment"]["merkle_root_hex"]
        rec["observation_leaf_count"] = b["observations_commitment"]["leaf_count"]
        rec["accepted_count"] = b["aggregate_summary"]["accepted_count"]
        rec["rejected_count"] = b["aggregate_summary"]["rejected_count"]
        rec["distinct_signers"] = b["aggregate_summary"]["distinct_signers"]
        rec["quality_score_micro_sum"] = b["aggregate_summary"].get("quality_score_micro_sum", "0")
        rec["producer_pubkey"] = b["batch_signature"]["signer_pubkey"]
        rec["header_hash_hex"] = b["batch_signature"]["header_hash_hex"]
        rec["batch_signature_hex"] = b["batch_signature"]["signature_hex"]
    return root.hex(), records


def verify_batch_subcommitments(
    batch: Mapping[str, Any],
    *,
    signer_pubkeys_b58: Sequence[str] | None = None,
    payload_commitment_hexes: Sequence[str] | None = None,
) -> None:
    """Recompute a batch's sub-commitment roots from their member sets and cross-check.

    Optional because a coordinator can anchor a batch whose off-chain member sets it does not
    hold. When the member sets ARE available (the normal pilot path), the producer-supplied
    root is NEVER trusted: it is recomputed and compared, and ``leaf_count`` / ``signer_count``
    must match the actual member-set size.
    """
    if signer_pubkeys_b58 is not None:
        root_hex, _ = signer_set_root(signer_pubkeys_b58)
        declared = batch["signer_set_commitment"]["merkle_root_hex"]
        if root_hex != declared:
            raise EvidenceRejected(
                RejectionCode.SUBTREE_ROOT_MISMATCH,
                "recomputed signer_set root %s != declared %s" % (root_hex, declared),
                recomputed=root_hex,
                declared=declared,
            )
        declared_n = batch["signer_set_commitment"]["signer_count"]
        if str(len(signer_pubkeys_b58)) != declared_n:
            raise EvidenceRejected(
                RejectionCode.LEAF_COUNT_MISMATCH,
                "signer_count %s != actual signer set size %d" % (declared_n, len(signer_pubkeys_b58)),
            )
    if payload_commitment_hexes is not None:
        root_hex, _ = observations_root(payload_commitment_hexes)
        declared = batch["observations_commitment"]["merkle_root_hex"]
        if root_hex != declared:
            raise EvidenceRejected(
                RejectionCode.SUBTREE_ROOT_MISMATCH,
                "recomputed observations root %s != declared %s" % (root_hex, declared),
                recomputed=root_hex,
                declared=declared,
            )
        declared_n = batch["observations_commitment"]["leaf_count"]
        if str(len(payload_commitment_hexes)) != declared_n:
            raise EvidenceRejected(
                RejectionCode.LEAF_COUNT_MISMATCH,
                "leaf_count %s != actual observation set size %d"
                % (declared_n, len(payload_commitment_hexes)),
            )


# ------------------------------------------------------------------ assignment / participant


def assignment_root(
    assignments: Iterable[Any],
) -> tuple[str, list[dict[str, Any]]]:
    """Assignment root over ``CohortAssignment`` records from the reference derivation.

    Leaf = ``CJSON({"arm": …, "cohort_id": …})`` (§7.5); order = ``cohort_id`` ascending by
    UTF-16 code unit (§6.2). ``derive_assignment`` already returns that order; it is
    re-applied here so the function is correct for any input order.
    """
    items = list(assignments)
    ordered = sorted(items, key=lambda a: a.cohort_id.encode("utf-16-be"))
    seen: set[str] = set()
    for a in ordered:
        if a.cohort_id in seen:
            raise EvidenceRejected(
                RejectionCode.SCHEMA_INVALID,
                "duplicate cohort_id in assignment set: %r" % (a.cohort_id,),
            )
        seen.add(a.cohort_id)
    leaves = [_ref.assignment.assignment_leaf_bytes(a) for a in ordered]
    root = _ref.merkle.merkle_root(leaves, _ref.merkle.DOMAIN_ASSIGNMENT)
    records = [
        {
            "position": i,
            "cohort_id": a.cohort_id,
            "arm": a.arm,
            "prf_u64": str(a.prf_u64),
            "leaf_hash_hex": _ref.merkle.leaf_hash(
                _ref.merkle.DOMAIN_ASSIGNMENT, leaves[i]
            ).hex(),
        }
        for i, a in enumerate(ordered)
    ]
    return root.hex(), records


def participant_root(
    participants: Sequence[Mapping[str, Any]],
) -> tuple[str, list[dict[str, Any]]]:
    """PROVISIONAL participant root (§6.2 sort key not yet pinned — see PARTICIPANT_LEAF_STATUS).

    Implements the spec's "recommendation of record": leaf order = ``participant_id``
    ascending by UTF-16 code unit of the NFC-normalized id. Leaf preimage (also provisional):

        leaf_object = {"cohort_id": <string>, "participant_id": <string>}
        leaf_bytes  = CJSON(leaf_object)          # domain CRP:participant:v1

    Mirrors §7.5's minimalism: the leaf binds the membership decision (who is in the
    experiment and in which cohort) and nothing else. Any reward-weight input stays in
    ``participants.parquet`` as an auditable column, not in the leaf.

    Until §6.2 pins this, ``roots.json`` labels the value with ``PARTICIPANT_LEAF_STATUS`` and
    a bundle carrying it is NOT claimed to be on-chain-verifiable for the participant root.
    """
    import unicodedata

    ordered = sorted(
        participants,
        key=lambda p: unicodedata.normalize("NFC", str(p["participant_id"])).encode("utf-16-be"),
    )
    seen: set[str] = set()
    leaves: list[bytes] = []
    records: list[dict[str, Any]] = []
    for i, p in enumerate(ordered):
        pid = unicodedata.normalize("NFC", str(p["participant_id"]))
        if pid in seen:
            raise EvidenceRejected(
                RejectionCode.SCHEMA_INVALID,
                "duplicate participant_id in participant set: %r" % (pid,),
            )
        seen.add(pid)
        leaf_obj = {"cohort_id": str(p["cohort_id"]), "participant_id": pid}
        lb = _ref.canonical_json_bytes(leaf_obj)
        leaves.append(lb)
        records.append(
            {
                "position": i,
                "participant_id": pid,
                "cohort_id": str(p["cohort_id"]),
                "leaf_hash_hex": _ref.merkle.leaf_hash(
                    _ref.merkle.DOMAIN_PARTICIPANT, lb
                ).hex(),
            }
        )
    root = _ref.merkle.merkle_root(leaves, _ref.merkle.DOMAIN_PARTICIPANT)
    return root.hex(), records
