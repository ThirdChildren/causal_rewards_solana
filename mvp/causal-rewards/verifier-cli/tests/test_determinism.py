"""Determinism: the verdict itself must be reproducible byte-for-byte.

Two independent runs on the same bundle — text and JSON — must emit identical bytes, and a
re-assembled bundle must reproduce identical roots. The verifier reads no wall-clock and no
RNG, so any diff here is a determinism bug (the exact thing this agent exists to catch).
"""

from __future__ import annotations

import io
from pathlib import Path

from crp_verifier.cli import main

import conftest as C


def _capture(argv) -> str:
    out = io.StringIO()
    main(argv, out=out, err=io.StringIO())
    return out.getvalue()


def test_two_text_runs_identical(golden_bundle: Path) -> None:
    a = _capture([str(golden_bundle)])
    b = _capture([str(golden_bundle)])
    assert a == b


def test_two_json_runs_identical(golden_bundle: Path) -> None:
    a = _capture([str(golden_bundle), "--json"])
    b = _capture([str(golden_bundle), "--json"])
    assert a == b


def test_reassembled_bundle_reproduces_identical_roots(tmp_path: Path) -> None:
    d1 = C.BUILDER.build(tmp_path / "b1")
    d2 = C.BUILDER.build(tmp_path / "b2")
    assert (d1 / "roots.json").read_bytes() == (d2 / "roots.json").read_bytes()
    assert (d1 / "manifest.json").read_bytes() == (d2 / "manifest.json").read_bytes()
    assert (d1 / "analysis.json").read_bytes() == (d2 / "analysis.json").read_bytes()
