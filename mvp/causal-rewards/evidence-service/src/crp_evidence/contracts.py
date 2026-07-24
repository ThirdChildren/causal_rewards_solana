"""Interface contract for the artifacts OWNED BY ``causal-inference-engineer``.

This service owns the bundle skeleton, the evidence/participant/assignment tables, the roots
and the provenance. It does **not** produce ``analysis.json`` or ``rewards.parquet`` — those
come from the causal engine / reward compiler. This module is the written-down contract for
where they go, what they are called, and what shape the assembler will accept, so the two
sides can be built in parallel and integrate without a negotiation round.

The assembler VALIDATES against this contract and refuses to seal a bundle whose analysis or
rewards artifact does not conform. It never repairs or reformats them: if the causal engine
emits a different shape, the contract is renegotiated in the spec, not patched in the sealer.

--------------------------------------------------------------------------------
``analysis.json`` — bundle root, exact filename, produced by causal-inference-engineer
--------------------------------------------------------------------------------
Canonical-JSON bytes (serialization.md §3/§4) written with the SAME encoder
(``verifier-cli/reference/canonical.py``). Therefore: **no JSON number tokens** — every
numeric value is a canonical integer-scaled decimal STRING (§2).

The engine's richer schema (``crp_engine.artifacts.build_analysis``) is normative for the
file's content. The assembler validates only the seam it depends on — it does not force the
engine into a second, redundant ``result{…_micro}`` block. Required top-level keys the
assembler enforces:

    spec_version                 "1.1.0"
    experiment_id                must equal manifest.experiment_id
    evidence_epoch_roots         [ "<64-hex>", ... ] in ASCENDING epoch order — the exact
                                 roots this analysis consumed; the assembler cross-checks
                                 them against the roots it built (mismatch = hard error,
                                 this is the freeze-before-reveal link between evidence and
                                 result)
    primary_estimate             the top-level primary result object (effect / SE / margin /
                                 conservative improvement, all scaled integer strings)
    reward_summary               budget / allocation / reward_root_hex summary
    cohorts                      [ per-cohort estimate objects ]

If the object carries ``engine.analysis_container_digest`` and the frozen manifest declares
one, the assembler additionally requires they agree (freeze binding).

``result_artifact_hash`` (what ``submit_evaluation`` anchors) = SHA-256 of the CJSON bytes of
this object = the ``sha256`` the assembler records for ``analysis.json``. The causal engine
does NOT put that hash inside the file (it would be self-referential).

--------------------------------------------------------------------------------
``rewards.parquet`` — bundle root, exact filename, produced by causal-inference-engineer
--------------------------------------------------------------------------------
Written by ``parquet_writer.write_table`` with the pinned settings (import it; do not write
Parquet by hand — byte-stability is the whole point). All columns are UTF-8 strings.

Row order MUST be the §6.6 reward-tree leaf order: ascending ``recipient`` (32-byte
big-endian compare of the hex-decoded pubkey), i.e. ``leaf_index`` ascending, contiguous
from 0. ``sort_order`` = ``"reward_leaf_index_asc"``.

Columns (exact names, exact order):

    leaf_index               canonical uint string, 0..N-1, contiguous
    recipient_hex            64 lowercase hex, MUST hex-decode to exactly 32 bytes (else hard
                             error). This matches the ratified reward-0x test vectors and the
                             engine's leaf-set output; hex vs base58 is presentation only — the
                             §6.6 preimage consumes 32 raw bytes, so the encoding does not move
                             any leaf hash or the reward root.
    amount_base_units        canonical uint string, mint-native base units
    leaf_hash_hex            64 lowercase hex, SHA-256(0x00||"CRP:reward:v1"||leaf_content)

One leaf per RECIPIENT (aggregate over cohorts, §6.6 RESIDUAL-A shape); recipients whose
aggregate is 0 are OMITTED. Per-cohort detail belongs in ``analysis.json``, not here.

The assembler recomputes ``reward_root`` from these rows with
``verifier-cli/reference/reward.py`` and rejects the bundle if the recomputed root disagrees
with the table's own ``leaf_hash_hex`` values or if the row order is not §6.6-canonical.

--------------------------------------------------------------------------------
Handoff mechanics
--------------------------------------------------------------------------------
The causal engine may either (a) write both files into a directory and pass it as
``analysis_dir`` to ``assemble_bundle``, or (b) pass ``analysis_object`` / ``rewards_table``
in-process. Either way the assembler is the only writer of the sealed bundle, so there is
exactly one place that decides bytes.

A bundle sealed WITHOUT these two artifacts is legal and marked
``"completeness": "evidence-only"`` in ``roots.json`` — useful for anchoring evidence epochs
before evaluation exists. It is NOT sufficient for ``finalize_distribution``.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from .errors import EvidenceRejected, RejectionCode
from .parquet_writer import Table
from .validate import RE_HEX64, RE_UINT

__all__ = [
    "ANALYSIS_FILENAME",
    "REWARDS_FILENAME",
    "REWARDS_COLUMNS",
    "REWARDS_SORT_ORDER",
    "ANALYSIS_REQUIRED_KEYS",
    "validate_analysis_object",
    "validate_rewards_table",
]

ANALYSIS_FILENAME = "analysis.json"
REWARDS_FILENAME = "rewards.parquet"
REWARDS_COLUMNS = ("leaf_index", "recipient_hex", "amount_base_units", "leaf_hash_hex")
REWARDS_SORT_ORDER = "reward_leaf_index_asc"

ANALYSIS_REQUIRED_KEYS = (
    "spec_version",
    "experiment_id",
    "evidence_epoch_roots",
    "primary_estimate",
    "reward_summary",
    "cohorts",
)


def _nested_container_digest(analysis: Mapping[str, Any]) -> str | None:
    """The engine nests the digest under ``engine.analysis_container_digest``."""
    engine = analysis.get("engine")
    if isinstance(engine, Mapping):
        d = engine.get("analysis_container_digest")
        if d is not None:
            return str(d)
    return None


def validate_analysis_object(
    analysis: Mapping[str, Any],
    *,
    experiment_id: str,
    evidence_epoch_roots: Sequence[str],
    analysis_container_digest: str | None = None,
) -> None:
    """Enforce the ``analysis.json`` seam contract. Raises ``EvidenceRejected`` on violation.

    The engine's richer schema is normative for content; the assembler validates only the
    keys it depends on plus the freeze-before-reveal ``evidence_epoch_roots`` link.
    """
    missing = [k for k in ANALYSIS_REQUIRED_KEYS if k not in analysis]
    if missing:
        raise EvidenceRejected(
            RejectionCode.BUNDLE_INCOMPLETE,
            "analysis.json missing required keys: %s" % ", ".join(missing),
            missing=missing,
        )
    if analysis["experiment_id"] != experiment_id:
        raise EvidenceRejected(
            RejectionCode.EXPERIMENT_ID_MISMATCH,
            "analysis.json experiment_id %r != bundle %r"
            % (analysis["experiment_id"], experiment_id),
        )
    if analysis_container_digest is not None:
        declared_digest = _nested_container_digest(analysis)
        if declared_digest is not None and declared_digest != analysis_container_digest:
            raise EvidenceRejected(
                RejectionCode.BUNDLE_INCOMPLETE,
                "analysis.json engine.analysis_container_digest %r != frozen manifest %r"
                % (declared_digest, analysis_container_digest),
            )
    declared = list(analysis["evidence_epoch_roots"])
    if declared != list(evidence_epoch_roots):
        raise EvidenceRejected(
            RejectionCode.BUNDLE_INCOMPLETE,
            "analysis.json evidence_epoch_roots do not match the roots built from this "
            "bundle's evidence (analysis consumed different evidence): analysis=%s bundle=%s"
            % (declared, list(evidence_epoch_roots)),
            analysis_roots=declared,
            bundle_roots=list(evidence_epoch_roots),
        )


def validate_rewards_table(table: Table) -> None:
    """Enforce the ``rewards.parquet`` contract (shape + §6.6 ordering)."""
    if tuple(table.columns) != REWARDS_COLUMNS:
        raise EvidenceRejected(
            RejectionCode.BUNDLE_INCOMPLETE,
            "rewards.parquet columns must be exactly %s, got %s"
            % (list(REWARDS_COLUMNS), list(table.columns)),
        )
    if table.sort_order != REWARDS_SORT_ORDER:
        raise EvidenceRejected(
            RejectionCode.BUNDLE_INCOMPLETE,
            "rewards.parquet sort_order must be %r, got %r"
            % (REWARDS_SORT_ORDER, table.sort_order),
        )
    for i, row in enumerate(table.rows):
        leaf_index, recipient, amount, leaf_hash = row
        if not RE_UINT.match(leaf_index) or int(leaf_index) != i:
            raise EvidenceRejected(
                RejectionCode.BUNDLE_INCOMPLETE,
                "rewards.parquet leaf_index must be 0..N-1 contiguous in row order; row %d "
                "has leaf_index=%r" % (i, leaf_index),
            )
        if not RE_UINT.match(amount):
            raise EvidenceRejected(
                RejectionCode.NON_CANONICAL_INTEGER_STRING,
                "rewards.parquet amount_base_units is not a canonical uint string: %r" % (amount,),
            )
        if not RE_HEX64.match(leaf_hash):
            raise EvidenceRejected(
                RejectionCode.BUNDLE_INCOMPLETE,
                "rewards.parquet leaf_hash_hex is not 64 lowercase hex: %r" % (leaf_hash,),
            )
        if not RE_HEX64.match(recipient):
            raise EvidenceRejected(
                RejectionCode.BUNDLE_INCOMPLETE,
                "rewards.parquet recipient_hex must be 64 lowercase hex (hex-decode to "
                "exactly 32 bytes): %r" % (recipient,),
            )
