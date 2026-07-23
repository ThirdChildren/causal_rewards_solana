"""Bundle layout, sealing, verification, and the causal-engine artifact contract."""

from __future__ import annotations

import json
from pathlib import Path

import fixtures as fx
import pytest

from crp_evidence import _ref
from crp_evidence.bundle import assemble_bundle, verify_bundle
from crp_evidence.contracts import REWARDS_COLUMNS, REWARDS_SORT_ORDER
from crp_evidence.errors import EvidenceRejected
from crp_evidence.ingest import EvidenceLedger
from crp_evidence.parquet_writer import Table
from crp_evidence.provenance import BuildContext
from crp_evidence.schedule import evaluate_coverage, schedule_from_manifest

CTX = BuildContext(
    source_commit="deadbeef", container_digest="sha256:test", execution_timestamp="0"
)


def _ledger() -> EvidenceLedger:
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest_many(fx.full_batch_set(), strict=True)
    return led


def _build(tmp_path: Path, **kw):
    manifest = fx.small_manifest()
    led = _ledger()
    return assemble_bundle(
        tmp_path / "bundle",
        manifest=manifest,
        ledger=led,
        participants=fx.participants(),
        assignments=fx.assignments(),
        missingness=evaluate_coverage(
            schedule_from_manifest(manifest, fx.COHORT_IDS), [a.batch for a in led.accepted]
        ),
        build_context=CTX,
        **kw,
    )


def test_bundle_has_the_required_file_set(tmp_path: Path) -> None:
    res = _build(tmp_path)
    d = res.root_dir
    for rel in (
        "manifest.json",
        "participants.parquet",
        "assignment.parquet",
        "evidence/epoch-000000.parquet",
        "evidence/epoch-000001.parquet",
        "evidence/findings.json",
        "evidence/missingness.json",
        "roots.json",
        "provenance.json",
    ):
        assert (d / rel).is_file(), rel
    # analysis.json / rewards.parquet are the causal engine's; absent => evidence-only.
    assert res.completeness == "evidence-only"
    assert not (d / "analysis.json").exists()
    assert not (d / "rewards.parquet").exists()


def test_manifest_json_is_the_frozen_manifest_verbatim(tmp_path: Path) -> None:
    """manifest_hash must equal the hash the chain anchored — CJSON of the manifest itself."""
    res = _build(tmp_path)
    raw = (res.root_dir / "manifest.json").read_bytes()
    assert raw == _ref.canonical_json_bytes(fx.small_manifest())
    assert res.manifest_hash == _ref.sha256_hex(raw)


def test_roots_json_shape(tmp_path: Path) -> None:
    res = _build(tmp_path)
    roots = json.loads((res.root_dir / "roots.json").read_bytes().decode("utf-8"))
    assert roots["bundle_layout_version"] == "1.0.0"
    assert roots["spec_version"] == "1.1.0"
    assert roots["roots"]["participant_root_status"] == "PROVISIONAL-UNPINNED-6.2"
    assert roots["roots"]["reward_root_hex"] == "absent"
    epochs = roots["roots"]["evidence_epochs"]
    assert [e["epoch_index"] for e in epochs] == ["0", "1"]
    assert [e["batch_count"] for e in epochs] == ["3", "2"]
    for e in epochs:
        assert len(e["evidence_epoch_root_hex"]) == 64
        assert len(e["per_batch_signer_set_root_hex"]) == int(e["batch_count"])
        assert len(e["per_batch_observations_root_hex"]) == int(e["batch_count"])
    # The open on-chain mapping question is disclosed IN the artifact, not just in docs.
    assert "on_chain_epoch_field_mapping" in roots["notes"]
    assert "dedup_semantics" in roots["notes"]


def test_evidence_rows_are_in_leaf_hash_order(tmp_path: Path) -> None:
    import pyarrow.parquet as pq

    res = _build(tmp_path)
    t = pq.read_table(res.root_dir / "evidence/epoch-000000.parquet")
    leaf_hashes = t.column("leaf_hash_hex").to_pylist()
    assert leaf_hashes == sorted(leaf_hashes)
    assert t.column("position").to_pylist() == [str(i) for i in range(len(leaf_hashes))]
    assert all(t.schema.field(i).type == __import__("pyarrow").string() for i in range(t.num_columns))


def test_assignment_rows_are_in_cohort_id_order(tmp_path: Path) -> None:
    import pyarrow.parquet as pq

    res = _build(tmp_path)
    t = pq.read_table(res.root_dir / "assignment.parquet")
    assert t.column("cohort_id").to_pylist() == sorted(fx.COHORT_IDS)


def test_verify_bundle_passes_on_a_sealed_bundle(tmp_path: Path) -> None:
    res = _build(tmp_path)
    report = verify_bundle(res.root_dir)
    assert report["ok"] == "true"
    assert report["bundle_content_hash"] == res.bundle_content_hash
    assert report["matches_provenance"] == "true"
    assert report["missing_files"] == []


def test_verify_bundle_detects_tampering(tmp_path: Path) -> None:
    res = _build(tmp_path)
    p = res.root_dir / "evidence/epoch-000000.parquet"
    p.write_bytes(p.read_bytes() + b"\x00")
    report = verify_bundle(res.root_dir)
    assert report["ok"] == "false"
    assert "evidence/epoch-000000.parquet" in report["mismatched_files"]


