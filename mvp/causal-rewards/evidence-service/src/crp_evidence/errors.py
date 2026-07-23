"""Typed hard errors with stable rejection codes.

Every rejection in the ingestion / root-building path raises ``EvidenceRejected`` carrying a
STABLE machine-readable ``code``. Codes are part of the wire contract: the golden vectors in
``test-vectors/`` (evidence-05, adv-02, adv-03) name them, the SDK surfaces them, and the
dashboard renders them. Adding a code is additive; renaming one is a breaking change.

Hard error vs finding
---------------------
* **Hard error (this module)** — the input is unusable; the batch/tree is REJECTED. Nothing
  downstream may proceed. Used for anything that would make two honest verifiers disagree
  (invariant 2) or that admits provably duplicated evidence.
* **Finding** (``anomalies.py``) — the input is admissible but suspicious (correlation /
  Sybil-replication / missingness signals). Findings are recorded in the audit bundle so a
  human or the challenge process can act on them; they never silently drop data.
"""

from __future__ import annotations

from typing import Any, Mapping

__all__ = ["RejectionCode", "EvidenceRejected"]


class RejectionCode:
    """Stable rejection code constants (string values are the wire contract)."""

    # --- structural / schema ---
    SCHEMA_INVALID = "SCHEMA_INVALID"
    UNSUPPORTED_SPEC_VERSION = "UNSUPPORTED_SPEC_VERSION"
    NON_CANONICAL_INTEGER_STRING = "NON_CANONICAL_INTEGER_STRING"
    TIME_RANGE_INVALID = "TIME_RANGE_INVALID"
    AGGREGATE_SUMMARY_INCONSISTENT = "AGGREGATE_SUMMARY_INCONSISTENT"

    # --- signature / identity (serialization.md §6.5) ---
    SIGNER_PUBKEY_NOT_32_BYTES = "SIGNER_PUBKEY_NOT_32_BYTES"
    SIGNER_PUBKEY_INVALID_BASE58 = "SIGNER_PUBKEY_INVALID_BASE58"
    BATCH_HEADER_HASH_MISMATCH = "BATCH_HEADER_HASH_MISMATCH"
    BATCH_SIGNATURE_INVALID = "BATCH_SIGNATURE_INVALID"
    UNSUPPORTED_SIGNATURE_ALGO = "UNSUPPORTED_SIGNATURE_ALGO"

    # --- anti-abuse at ingestion ---
    REPLAYED_BATCH = "REPLAYED_BATCH"
    DUPLICATE_EVENT_NONCE = "DUPLICATE_EVENT_NONCE"
    EXPERIMENT_ID_MISMATCH = "EXPERIMENT_ID_MISMATCH"
    EPOCH_INDEX_NOT_MONOTONIC = "EPOCH_INDEX_NOT_MONOTONIC"
    EPOCH_OUT_OF_SCHEDULE = "EPOCH_OUT_OF_SCHEDULE"

    # --- Merkle tree totality (serialization.md §6.5) ---
    DUPLICATE_EVIDENCE_LEAF = "DUPLICATE_EVIDENCE_LEAF"
    DUPLICATE_SIGNER_LEAF = "DUPLICATE_SIGNER_LEAF"
    DUPLICATE_OBSERVATION_LEAF = "DUPLICATE_OBSERVATION_LEAF"
    SUBTREE_ROOT_MISMATCH = "SUBTREE_ROOT_MISMATCH"
    LEAF_COUNT_MISMATCH = "LEAF_COUNT_MISMATCH"

    # --- bundle assembly ---
    BUNDLE_INCOMPLETE = "BUNDLE_INCOMPLETE"
    BUNDLE_CONTENT_ADDRESS_MISMATCH = "BUNDLE_CONTENT_ADDRESS_MISMATCH"
    DATA_MINIMIZATION_VIOLATION = "DATA_MINIMIZATION_VIOLATION"


class EvidenceRejected(ValueError):
    """A hard, typed rejection. ``code`` is stable; ``detail`` is human/diagnostic only."""

    def __init__(self, code: str, message: str, **detail: Any) -> None:
        super().__init__("[%s] %s" % (code, message))
        self.code = code
        self.message = message
        self.detail: Mapping[str, Any] = dict(detail)

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "detail": dict(self.detail)}
