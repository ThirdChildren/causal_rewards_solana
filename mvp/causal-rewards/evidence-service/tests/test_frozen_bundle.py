"""Frozen input fixture -> frozen roots and bundle hashes (M3 definition of done).

These are golden values. If one changes, a byte rule changed — find out which and why before
touching the constants. The candidate for promotion into `test-vectors/` jointly with
`verifier-reproducibility-engineer` is exactly this fixture (``fixtures.full_batch_set`` +
``fixtures.small_manifest``) and exactly these hashes.

Which hashes are portable:

* ``EXPECTED_*_ROOT`` and ``EXPECTED_MANIFEST_HASH`` — pure CJSON/SHA-256, portable to ANY
  machine, language, or library version. Unconditional.
* ``EXPECTED_BUNDLE_LOGICAL_HASH`` — CJSON over logical table content. Also unconditional and
  environment-independent; this is the cross-machine reproducibility claim of record.
* ``EXPECTED_BUNDLE_CONTENT_HASH`` — includes parquet FILE bytes, so it is pinned to the
  container (pyarrow 18.1.0 with ``PARQUET_WRITER_SETTINGS``). It is asserted here because we
  run that container; a different pyarrow is a legitimate reason for it alone to move, and
  provenance.json records the version that produced it.
"""

from __future__ import annotations

import json
from pathlib import Path

import fixtures as fx

from crp_evidence.bundle import assemble_bundle, verify_bundle
from crp_evidence.ingest import EvidenceLedger
from crp_evidence.provenance import BuildContext
from crp_evidence.schedule import evaluate_coverage, schedule_from_manifest

EXPECTED_MANIFEST_HASH = "4aafcf1e0beb123af7c21d197bc1b959c87a10b653795539caabdfb1085b74eb"
EXPECTED_EPOCH0_ROOT = "25b60b5d19fd83fbda4f1ca836265e18a4cb3e1caca942ed2ed1e59dfd16d3e5"
EXPECTED_EPOCH1_ROOT = "06b8ec750c0c4f92fe812fcd3952a25eef6d237c0fdc6e80399aa3168313339d"
EXPECTED_ASSIGNMENT_ROOT = "a926f235c2d5ac82981dcf5fbca283b89a1c98d08506e43a40eca9ce0347e8f7"
EXPECTED_PARTICIPANT_ROOT_PROVISIONAL = (
    "b4683d9f6df64f1866445716b0513899d06e7005d36142ba429d90d32c89224a"
)
EXPECTED_BUNDLE_LOGICAL_HASH = (
    "c39143c866da4733b454a6a4bcce9eec98fbb4c22c9428f692ca2c474bd16f40"
)
EXPECTED_BUNDLE_CONTENT_HASH = (
    "064adccb0ea96d48c41ac9433fe6954d3a1f8404ef34c395bd917668bf71a529"
)
EXPECTED_TABLE_CANONICAL_HASHES = {
    "assignment.parquet": "a6b43b575e52fb193c1c382f023e7789d6316865c824b487ce21141ccbe61991",
    "evidence/epoch-000000.parquet": "a731938630e4cc7e352e5dbb0ed7c4772c2bd68f10df17c984ee2cbcf06b9085",
    "evidence/epoch-000001.parquet": "7dc0a296090e56598baba7a2425ca6f1186eae4a834ceb4a180fd01ed2197972",
    "participants.parquet": "1730b39e095417a22f59006454409f868d711db902b904be0b4776e77887027b",
}

CTX = BuildContext(
    source_commit="deadbeef", container_digest="sha256:test", execution_timestamp="0"
)


def _build(out: Path):
    manifest = fx.small_manifest()
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest_many(fx.full_batch_set(), strict=True)
    return assemble_bundle(
        out,
        manifest=manifest,
        ledger=led,
        participants=fx.participants(),
        assignments=fx.assignments(),
        missingness=evaluate_coverage(
            schedule_from_manifest(manifest, fx.COHORT_IDS), [a.batch for a in led.accepted]
        ),
        build_context=CTX,
    )


def test_frozen_roots(tmp_path: Path) -> None:
    res = _build(tmp_path / "b")
    assert res.manifest_hash == EXPECTED_MANIFEST_HASH
    epochs = {e["epoch_index"]: e["evidence_epoch_root_hex"] for e in res.roots["evidence_epochs"]}
    assert epochs == {"0": EXPECTED_EPOCH0_ROOT, "1": EXPECTED_EPOCH1_ROOT}
    assert res.roots["assignment_root_hex"] == EXPECTED_ASSIGNMENT_ROOT
    assert res.roots["participant_root_hex"] == EXPECTED_PARTICIPANT_ROOT_PROVISIONAL
    assert res.roots["participant_root_status"] == "PROVISIONAL-UNPINNED-6.2"


def test_frozen_table_logical_hashes(tmp_path: Path) -> None:
    res = _build(tmp_path / "b")
    actual = {
        rel: meta["canonical_content_hash"]
        for rel, meta in res.files.items()
        if "canonical_content_hash" in meta
    }
    assert actual == EXPECTED_TABLE_CANONICAL_HASHES


def test_frozen_bundle_logical_hash(tmp_path: Path) -> None:
    """Environment-independent. Must hold on any machine running any pyarrow."""
    res = _build(tmp_path / "b")
    assert res.bundle_logical_hash == EXPECTED_BUNDLE_LOGICAL_HASH


def test_frozen_bundle_content_hash_in_the_pinned_container(tmp_path: Path) -> None:
    import pyarrow

    assert pyarrow.__version__ == "18.1.0", (
        "EXPECTED_BUNDLE_CONTENT_HASH is pinned to pyarrow 18.1.0; the logical hash test is "
        "the portable gate"
    )
    res = _build(tmp_path / "b")
    assert res.bundle_content_hash == EXPECTED_BUNDLE_CONTENT_HASH


def test_verify_reports_both_hashes(tmp_path: Path) -> None:
    res = _build(tmp_path / "b")
    report = verify_bundle(res.root_dir)
    assert report["bundle_logical_hash"] == EXPECTED_BUNDLE_LOGICAL_HASH
    assert report["declared_bundle_logical_hash"] == EXPECTED_BUNDLE_LOGICAL_HASH
    assert report["ok"] == "true"


def test_bundle_carries_no_coordinates_or_raw_telemetry(tmp_path: Path) -> None:
    """Data minimization (invariant 5), asserted over the actual emitted bytes."""
    import pyarrow.parquet as pq

    res = _build(tmp_path / "b")
    forbidden = ("lat", "lon", "latitude", "longitude", "geo_point", "raw_", "payload_value")
    for rel in res.files:
        if rel.endswith(".parquet"):
            cols = [c.lower() for c in pq.read_schema(res.root_dir / rel).names]
            for col in cols:
                assert not any(f in col for f in forbidden), "%s exposes %s" % (rel, col)
    roots = json.loads((res.root_dir / "roots.json").read_bytes().decode("utf-8"))
    blob = json.dumps(roots).lower()
    assert "latitude" not in blob and "longitude" not in blob