def test_bundle_is_mirrorable_by_plain_copy(tmp_path: Path) -> None:
    import shutil

    res = _build(tmp_path)
    mirror = tmp_path / "mirror"
    shutil.copytree(res.root_dir, mirror)
    report = verify_bundle(mirror)
    assert report["ok"] == "true"
    assert report["bundle_content_hash"] == res.bundle_content_hash


def test_ledger_manifest_experiment_id_must_agree(tmp_path: Path) -> None:
    manifest = fx.small_manifest()
    manifest["experiment_id"] = "another-experiment"
    with pytest.raises(EvidenceRejected) as ei:
        assemble_bundle(
            tmp_path / "b",
            manifest=manifest,
            ledger=_ledger(),
            participants=fx.participants(),
            assignments=fx.assignments(),
            build_context=CTX,
        )
    assert ei.value.code == "EXPERIMENT_ID_MISMATCH"


# --------------------------------------------------------------- causal-engine contract


def _rewards_table(recipients: list[bytes], amounts: list[int]) -> Table:
    agg = _ref.reward.aggregate_contributions(list(zip(recipients, amounts)))
    leaves = _ref.reward.compile_reward_leaves(agg)
    records = [
        {
            "leaf_index": str(lf.leaf_index),
            "recipient_pubkey": _ref.evidence.b58encode(lf.recipient),
            "amount_base_units": str(lf.amount_base_units),
            "leaf_hash_hex": _ref.reward.reward_leaf_hash(
                lf.recipient, lf.amount_base_units, lf.leaf_index
            ).hex(),
        }
        for lf in leaves
    ]
    return Table.from_records("rewards", REWARDS_COLUMNS, records, REWARDS_SORT_ORDER)


def _analysis(epoch_roots: list[str]) -> dict:
    return {
        "spec_version": "1.1.0",
        "experiment_id": fx.EXPERIMENT_ID,
        "analysis_container_digest": fx.small_manifest()["analysis_plan"][
            "analysis_container_digest"
        ],
        "evidence_epoch_roots": epoch_roots,
        "estimates": [],
        "result": {
            "effect_micro": "125000",
            "standard_error_micro": "40000",
            "conservative_effect_micro": "46800",
            "critical_value_micro": "1960000",
            "confidence_level_micro": "950000",
            "degrees_of_freedom": "12",
            "eligible_cohort_count": "2",
            "null_result": "false",
        },
        "sensitivity": {},
        "missingness_handling": {"policy": "listwise-drop-of-missing-cells"},
    }


def test_complete_bundle_with_analysis_and_rewards(tmp_path: Path) -> None:
    res0 = _build(tmp_path / "probe")
    epoch_roots = [e["evidence_epoch_root_hex"] for e in res0.roots["evidence_epochs"]]
    rewards = _rewards_table(
        [bytes([0xD1]) + bytes(31), bytes([0xD2]) + bytes(31)], [1000, 2500]
    )
    res = _build(
        tmp_path / "full", analysis_object=_analysis(epoch_roots), rewards_table=rewards
    )
    assert res.completeness == "complete"
    assert (res.root_dir / "analysis.json").is_file()
    assert (res.root_dir / "rewards.parquet").is_file()
    assert res.roots["reward_root_hex"] != "absent"
    assert len(res.roots["reward_root_hex"]) == 64
    assert verify_bundle(res.root_dir)["ok"] == "true"


def test_analysis_declaring_different_evidence_roots_is_rejected(tmp_path: Path) -> None:
    rewards = _rewards_table([bytes([0xD1]) + bytes(31)], [1000])
    with pytest.raises(EvidenceRejected) as ei:
        _build(
            tmp_path / "bad",
            analysis_object=_analysis(["11" * 32]),
            rewards_table=rewards,
        )
    assert ei.value.code == "BUNDLE_INCOMPLETE"
    assert "evidence_epoch_roots" in ei.value.message


def test_rewards_without_analysis_is_rejected(tmp_path: Path) -> None:
    rewards = _rewards_table([bytes([0xD1]) + bytes(31)], [1000])
    with pytest.raises(EvidenceRejected) as ei:
        _build(tmp_path / "bad", rewards_table=rewards)
    assert ei.value.code == "BUNDLE_INCOMPLETE"


def test_rewards_table_with_a_wrong_leaf_hash_is_rejected(tmp_path: Path) -> None:
    res0 = _build(tmp_path / "probe")
    epoch_roots = [e["evidence_epoch_root_hex"] for e in res0.roots["evidence_epochs"]]
    good = _rewards_table([bytes([0xD1]) + bytes(31)], [1000])
    rows = list(good.rows)
    rows[0] = (rows[0][0], rows[0][1], rows[0][2], "ff" * 32)
    tampered = Table(good.name, good.columns, tuple(rows), good.sort_order)
    with pytest.raises(EvidenceRejected) as ei:
        _build(
            tmp_path / "bad",
            analysis_object=_analysis(epoch_roots),
            rewards_table=tampered,
        )
    assert ei.value.code == "BUNDLE_INCOMPLETE"
    assert "leaf_hash_hex" in ei.value.message
