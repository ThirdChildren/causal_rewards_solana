"""The happy path: a real assembled bundle must PASS every check."""

from __future__ import annotations

from pathlib import Path

from crp_verifier.bundle import Bundle
from crp_verifier.checks import FAIL, PASS, SKIP, run_all


def test_every_check_passes(golden_bundle: Path) -> None:
    results = run_all(Bundle(golden_bundle))
    by_name = {r.name: r for r in results}
    # No check may FAIL on a valid bundle.
    assert not [r.name for r in results if r.status == FAIL]
    # These roots must be positively REPRODUCED (not skipped).
    for name in ("manifest_hash", "assignment_root", "evidence_epoch_roots",
                 "result_artifact_hash", "reward_root"):
        assert by_name[name].status == PASS, (name, by_name[name].summary)


def test_reproduces_the_golden_roots(golden_bundle: Path) -> None:
    b = Bundle(golden_bundle)
    r = b.roots["roots"]
    assert b.roots["manifest_hash"].startswith("74e0bb82")
    assert r["assignment_root_hex"].startswith("c229b5cc")
    assert r["evidence_epochs"][0]["evidence_epoch_root_hex"].startswith("a13e1cdc")
    assert r["reward_root_hex"].startswith("a9c35cf4")


def test_onchain_cross_check_passes_for_matching_anchors(golden_bundle: Path) -> None:
    b = Bundle(golden_bundle)
    r = b.roots["roots"]
    onchain = {
        "manifest_hash": b.roots["manifest_hash"],
        "cohort_root": r["assignment_root_hex"],
        "reward_root": r["reward_root_hex"],
    }
    results = run_all(b, onchain=onchain)
    oc = next(x for x in results if x.name == "onchain_commitments")
    assert oc.status == PASS
    assert not [x for x in results if x.status == FAIL]
