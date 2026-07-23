"""``crp-evidence`` CLI — ingest, root, assemble, verify.

Every artifact-producing subcommand takes its non-data inputs explicitly (execution
timestamp, container digest, source commit) so no subcommand ever reads the clock. Output is
canonical JSON on stdout.

Subcommands
-----------
``ingest``      verify + deduplicate a JSON array of signed batches; print the ledger summary
``roots``       print the evidence epoch roots for a batch file
``vectors``     replay ``test-vectors/evidence/*`` and report reproduce/fail per vector
``assemble``    build an audit bundle from a manifest + batches + participants + assignment
``verify``      re-hash a bundle directory and recompute ``bundle_content_hash``
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import _ref
from .bundle import assemble_bundle, verify_bundle
from .errors import EvidenceRejected
from .ingest import EvidenceLedger
from .provenance import BuildContext
from .roots import (
    EMPTY_ROOT_HEX,
    evidence_epoch_root,
    observations_root,
    signer_set_root,
)
from .schedule import evaluate_coverage, schedule_from_manifest


def _load(path: str) -> Any:
    return json.loads(Path(path).read_bytes().decode("utf-8"))


def _emit(obj: Any) -> None:
    sys.stdout.write(_ref.canonical_json_bytes(obj).decode("utf-8") + "\n")


def _cmd_ingest(args: argparse.Namespace) -> int:
    batches = _load(args.batches)
    ledger = EvidenceLedger(
        experiment_id=args.experiment_id, verify_signatures=not args.no_verify_signatures
    )
    ledger.ingest_many(batches, strict=args.strict)
    _emit(
        {
            "accepted": str(len(ledger.accepted)),
            "epochs": ledger.epochs(),
            "findings": [f.to_dict() for f in ledger.findings()],
            "rejected": ledger.rejection_records(),
        }
    )
    return 0


def _cmd_roots(args: argparse.Namespace) -> int:
    batches = _load(args.batches)
    ledger = EvidenceLedger(
        experiment_id=args.experiment_id, verify_signatures=not args.no_verify_signatures
    )
    ledger.ingest_many(batches, strict=True)
    out = []
    for epoch in ledger.epochs():
        root_hex, records = evidence_epoch_root(ledger.batches_for_epoch(epoch))
        out.append(
            {
                "batch_count": str(len(records)),
                "epoch_index": epoch,
                "evidence_epoch_root_hex": root_hex,
            }
        )
    _emit({"epochs": out})
    return 0


def _cmd_vectors(args: argparse.Namespace) -> int:
    """Replay the ratified evidence golden vectors. Exit 1 on any mismatch."""
    tv = Path(args.test_vectors)
    index = json.loads((tv / "index.json").read_bytes().decode("utf-8"))
    results: list[dict[str, str]] = []
    ok = True
    for entry in index["vectors"]:
        name = entry["name"]
        vec = json.loads((tv / (name + ".json")).read_bytes().decode("utf-8"))
        kind = entry["kind"]
        try:
            if kind == "evidence_epoch":
                actual, _ = evidence_epoch_root(vec["inputs"]["batches"])
                expected = entry["evidence_epoch_root_hex"]
            elif kind == "evidence_signer_set":
                actual, _ = signer_set_root(vec["inputs"]["signer_pubkeys_base58"])
                expected = entry["signer_set_root_hex"]
            elif kind == "evidence_observation_set":
                actual, _ = observations_root(vec["inputs"]["payload_commitment_hexes"])
                expected = entry["observations_root_hex"]
            elif kind == "evidence_empty_tree":
                actual, _ = evidence_epoch_root([])
                expected = entry["empty_root_hex"]
                if actual != EMPTY_ROOT_HEX:
                    ok = False
            elif kind == "evidence_signer_not_32_error":
                expected = entry["rejection_code"]
                try:
                    signer_set_root([vec["inputs"]["signer_pubkey_base58"]])
                    actual = "ACCEPTED"
                except EvidenceRejected as exc:
                    actual = exc.code
            else:  # pragma: no cover
                actual, expected = "UNKNOWN_KIND", kind
        except EvidenceRejected as exc:  # pragma: no cover
            actual, expected = "ERROR:" + exc.code, "<root>"
        match = actual == expected
        ok = ok and match
        results.append(
            {"actual": actual, "expected": expected, "match": "true" if match else "false", "name": name}
        )
    _emit({"ok": "true" if ok else "false", "vectors": results})
    return 0 if ok else 1


def _cmd_assemble(args: argparse.Namespace) -> int:
    manifest = _load(args.manifest)
    batches = _load(args.batches)
    participants = _load(args.participants) if args.participants else []
    ledger = EvidenceLedger(
        experiment_id=str(manifest["experiment_id"]),
        verify_signatures=not args.no_verify_signatures,
    )
    ledger.ingest_many(batches, strict=args.strict)

    assignments: list[Any] = []
    if args.assignment:
        raw = _load(args.assignment)
        assignments = [
            _ref.assignment.CohortAssignment(
                str(a["cohort_id"]), str(a["arm"]), int(a["prf_u64"])
            )
            for a in raw
        ]

    missingness = None
    if args.cohort_ids:
        cohort_ids = _load(args.cohort_ids)
        missingness = evaluate_coverage(
            schedule_from_manifest(manifest, cohort_ids),
            [a.batch for a in ledger.accepted],
        )

    ctx = BuildContext.from_env(
        source_commit=args.source_commit,
        container_digest=args.container_digest,
        execution_timestamp=args.execution_timestamp,
    )
    result = assemble_bundle(
        args.out,
        manifest=manifest,
        ledger=ledger,
        participants=participants,
        assignments=assignments,
        missingness=missingness,
        build_context=ctx,
    )
    _emit(result.to_dict())
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    report = verify_bundle(args.bundle)
    _emit(report)
    return 0 if report["ok"] == "true" else 1


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="crp-evidence", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def _sig_flags(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--no-verify-signatures",
            action="store_true",
            help="skip ed25519 verification (golden-vector replay ONLY; recorded in provenance)",
        )

    sp = sub.add_parser("ingest")
    sp.add_argument("--experiment-id", required=True)
    sp.add_argument("--batches", required=True)
    sp.add_argument("--strict", action="store_true", default=False)
    _sig_flags(sp)
    sp.set_defaults(func=_cmd_ingest)

    sp = sub.add_parser("roots")
    sp.add_argument("--experiment-id", required=True)
    sp.add_argument("--batches", required=True)
    _sig_flags(sp)
    sp.set_defaults(func=_cmd_roots)

    sp = sub.add_parser("vectors")
    sp.add_argument("--test-vectors", default="../test-vectors/evidence")
    sp.set_defaults(func=_cmd_vectors)

    sp = sub.add_parser("assemble")
    sp.add_argument("--manifest", required=True)
    sp.add_argument("--batches", required=True)
    sp.add_argument("--participants")
    sp.add_argument("--assignment")
    sp.add_argument("--cohort-ids", help="JSON array of the frozen cohort id set (missingness)")
    sp.add_argument("--out", required=True)
    sp.add_argument("--strict", action="store_true", default=False)
    sp.add_argument("--source-commit")
    sp.add_argument("--container-digest")
    sp.add_argument(
        "--execution-timestamp",
        help="unix seconds as a decimal string; never read from the clock",
    )
    _sig_flags(sp)
    sp.set_defaults(func=_cmd_assemble)

    sp = sub.add_parser("verify")
    sp.add_argument("bundle")
    sp.set_defaults(func=_cmd_verify)

    args = p.parse_args(argv)
    try:
        return int(args.func(args))
    except EvidenceRejected as exc:
        _emit({"error": exc.to_dict()})
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
