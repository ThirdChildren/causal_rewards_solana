"""CLI end-to-end: golden-vector replay, assemble, verify."""

from __future__ import annotations

import json
from pathlib import Path

import fixtures as fx

from crp_evidence import _ref
from crp_evidence.cli import main

TV = str(fx.TEST_VECTORS / "evidence")


def test_vectors_subcommand_exits_zero_and_reports_every_root(capsys) -> None:
    rc = main(["vectors", "--test-vectors", TV])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["ok"] == "true"
    actual = {v["name"]: v["actual"] for v in out["vectors"]}
    assert actual["evidence-01-epoch-multibatch"].startswith("a13e1cdc")
    assert actual["evidence-02-signer-set-multisigner"].startswith("e45697c8")
    assert actual["evidence-03-observation-set"].startswith("1010891b")
    assert actual["evidence-04-empty-tree"] == "00" * 32
    assert actual["evidence-05-signer-not-32-error"] == "SIGNER_PUBKEY_NOT_32_BYTES"


def test_assemble_and_verify_roundtrip(tmp_path: Path, capsys) -> None:
    manifest_p = tmp_path / "manifest.json"
    batches_p = tmp_path / "batches.json"
    participants_p = tmp_path / "participants.json"
    cohorts_p = tmp_path / "cohorts.json"
    manifest_p.write_bytes(_ref.canonical_json_bytes(fx.small_manifest()))
    batches_p.write_bytes(_ref.canonical_json_bytes(fx.full_batch_set()))
    participants_p.write_bytes(_ref.canonical_json_bytes(fx.participants()))
    cohorts_p.write_bytes(_ref.canonical_json_bytes(list(fx.COHORT_IDS)))

    rc = main(
        [
            "assemble",
            "--manifest", str(manifest_p),
            "--batches", str(batches_p),
            "--participants", str(participants_p),
            "--cohort-ids", str(cohorts_p),
            "--out", str(tmp_path / "bundle"),
            "--strict",
            "--source-commit", "cafebabe",
            "--container-digest", "sha256:deadbeef",
            "--execution-timestamp", "1721001600",
        ]
    )
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["completeness"] == "evidence-only"

    rc = main(["verify", str(tmp_path / "bundle")])
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["ok"] == "true"
    assert report["bundle_content_hash"] == result["bundle_content_hash"]

    prov = json.loads((tmp_path / "bundle" / "provenance.json").read_bytes().decode("utf-8"))
    assert prov["source_commit"] == "cafebabe"
    assert prov["container_digest"] == "sha256:deadbeef"
    assert prov["execution_timestamp"] == "1721001600"
    assert prov["ingest_flags"]["verify_signatures"] == "true"


def test_ingest_subcommand_reports_findings(tmp_path: Path, capsys) -> None:
    obs = fx.commitments(4, 0x40)
    batches = [
        fx.make_batch(epoch_index="0", cohort_id="cohort-a", obs=obs),
        fx.make_batch(
            epoch_index="0", cohort_id="cohort-a", obs=obs, secret=fx.PRODUCER_B_SECRET
        ),
    ]
    p = tmp_path / "b.json"
    p.write_bytes(_ref.canonical_json_bytes(batches))
    rc = main(["ingest", "--experiment-id", fx.EXPERIMENT_ID, "--batches", str(p), "--strict"])
    out = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert out["accepted"] == "2"
    assert any(
        f["code"] == "DUPLICATE_OBSERVATIONS_ROOT_ACROSS_PRODUCERS" for f in out["findings"]
    )
