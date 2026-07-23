"""crp_evidence — off-chain evidence pipeline and audit-bundle assembler (M3).

Pipeline shape::

    signed batches -> ingest.EvidenceLedger -> roots.* -> bundle.assemble_bundle
                        (verify/dedup)         (Merkle)     (content-addressed artifact)

Every hash and every ordering decision comes from ``verifier-cli/reference/`` (the ratified
conformance oracle) via ``_ref``; this package never defines a second encoder.
"""

from __future__ import annotations

from .bundle import BUNDLE_LAYOUT_VERSION, BundleResult, assemble_bundle, verify_bundle
from .cas import ContentAddressedStore
from .errors import EvidenceRejected, RejectionCode
from .ingest import EvidenceLedger, ingest_all, recompute_header_hash, verify_batch_signature
from .parquet_writer import PARQUET_WRITER_SETTINGS, Table, write_table
from .provenance import BuildContext
from .roots import (
    assignment_root,
    evidence_epoch_root,
    observations_root,
    participant_root,
    signer_set_root,
)
from .schedule import evaluate_coverage, schedule_from_manifest

__all__ = [
    "BUNDLE_LAYOUT_VERSION",
    "BuildContext",
    "BundleResult",
    "ContentAddressedStore",
    "EvidenceLedger",
    "EvidenceRejected",
    "PARQUET_WRITER_SETTINGS",
    "RejectionCode",
    "Table",
    "assemble_bundle",
    "assignment_root",
    "evaluate_coverage",
    "evidence_epoch_root",
    "ingest_all",
    "observations_root",
    "participant_root",
    "recompute_header_hash",
    "schedule_from_manifest",
    "signer_set_root",
    "verify_batch_signature",
    "verify_bundle",
    "write_table",
]

__version__ = "0.1.0a0"
