"""CLI contract: exit codes, report shape, and argument handling."""

from __future__ import annotations

import io
from pathlib import Path

from crp_verifier.cli import EXIT_BUNDLE_ERROR, EXIT_OK, EXIT_USAGE, main


def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    rc = main(argv, out=out, err=err)
    return rc, out.getvalue(), err.getvalue()


def test_happy_bundle_exits_zero(golden_bundle: Path) -> None:
    rc, out, _ = _run([str(golden_bundle)])
    assert rc == EXIT_OK
    assert "verdict: ACCEPT" in out
    assert "[PASS] manifest_hash" in out
    assert "[PASS] reward_root" in out


def test_json_output_is_byte_stable(golden_bundle: Path) -> None:
    rc1, out1, _ = _run([str(golden_bundle), "--json"])
    rc2, out2, _ = _run([str(golden_bundle), "--json"])
    assert rc1 == rc2 == EXIT_OK
    assert out1 == out2
    assert out1.startswith("{") and '"verdict":"ACCEPT"' in out1


def test_missing_bundle_dir_is_bundle_error(tmp_path: Path) -> None:
    rc, _, err = _run([str(tmp_path / "does-not-exist")])
    assert rc == EXIT_BUNDLE_ERROR
    assert "not a directory" in err


def test_bad_seed_hex_is_usage_error(golden_bundle: Path) -> None:
    rc, _, err = _run([str(golden_bundle), "--seed", "xyz"])
    assert rc == EXIT_USAGE
    assert "--seed" in err


def test_onchain_mismatch_exits_nonzero(golden_bundle: Path, tmp_path: Path) -> None:
    oc = tmp_path / "oc.json"
    oc.write_text('{"reward_root":"%s"}' % ("de" * 32))
    rc, out, _ = _run([str(golden_bundle), "--onchain", str(oc)])
    assert rc != 0
    assert "verdict: REJECT" in out
