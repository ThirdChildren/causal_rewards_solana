"""Audit-bundle assembly — the immutable, content-addressed, mirrorable artifact.

Layout (``bundle_layout_version`` 1.0.0)::

    manifest.json          the FROZEN experiment manifest, verbatim canonical bytes
    participants.parquet   participant set, in participant-leaf order
    assignment.parquet     cohort -> arm, in assignment-leaf order (cohort_id UTF-16 asc)
    evidence/
      epoch-<NNNNNN>.parquet   one table per epoch, rows in evidence-leaf order (leaf_hash asc)
      findings.json            ingestion correlation findings + rejected submissions
      missingness.json         expected schedule vs anchored coverage
    analysis.json          OWNED BY causal-inference-engineer (see contracts.py)
    rewards.parquet        OWNED BY causal-inference-engineer (see contracts.py)
    roots.json             every Merkle root + the file index
    provenance.json        source commit, container digest, package versions, timestamp

``manifest.json`` is the frozen EXPERIMENT manifest, byte-for-byte, because its SHA-256 is
what ``freeze_experiment`` anchored on-chain — rewriting it in any way would break the one
hash the whole protocol hangs off. The bundle's own file index therefore lives in
``roots.json``, not in a second "manifest".

Hashing rules
-------------
* ``manifest_hash``       = SHA-256(CJSON(manifest))            — matches the on-chain value
* per-file ``sha256``     = SHA-256(the exact stored bytes)
* per-table ``canonical_content_hash`` = SHA-256(CJSON(logical rows)) — environment-independent
* ``bundle_content_hash`` = SHA-256(CJSON({relpath: {"canonical_content_hash"?, "sha256"}}))
  over every bundle file EXCEPT ``provenance.json`` — PHYSICAL identity of this exact
  materialization; stable within the pinned container.
* ``bundle_logical_hash``  = SHA-256(CJSON({relpath: canonical_content_hash or sha256})) over
  the same file set — LOGICAL identity, environment-independent (a different pyarrow build
  changes parquet bytes but not this). **This is the cross-machine reproducibility claim.**

``provenance.json`` is excluded because it legitimately varies between two runs of identical
inputs (execution timestamp, platform). It carries ``bundle_content_hash`` itself, so the
chain of custody is complete without making the content hash time-dependent. See
``provenance.py``.

Mirroring
---------
A bundle is a directory of immutable files plus a ``roots.json`` index that names each one by
hash. Copy it anywhere — S3, IPFS, Arweave, a tarball on a laptop — and ``verify_bundle`` on
the copy is sufficient to prove it is the same bundle. Nothing resolves through a hosted
endpoint, so no mirror is privileged.

Data minimization
-----------------
Only material already permitted by ``evidence.schema.json`` (commitments, coarse cohort
labels, integer aggregates, time ranges, signatures) reaches the bundle tables. Cohort ids are
the generalized cohort identifier; no coordinates, no per-reading timestamps, no raw payloads.
``validate.py`` enforces the closed schema at ingestion, so a producer cannot smuggle extra
fields into a table, and ``participants.parquet`` carries pubkeys and cohort labels only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import _ref, contracts, roots as roots_mod
from .anomalies import Finding
from .errors import EvidenceRejected, RejectionCode
from .ingest import EvidenceLedger
from .parquet_writer import PARQUET_WRITER_SETTINGS, Table, TableDigest, write_table
from .provenance import BuildContext, provenance_object
from .schedule import MissingnessReport

__all__ = [
    "BUNDLE_LAYOUT_VERSION",
    "SPEC_VERSION",
    "PARTICIPANT_COLUMNS",
    "ASSIGNMENT_COLUMNS",
    "EVIDENCE_COLUMNS",
    "BundleResult",
    "assemble_bundle",
    "verify_bundle",
]

BUNDLE_LAYOUT_VERSION = "1.0.0"
SPEC_VERSION = "1.1.0"

PARTICIPANT_COLUMNS = ("position", "participant_id", "cohort_id", "leaf_hash_hex")
ASSIGNMENT_COLUMNS = ("position", "cohort_id", "arm", "prf_u64", "leaf_hash_hex")
EVIDENCE_COLUMNS = (
    "position",
    "leaf_hash_hex",
    "experiment_id",
    "epoch_index",
    "cohort_id",
    "time_range_start",
    "time_range_end",
    "producer_pubkey",
    "header_hash_hex",
    "batch_signature_hex",
    "signer_set_root_hex",
    "signer_count",
    "observations_root_hex",
    "observation_leaf_count",
    "accepted_count",
    "rejected_count",
    "distinct_signers",
    "quality_score_micro_sum",
    "leaf_canonical_bytes_len",
    "batch_object_sha256",
)


def _content_index(files: Mapping[str, Mapping[str, str]]) -> dict[str, Any]:
    """Physical index: exact stored bytes of every file (level-2, container-scoped)."""
    return {
        rel: {k: v for k, v in sorted(meta.items()) if k in ("sha256", "canonical_content_hash")}
        for rel, meta in sorted(files.items())
    }


def _logical_index(files: Mapping[str, Mapping[str, str]]) -> dict[str, str]:
    """Logical index: ``canonical_content_hash`` where a table has one, else ``sha256``.

    JSON files in the bundle are already canonical bytes, so their ``sha256`` IS a logical
    hash. Parquet files are not, so their logical identity is the table's
    ``canonical_content_hash``. The resulting ``bundle_logical_hash`` is therefore
    environment-independent: it is identical on any machine, Python or pyarrow build, and it
    is the cross-machine reproducibility claim of record.
    """
    return {
        rel: str(meta.get("canonical_content_hash") or meta["sha256"])
        for rel, meta in sorted(files.items())
    }


def _write_json(path: Path, obj: Any) -> tuple[str, int]:
    """Write CJSON bytes; return (sha256_hex, size). One encoder, everywhere."""
    data = _ref.canonical_json_bytes(obj)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _ref.sha256_hex(data), len(data)


@dataclass(frozen=True)
class BundleResult:
    root_dir: Path
    #: SHA-256 over the exact stored bytes of every bundle file (physical, container-scoped).
    bundle_content_hash: str
    #: SHA-256 over the logical content of every bundle file (environment-independent).
    bundle_logical_hash: str
    manifest_hash: str
    roots: Mapping[str, Any]
    files: Mapping[str, Mapping[str, str]]
    completeness: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_content_hash": self.bundle_content_hash,
            "bundle_logical_hash": self.bundle_logical_hash,
            "completeness": self.completeness,
            "manifest_hash": self.manifest_hash,
            "root_dir": str(self.root_dir),
        }


def _epoch_filename(epoch_index: str) -> str:
    return "evidence/epoch-%06d.parquet" % int(epoch_index)


def assemble_bundle(
    out_dir: Path | str,
    *,
    manifest: Mapping[str, Any],
    ledger: EvidenceLedger,
    participants: Sequence[Mapping[str, Any]],
    assignments: Sequence[Any],
    missingness: MissingnessReport | None = None,
    analysis_object: Mapping[str, Any] | None = None,
    rewards_table: Table | None = None,
    build_context: BuildContext | None = None,
    extra_findings: Sequence[Finding] = (),
) -> BundleResult:
    """Assemble and seal an audit bundle. Pure function of its inputs (no clock, no RNG).

    ``analysis_object`` / ``rewards_table`` are the causal engine's artifacts (contracts.py).
    Omitting them yields a legal ``completeness="evidence-only"`` bundle.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, str]] = {}

    # -- manifest.json (verbatim canonical bytes of the FROZEN manifest) ---------------
    manifest_hash, manifest_size = _write_json(out / "manifest.json", manifest)
    files["manifest.json"] = {"sha256": manifest_hash, "size": str(manifest_size)}
    experiment_id = str(manifest["experiment_id"])
    if ledger.experiment_id != experiment_id:
        raise EvidenceRejected(
            RejectionCode.EXPERIMENT_ID_MISMATCH,
            "ledger experiment_id %r != manifest experiment_id %r"
            % (ledger.experiment_id, experiment_id),
        )

    # -- participants.parquet ----------------------------------------------------------
    participant_root_hex, participant_records = roots_mod.participant_root(participants)
    participants_table = Table.from_records(
        "participants", PARTICIPANT_COLUMNS, participant_records, "participant_id_utf16_asc"
    )
    d = write_table(participants_table, out / "participants.parquet", rel_path="participants.parquet")
    files["participants.parquet"] = d.to_dict()

    # -- assignment.parquet ------------------------------------------------------------
    assignment_root_hex, assignment_records = roots_mod.assignment_root(assignments)
    assignment_table = Table.from_records(
        "assignment", ASSIGNMENT_COLUMNS, assignment_records, "cohort_id_utf16_asc"
    )
    d = write_table(assignment_table, out / "assignment.parquet", rel_path="assignment.parquet")
    files["assignment.parquet"] = d.to_dict()

    # -- evidence/epoch-*.parquet ------------------------------------------------------
    epoch_entries: list[dict[str, Any]] = []
    for epoch_index in ledger.epochs():
        batches = ledger.batches_for_epoch(epoch_index)
        root_hex, records = roots_mod.evidence_epoch_root(batches)
        # Content address of the stored batch object = SHA-256(CJSON(batch)). Recorded so a
        # verifier can fetch the exact object from any mirror of the CAS. Keyed by leaf_hash
        # so the attachment cannot perturb the canonical row order.
        by_leaf: dict[str, str] = {}
        for b in batches:
            cb = _ref.canonical_json_bytes(b)
            lh = _ref.sha256(_ref.merkle.LEAF_PREFIX + _ref.merkle.DOMAIN_EVIDENCE + cb).hex()
            by_leaf[lh] = _ref.sha256_hex(cb)
        for rec in records:
            rec["batch_object_sha256"] = by_leaf[rec["leaf_hash_hex"]]

        table = Table.from_records(
            "evidence_epoch_%s" % epoch_index, EVIDENCE_COLUMNS, records, "leaf_hash_asc"
        )
        rel = _epoch_filename(epoch_index)
        d = write_table(table, out / rel, rel_path=rel)
        files[rel] = d.to_dict()
        epoch_entries.append(
            {
                "batch_count": str(len(batches)),
                "epoch_index": str(epoch_index),
                "evidence_epoch_root_hex": root_hex,
                "file": rel,
                "per_batch_observations_root_hex": [
                    r["observations_root_hex"] for r in records
                ],
                "per_batch_signer_set_root_hex": [r["signer_set_root_hex"] for r in records],
            }
        )

    # -- evidence/findings.json --------------------------------------------------------
    findings = sorted(list(ledger.findings()) + list(extra_findings))
    findings_obj = {
        "experiment_id": experiment_id,
        "findings": [f.to_dict() for f in findings],
        "policy": (
            "Findings are ADMITTED-but-flagged signals, never rejections. Rejected "
            "submissions are listed separately and never entered any tree."
        ),
        "rejected_submissions": ledger.rejection_records(),
    }
    h, size = _write_json(out / "evidence/findings.json", findings_obj)
    files["evidence/findings.json"] = {"sha256": h, "size": str(size)}

    # -- evidence/missingness.json -----------------------------------------------------
    missingness_obj: dict[str, Any] = (
        missingness.to_dict()
        if missingness is not None
        else {
            "status": "not_evaluated",
            "policy": (
                "No frozen schedule was supplied to the assembler, so selective-reporting "
                "coverage could NOT be evaluated. A bundle in this state must not be used to "
                "support a causal claim."
            ),
        }
    )
    h, size = _write_json(out / "evidence/missingness.json", missingness_obj)
    files["evidence/missingness.json"] = {"sha256": h, "size": str(size)}

    # -- analysis.json / rewards.parquet (causal-inference-engineer, contracts.py) ------
    completeness = "evidence-only"
    reward_root_hex = "absent"
    all_epoch_roots = [e["evidence_epoch_root_hex"] for e in epoch_entries]

    if analysis_object is not None:
        contracts.validate_analysis_object(
            analysis_object,
            experiment_id=experiment_id,
            evidence_epoch_roots=all_epoch_roots,
            analysis_container_digest=str(
                manifest.get("analysis_plan", {}).get("analysis_container_digest")
            )
            if manifest.get("analysis_plan", {}).get("analysis_container_digest") is not None
            else None,
        )
        h, size = _write_json(out / contracts.ANALYSIS_FILENAME, analysis_object)
        files[contracts.ANALYSIS_FILENAME] = {"sha256": h, "size": str(size)}

    if rewards_table is not None:
        contracts.validate_rewards_table(rewards_table)
        reward_root_hex = _reward_root_from_table(rewards_table)
        d = write_table(
            rewards_table, out / contracts.REWARDS_FILENAME, rel_path=contracts.REWARDS_FILENAME
        )
        files[contracts.REWARDS_FILENAME] = d.to_dict()

    if analysis_object is not None and rewards_table is not None:
        completeness = "complete"
    elif analysis_object is not None or rewards_table is not None:
        raise EvidenceRejected(
            RejectionCode.BUNDLE_INCOMPLETE,
            "analysis.json and rewards.parquet must be supplied together (a reward root with "
            "no analysis, or an analysis with no rewards, is not settleable)",
        )

    # -- roots.json --------------------------------------------------------------------
    roots_obj: dict[str, Any] = {
        "bundle_layout_version": BUNDLE_LAYOUT_VERSION,
        "completeness": completeness,
        "experiment_id": experiment_id,
        "files": {k: files[k] for k in sorted(files)},
        "manifest_hash": manifest_hash,
        "merkle_scheme": {
            "domain_tags": {
                "assignment": "CRP:assignment:v1",
                "evidence": "CRP:evidence:v1",
                "observation_subtree_leaf": "obs",
                "participant": "CRP:participant:v1",
                "reward": "CRP:reward:v1",
                "signer_subtree_leaf": "signer",
            },
            "empty_root_hex": roots_mod.EMPTY_ROOT_HEX,
            "leaf_prefix": "00",
            "node_prefix": "01",
            "odd_node": "promote-unpaired-trailing-node",
            "spec": "serialization.md §6.1-§6.6",
        },
        "roots": {
            "assignment_root_hex": assignment_root_hex,
            "evidence_epochs": epoch_entries,
            "participant_root_hex": participant_root_hex,
            "participant_root_status": roots_mod.PARTICIPANT_LEAF_STATUS,
            "reward_root_hex": reward_root_hex,
        },
        "spec_version": SPEC_VERSION,
        "notes": {
            "on_chain_epoch_field_mapping": (
                "EvidenceEpoch.{signer_set_root,observations_root} are SINGULAR on-chain "
                "while a multi-batch epoch has one sub-root per batch. The mapping is an OPEN "
                "item owned by protocol-architect + solana-program-engineer; this bundle "
                "publishes the full ordered per-batch lists so any ratified mapping is "
                "computable from the bundle without re-ingesting."
            ),
            "dedup_semantics": (
                "The evidence tree does NOT deduplicate. Two producers reporting the same "
                "(experiment_id, epoch_index, cohort_id) are two distinct admitted leaves. "
                "Replay/double-report dedup happens at ingestion (event nonce + content hash)."
            ),
        },
    }
    h, size = _write_json(out / "roots.json", roots_obj)
    files["roots.json"] = {"sha256": h, "size": str(size)}

    # -- bundle hashes (everything except provenance.json) ------------------------------
    bundle_content_hash = _ref.sha256_hex(
        _ref.canonical_json_bytes(_content_index(files))
    )
    bundle_logical_hash = _ref.sha256_hex(
        _ref.canonical_json_bytes(_logical_index(files))
    )

    # -- provenance.json (EXCLUDED from bundle_content_hash) ---------------------------
    ctx = build_context or BuildContext.from_env()
    prov = provenance_object(
        ctx,
        bundle_layout_version=BUNDLE_LAYOUT_VERSION,
        spec_version=SPEC_VERSION,
        parquet_writer_settings=PARQUET_WRITER_SETTINGS,
        ingest_flags={
            "accepted_batches": len(ledger.accepted),
            "rejected_batches": len(ledger.rejected),
            "unverified_header_hash_mismatches": len(ledger.unverified_header_hash_mismatches),
            "verify_signatures": "true" if ledger.verify_signatures else "false",
        },
    )
    prov["bundle_content_hash"] = bundle_content_hash
    prov["bundle_logical_hash"] = bundle_logical_hash
    prov["manifest_hash"] = manifest_hash
    _write_json(out / "provenance.json", prov)

    return BundleResult(
        root_dir=out,
        bundle_content_hash=bundle_content_hash,
        bundle_logical_hash=bundle_logical_hash,
        manifest_hash=manifest_hash,
        roots=roots_obj["roots"],
        files=files,
        completeness=completeness,
    )


