"""Signed-telemetry ingestion: verify, normalize, deduplicate.

This is the trust boundary. Everything downstream (roots, bundle, chain) assumes a batch that
reached ``EvidenceLedger.accepted`` was (a) structurally valid, (b) hashed by US not by the
producer, (c) signed by the key it claims, and (d) not a replay.

Never trust a producer-supplied hash
------------------------------------
``batch_signature.header_hash_hex`` is an ASSERTION by the producer. The service recomputes

    header_hash = SHA-256( CJSON(batch \\ {"batch_signature"}) )

with the single ratified encoder and rejects on mismatch (``BATCH_HEADER_HASH_MISMATCH``)
BEFORE checking the signature. Order matters: verifying the signature first would let a
producer sign a hash of something other than the batch it submitted and still pass, so the
hash binding must be established first.

The ed25519 signature is verified over those 32 recomputed bytes (per the schema:
"The signature is over these 32 bytes"), using the base58 ``signer_pubkey`` decoded under the
§6.5 exactly-32-bytes pin.

Anti-abuse, three independent layers
------------------------------------
1. **Content hash** — ``SHA-256(CJSON(batch))`` over the WHOLE signed batch (signature
   included) is the batch's content address. Seeing it twice is a replay of a byte-identical
   signed batch (``REPLAYED_BATCH``): the ingestion-side analogue of the tree's
   ``DUPLICATE_EVIDENCE_LEAF``, caught earlier and with the producer named. It deliberately is
   NOT ``header_hash`` (body only) — two honest producers may sign the identical body for the
   same cell, and collapsing those would destroy corroboration.
2. **Event nonce** — ``(experiment_id, epoch_index, cohort_id, producer_pubkey)``. One producer
   gets ONE batch per cohort-epoch; a second, differently-signed batch for the same cell from
   the same producer is a double-report (``DUPLICATE_EVENT_NONCE``). The batch schema carries no
   dedicated nonce field, so the nonce is this natural key — see README "Event nonce" for why
   adding a nonce field to the frozen schema was rejected.
3. **Correlation checks** — cross-producer / cross-cell equality of committed roots
   (``anomalies.py``). These produce FINDINGS, not rejections.

Deduplication is NOT the tree's job
-----------------------------------
Two DIFFERENT producers reporting the same ``(experiment_id, epoch_index, cohort_id)`` are two
distinct event nonces: both are ADMITTED and both become distinct leaves (their signatures
differ ⇒ their CJSON differs ⇒ their leaf_hash differs). Independent corroboration of a cohort
is evidence. Only layers 1–2 above collapse duplicates, and they run here, at ingestion.

Determinism
-----------
No wall-clock, no RNG, no float. The ledger's accepted order is insertion order for
diagnostics only; every artifact it feeds is re-sorted by its canonical key first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

from . import _ref, ed25519
from .anomalies import Finding, correlation_findings
from .errors import EvidenceRejected, RejectionCode
from .roots import signer_pubkey_be32
from .validate import validate_batch

__all__ = [
    "AcceptedBatch",
    "RejectedBatch",
    "EvidenceLedger",
    "recompute_header_hash",
    "verify_batch_signature",
    "event_nonce",
]


def recompute_header_hash(batch: Mapping[str, Any]) -> bytes:
    """SHA-256 over ``CJSON(batch)`` with ``batch_signature`` REMOVED (the signed preimage)."""
    unsigned = {k: v for k, v in batch.items() if k != "batch_signature"}
    return _ref.sha256(_ref.canonical_json_bytes(unsigned))


def event_nonce(batch: Mapping[str, Any]) -> tuple[str, str, str, str]:
    """The ingestion event nonce: (experiment_id, epoch_index, cohort_id, producer_pubkey)."""
    return (
        batch["experiment_id"],
        batch["epoch_index"],
        batch["cohort_id"],
        batch["batch_signature"]["signer_pubkey"],
    )


def verify_batch_signature(batch: Mapping[str, Any]) -> bytes:
    """Recompute the header hash, enforce the producer's claim, verify the signature.

    Returns the 32 recomputed header-hash bytes. Raises ``EvidenceRejected`` otherwise.
    """
    sig = batch["batch_signature"]
    if sig["algo"] != "ed25519":
        raise EvidenceRejected(
            RejectionCode.UNSUPPORTED_SIGNATURE_ALGO,
            "unsupported batch_signature.algo: %r" % (sig["algo"],),
        )

    recomputed = recompute_header_hash(batch)
    declared = sig["header_hash_hex"]
    if recomputed.hex() != declared:
        raise EvidenceRejected(
            RejectionCode.BATCH_HEADER_HASH_MISMATCH,
            "producer-supplied header_hash_hex %s != recomputed %s "
            "(the producer hash is never trusted)" % (declared, recomputed.hex()),
            declared=declared,
            recomputed=recomputed.hex(),
        )

    pubkey = signer_pubkey_be32(sig["signer_pubkey"])  # §6.5 exactly-32-bytes pin
    signature = bytes.fromhex(sig["signature_hex"])
    if not ed25519.verify(pubkey, recomputed, signature):
        raise EvidenceRejected(
            RejectionCode.BATCH_SIGNATURE_INVALID,
            "ed25519 batch signature does not verify over the recomputed header hash",
            signer_pubkey=sig["signer_pubkey"],
            header_hash_hex=recomputed.hex(),
        )
    return recomputed


@dataclass(frozen=True)
class AcceptedBatch:
    """A batch that cleared the trust boundary. ``batch`` is the normalized header."""

    batch: Mapping[str, Any]
    #: SHA-256(CJSON(batch MINUS batch_signature)) — the signed preimage, recomputed by us.
    header_hash_hex: str
    #: SHA-256(CJSON(batch INCLUDING batch_signature)) — CAS address + replay key.
    batch_object_sha256: str
    leaf_hash_hex: str
    canonical_bytes_len: int

    @property
    def epoch_index(self) -> str:
        return str(self.batch["epoch_index"])

    @property
    def cohort_id(self) -> str:
        return str(self.batch["cohort_id"])

    @property
    def producer_pubkey(self) -> str:
        return str(self.batch["batch_signature"]["signer_pubkey"])


@dataclass(frozen=True)
class RejectedBatch:
    """A rejected submission, retained for the audit trail (never for the tree)."""

    code: str
    message: str
    detail: Mapping[str, Any]
    submission_index: int


@dataclass
class EvidenceLedger:
    """Stateful ingestion ledger for ONE experiment.

    ``verify_signatures=False`` exists for one purpose: replaying the ratified golden vectors
    (``test-vectors/evidence/``), whose batch headers carry PLACEHOLDER signature bytes
    (``aaaa…``) because they were authored to pin TREE bytes, not signature bytes. The tree
    is a pure function of ``CJSON(batch)`` and does not care whether the signature verifies,
    so root reproduction and signature policy are cleanly separable. It MUST be left True on
    any real ingestion path; the bundle records the flag in ``provenance.json`` so a bundle
    built with verification off is self-evident.
    """

    experiment_id: str
    verify_signatures: bool = True
    accepted: list[AcceptedBatch] = field(default_factory=list)
    rejected: list[RejectedBatch] = field(default_factory=list)
    unverified_header_hash_mismatches: list[str] = field(default_factory=list)
    _seen_content: dict[str, int] = field(default_factory=dict, repr=False)
    _seen_nonce: dict[tuple[str, str, str, str], int] = field(default_factory=dict, repr=False)
    _submissions: int = field(default=0, repr=False)

    # -- core ------------------------------------------------------------------

    def ingest(self, batch: Mapping[str, Any]) -> AcceptedBatch:
        """Validate → verify → deduplicate → admit. Raises ``EvidenceRejected`` on failure."""
        idx = self._submissions
        self._submissions += 1
        try:
            return self._ingest_inner(batch, idx)
        except EvidenceRejected as exc:
            self.rejected.append(
                RejectedBatch(exc.code, exc.message, dict(exc.detail), idx)
            )
            raise

    def _ingest_inner(self, batch: Mapping[str, Any], idx: int) -> AcceptedBatch:
        validated = validate_batch(batch, expected_experiment_id=self.experiment_id)

        if self.verify_signatures:
            header_hash = verify_batch_signature(validated)
        else:
            header_hash = recompute_header_hash(validated)
            declared = validated["batch_signature"]["header_hash_hex"]
            if header_hash.hex() != declared:
                # Golden fixtures legitimately carry placeholder hashes, so this cannot be a
                # hard error on this path — but it must never pass silently. It is counted
                # and published in provenance.json next to the verify_signatures=false flag.
                self.unverified_header_hash_mismatches.append(header_hash.hex())
            # §6.5 length pin still applies — it governs ORDERING, not signatures.
            signer_pubkey_be32(validated["batch_signature"]["signer_pubkey"])

        # Content address of the WHOLE signed batch — CJSON INCLUDING batch_signature. It must
        # NOT be `header_hash` (which covers the body only): two honest producers can sign the
        # identical body for the same cell, and that is corroboration, not a replay. Including
        # the signature makes the content key exactly "this signed artifact", which is also the
        # CAS object address and the evidence leaf preimage — one address, three uses.
        cb = _ref.canonical_json_bytes(validated)
        content_key = _ref.sha256_hex(cb)
        if content_key in self._seen_content:
            raise EvidenceRejected(
                RejectionCode.REPLAYED_BATCH,
                "this exact signed batch was already ingested (replay of submission #%d): "
                "batch_object_sha256=%s" % (self._seen_content[content_key], content_key),
                batch_object_sha256=content_key,
                header_hash_hex=header_hash.hex(),
                first_submission_index=self._seen_content[content_key],
            )

        nonce = event_nonce(validated)
        if nonce in self._seen_nonce:
            raise EvidenceRejected(
                RejectionCode.DUPLICATE_EVENT_NONCE,
                "producer %s already reported cohort %r in epoch %s (submission #%d); one "
                "batch per producer per cohort-epoch"
                % (nonce[3], nonce[2], nonce[1], self._seen_nonce[nonce]),
                event_nonce=list(nonce),
                first_submission_index=self._seen_nonce[nonce],
            )

        leaf = _ref.sha256(_ref.merkle.LEAF_PREFIX + _ref.merkle.DOMAIN_EVIDENCE + cb)

        accepted = AcceptedBatch(
            batch=validated,
            header_hash_hex=header_hash.hex(),
            batch_object_sha256=content_key,
            leaf_hash_hex=leaf.hex(),
            canonical_bytes_len=len(cb),
        )
        self._seen_content[content_key] = idx
        self._seen_nonce[nonce] = idx
        self.accepted.append(accepted)
        return accepted

    def ingest_many(
        self, batches: Iterable[Mapping[str, Any]], *, strict: bool = True
    ) -> list[AcceptedBatch]:
        """Ingest a stream. ``strict=False`` records rejections and continues.

        ``strict=False`` is for bulk operational ingest where one malformed submission must
        not stall an epoch; the rejection list is published in the bundle, so dropping a batch
        is never invisible.
        """
        out: list[AcceptedBatch] = []
        for b in batches:
            try:
                out.append(self.ingest(b))
            except EvidenceRejected:
                if strict:
                    raise
        return out

    # -- views -----------------------------------------------------------------

    def epochs(self) -> list[str]:
        """Distinct epoch indices present, ordered NUMERICALLY (not as strings)."""
        return [str(e) for e in sorted({int(a.epoch_index) for a in self.accepted})]

    def batches_for_epoch(self, epoch_index: str | int) -> list[Mapping[str, Any]]:
        want = str(int(epoch_index))
        return [a.batch for a in self.accepted if str(int(a.epoch_index)) == want]

    def findings(self) -> list[Finding]:
        return correlation_findings([a.batch for a in self.accepted])

    def rejection_records(self) -> list[dict[str, Any]]:
        return [
            {
                "submission_index": str(r.submission_index),
                "code": r.code,
                "message": r.message,
            }
            for r in sorted(self.rejected, key=lambda r: r.submission_index)
        ]


def ingest_all(
    experiment_id: str,
    batches: Sequence[Mapping[str, Any]],
    *,
    verify_signatures: bool = True,
    strict: bool = True,
) -> EvidenceLedger:
    """Convenience: build a ledger and ingest a whole submission list."""
    ledger = EvidenceLedger(experiment_id=experiment_id, verify_signatures=verify_signatures)
    ledger.ingest_many(batches, strict=strict)
    return ledger
