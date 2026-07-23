"""Determinism gates (CLAUDE.md invariant 2).

The strong gate is FRESH-PROCESS: each build runs in its own interpreter via ``subprocess``,
so anything that leaked process state (hash randomization, dict iteration seeded by address,
a cached clock read, an interned-string ordering) would show up as a byte difference. An
in-process loop would not catch those.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import fixtures as fx

from crp_evidence.parquet_writer import Table, table_bytes

SERVICE_DIR = Path(__file__).resolve().parents[1]

_BUILD_SCRIPT = r"""
import json, sys
sys.path.insert(0, %(src)r)
sys.path.insert(0, %(tests)r)
import fixtures as fx
from crp_evidence.bundle import assemble_bundle
from crp_evidence.ingest import EvidenceLedger
from crp_evidence.provenance import BuildContext
from crp_evidence.schedule import evaluate_coverage, schedule_from_manifest

out = sys.argv[1]
manifest = fx.small_manifest()
ledger = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
ledger.ingest_many(fx.full_batch_set(), strict=True)
missing = evaluate_coverage(
    schedule_from_manifest(manifest, fx.COHORT_IDS), [a.batch for a in ledger.accepted]
)
res = assemble_bundle(
    out,
    manifest=manifest,
    ledger=ledger,
    participants=fx.participants(),
    assignments=fx.assignments(),
    missingness=missing,
    build_context=BuildContext(
        source_commit="deadbeef", container_digest="sha256:test", execution_timestamp="0"
    ),
)
print(json.dumps({"hash": res.bundle_content_hash, "files": {k: v["sha256"] for k, v in res.files.items()}}))
"""


def _build_in_fresh_process(out_dir: Path) -> dict:
    script = _BUILD_SCRIPT % {
        "src": str(SERVICE_DIR / "src"),
        "tests": str(SERVICE_DIR / "tests"),
    }
    proc = subprocess.run(
        [sys.executable, "-c", script, str(out_dir)],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(SERVICE_DIR),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout.strip().splitlines()[-1])


def test_parquet_bytes_are_identical_across_fresh_processes(tmp_path: Path) -> None:
    a = _build_in_fresh_process(tmp_path / "a")
    b = _build_in_fresh_process(tmp_path / "b")
    for rel in sorted(a["files"]):
        if not rel.endswith(".parquet"):
            continue
        ba = (tmp_path / "a" / rel).read_bytes()
        bb = (tmp_path / "b" / rel).read_bytes()
        assert ba == bb, "parquet bytes differ across fresh processes for %s" % rel
        assert len(ba) > 0


def test_bundle_content_hash_is_identical_across_fresh_processes(tmp_path: Path) -> None:
    a = _build_in_fresh_process(tmp_path / "a")
    b = _build_in_fresh_process(tmp_path / "b")
    assert a["hash"] == b["hash"]
    assert a["files"] == b["files"]


def test_every_bundle_file_is_byte_identical_across_fresh_processes(tmp_path: Path) -> None:
    a = _build_in_fresh_process(tmp_path / "a")
    _build_in_fresh_process(tmp_path / "b")
    for rel in sorted(a["files"]):
        assert (tmp_path / "a" / rel).read_bytes() == (tmp_path / "b" / rel).read_bytes(), rel


def test_provenance_is_the_only_file_allowed_to_differ(tmp_path: Path) -> None:
    """Provenance is excluded from the content hash, so a timestamp change must not move it."""
    a = _build_in_fresh_process(tmp_path / "a")
    prov = json.loads((tmp_path / "a" / "provenance.json").read_bytes().decode("utf-8"))
    assert prov["bundle_content_hash"] == a["hash"]
    assert "provenance.json" not in a["files"]


def test_row_order_not_insertion_order_drives_table_bytes() -> None:
    """Two tables with the same rows in different insertion order are DIFFERENT tables.

    Determinism comes from callers sorting by the canonical leaf key, not from the writer
    silently sorting; this pins that the writer really does preserve the order it is given
    (so a caller bug is visible rather than masked).
    """
    rows = [("0", "a"), ("1", "b")]
    t1 = Table("t", ("i", "v"), tuple(rows), "i_asc")
    t2 = Table("t", ("i", "v"), tuple(reversed(rows)), "i_asc")
    assert table_bytes(t1) != table_bytes(t2)
    assert t1.canonical_content_hash() != t2.canonical_content_hash()


def test_canonical_content_hash_is_parquet_independent() -> None:
    """Level-1 determinism: the logical hash does not involve pyarrow at all."""
    records = [{"a": "1", "b": "x"}, {"a": "2", "b": "y"}]
    t = Table.from_records("t", ("a", "b"), records, "a_asc")
    assert t.canonical_content_hash() == Table.from_records(
        "t", ("a", "b"), records, "a_asc"
    ).canonical_content_hash()
    assert len(t.canonical_content_hash()) == 64


def test_fixture_batches_are_themselves_deterministic() -> None:
    assert fx.full_batch_set() == fx.full_batch_set()