def _reward_root_from_table(table: Table) -> str:
    """Recompute the §6.6 reward root from ``rewards.parquet`` rows via the reference impl."""
    leaves = []
    for leaf_index, recipient_b58, amount, leaf_hash_hex in table.rows:
        recipient = roots_mod.signer_pubkey_be32(recipient_b58)
        expected = _ref.reward.reward_leaf_hash(recipient, int(amount), int(leaf_index)).hex()
        if expected != leaf_hash_hex:
            raise EvidenceRejected(
                RejectionCode.BUNDLE_INCOMPLETE,
                "rewards.parquet leaf_hash_hex %s does not match the recomputed §6.6 leaf hash "
                "%s for leaf_index=%s" % (leaf_hash_hex, expected, leaf_index),
            )
        leaves.append(_ref.reward.RewardLeaf(recipient, int(amount), int(leaf_index)))
    return _ref.reward.reward_root(leaves).hex()


def verify_bundle(bundle_dir: Path | str) -> dict[str, Any]:
    """Re-hash a bundle on disk and recompute ``bundle_content_hash``.

    Offline and dependency-light: reads only the files named in ``roots.json``. Returns a
    report; raises only if the bundle is structurally unreadable. This is the assembler-side
    smoke check — ``verifier-cli`` remains the independent oracle that also RE-DERIVES the
    roots from the underlying data rather than merely re-hashing files.
    """
    d = Path(bundle_dir)
    roots_bytes = (d / "roots.json").read_bytes()
    roots_obj = json.loads(roots_bytes.decode("utf-8"))
    files = dict(roots_obj["files"])
    files["roots.json"] = {"sha256": _ref.sha256_hex(roots_bytes)}

    mismatched: list[str] = []
    missing: list[str] = []
    for rel, meta in sorted(files.items()):
        p = d / rel
        if not p.is_file():
            missing.append(rel)
            continue
        if _ref.sha256_hex(p.read_bytes()) != meta["sha256"]:
            mismatched.append(rel)

    bundle_content_hash = _ref.sha256_hex(_ref.canonical_json_bytes(_content_index(files)))
    bundle_logical_hash = _ref.sha256_hex(_ref.canonical_json_bytes(_logical_index(files)))

    prov_path = d / "provenance.json"
    declared: str | None = None
    declared_logical: str | None = None
    if prov_path.is_file():
        prov = json.loads(prov_path.read_bytes().decode("utf-8"))
        declared = prov.get("bundle_content_hash")
        declared_logical = prov.get("bundle_logical_hash")

    return {
        "bundle_content_hash": bundle_content_hash,
        "bundle_logical_hash": bundle_logical_hash,
        "declared_bundle_content_hash": declared or "",
        "declared_bundle_logical_hash": declared_logical or "",
        "file_count": str(len(files)),
        "matches_provenance": "true" if declared == bundle_content_hash else "false",
        "missing_files": missing,
        "mismatched_files": mismatched,
        "ok": "true" if (not missing and not mismatched and declared == bundle_content_hash) else "false",
    }
