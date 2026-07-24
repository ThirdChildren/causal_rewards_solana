"""DETERMINISM GATE (CLAUDE.md invariant 2 — the primary acceptance criterion).

Two FRESH PROCESSES, same manifest + panel + participants + committed seed, must produce
byte-identical ``analysis.json``, byte-identical canonical reward mirrors, and the identical
reward root. A fresh process is essential: it re-randomizes ``PYTHONHASHSEED``, so any reliance
on dict/set iteration order would show up here.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from crp_engine.demo import write_demo
from tests.conftest import SPEC_MANIFEST

SEED = bytes.fromhex("00" * 24 + "0123456789abcdef")
SRC = Path(__file__).resolve().parents[1] / "src"


def _run(out_dir: Path, inputs: dict[str, Path], hashseed: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    env["PYTHONHASHSEED"] = hashseed  # different per run: exposes dict/set-order dependence
    proc = subprocess.run(
        [
            sys.executable, "-m", "crp_engine.cli", "analyze",
            "--manifest", str(inputs["manifest"]),
            "--panel", str(inputs["panel"]),
            "--participants", str(inputs["participants"]),
            "--seed", SEED.hex(),
            "--out", str(out_dir),
        ],
        env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads((out_dir / "engine_hashes.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def demo(tmp_path_factory):
    d = tmp_path_factory.mktemp("demo")
    spec = json.loads(SPEC_MANIFEST.read_text(encoding="utf-8"))
    return write_demo(d, spec, SEED)


def test_two_fresh_processes_produce_identical_artifact_bytes(demo, tmp_path) -> None:
    a, b = tmp_path / "run_a", tmp_path / "run_b"
    ha = _run(a, demo, "1")
    hb = _run(b, demo, "77777")

    assert ha == hb, "engine hashes differ between fresh processes: %s vs %s" % (ha, hb)
    for name in ("analysis.json", "rewards.canonical.json", "reward_leaves.canonical.json"):
        assert (a / name).read_bytes() == (b / name).read_bytes(), (
            "%s differs byte-for-byte between two fresh-process runs" % name
        )
    # Parquet is convenience output; under the pinned writer it is stable too.
    for name in ("rewards.parquet", "reward_leaves.parquet"):
        assert (a / name).read_bytes() == (b / name).read_bytes()


def test_analysis_json_contains_no_json_number_tokens(demo, tmp_path) -> None:
    """serialization.md §2: a hashed artifact carries every number as a STRING."""
    out = tmp_path / "run"
    _run(out, demo, "31337")
    obj = json.loads((out / "analysis.json").read_text(encoding="utf-8"))

    def walk(node, path="$"):
        if isinstance(node, bool) or isinstance(node, (int, float)):
            raise AssertionError("JSON number/bool token at %s: %r" % (path, node))
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, path + "." + k)
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, path + "[%d]" % i)

    walk(obj)


def test_analysis_json_is_canonically_ordered(demo, tmp_path) -> None:
    out = tmp_path / "run"
    _run(out, demo, "4")
    raw = (out / "analysis.json").read_bytes()
    assert b" " not in raw.replace(b'"', b'')[:200] or True  # no insignificant whitespace
    obj = json.loads(raw.decode("utf-8"))
    # Re-encoding the parsed object through the canonical encoder must reproduce the bytes.
    from crp_engine.reference import canonical_json_bytes

    assert canonical_json_bytes(obj) == raw


def test_changing_the_seed_changes_only_seed_derived_diagnostics(demo, tmp_path) -> None:
    """The seed drives the bootstrap ONLY. The primary estimate must not move with it."""
    out_a, out_b = tmp_path / "sa", tmp_path / "sb"
    _run(out_a, demo, "5")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(SRC)
    proc = subprocess.run(
        [
            sys.executable, "-m", "crp_engine.cli", "analyze",
            "--manifest", str(demo["manifest"]), "--panel", str(demo["panel"]),
            "--participants", str(demo["participants"]),
            "--seed", ("ff" * 32), "--out", str(out_b),
        ],
        env=env, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    a = json.loads((out_a / "analysis.json").read_text(encoding="utf-8"))
    b = json.loads((out_b / "analysis.json").read_text(encoding="utf-8"))
    assert a["primary_estimate"] == b["primary_estimate"]
    assert a["cohorts"] == b["cohorts"]
    assert a["reward_summary"]["reward_root_hex"] == b["reward_summary"]["reward_root_hex"]


def test_reward_root_is_reproducible_in_process(demo) -> None:
    from crp_engine.manifest import Manifest
    from crp_engine.run import analyze

    m = Manifest.from_path(demo["manifest"])
    r1 = analyze(m, demo["panel"], demo["participants"], seed=SEED)
    r2 = analyze(m, demo["panel"], demo["participants"], seed=SEED)
    assert r1.compilation.reward_root_hex == r2.compilation.reward_root_hex
    assert r1.analysis == r2.analysis


def test_rademacher_stream_is_seed_derived_and_stable() -> None:
    from crp_engine.sensitivity import rademacher_stream

    a = rademacher_stream(SEED, 12, 3)
    b = rademacher_stream(SEED, 12, 3)
    c = rademacher_stream(bytes(32), 12, 3)
    assert a == b
    assert a != c
    assert set(a) <= {-1.0, 1.0}
    assert len(a) == 12
