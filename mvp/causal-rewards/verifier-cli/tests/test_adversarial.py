"""The verifier must REJECT bad bundles, not merely accept good ones.

Two layers:

1. Bundle tampers derived from the real golden bundle — ``crp-verify`` must exit non-zero
   and localize the fault (substituted reward root, tampered manifest/result, duplicate
   evidence leaf, non-monotonic epoch index, container-digest mismatch, evidence↔result
   seam break, invalid seed reveal).
2. The shared ``test-vectors/adversarial/`` fixtures (adv-01..06) — every one must be
   rejected by :func:`crp_verifier.adversarial.evaluate_fixture`, recomputed from inputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from crp_verifier import _ref
from crp_verifier.adversarial import BUNDLE, evaluate_fixture
from crp_verifier.bundle import Bundle
from crp_verifier.checks import FAIL, run_all
from crp_verifier.cli import main as cli_main

import conftest as C

ADV_DIR = C.REPO / "test-vectors" / "adversarial"


def _run(bundle_dir: Path, **kw) -> list:
    return run_all(Bundle(bundle_dir), **kw)


def _first_fail(results: list):
    fails = [r for r in results if r.status == FAIL]
    assert fails, "expected at least one FAIL, got: %s" % [(r.name, r.status) for r in results]
    return fails[0]


# ------------------------------------------------------------------ bundle-level rejections


def test_substituted_reward_root(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "sub-reward")
    cols = C.read_parquet_columns(d / "rewards.parquet")
    cols["amount_base_units"][0] = str(int(cols["amount_base_units"][0]) + 1)  # steal 1 unit
    C.write_parquet_columns(d / "rewards.parquet", cols)
    fail = _first_fail(_run(d))
    assert fail.name == "reward_root"


def test_tampered_manifest(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "tamper-manifest")
    m = C.read_json(d / "manifest.json")
    m["title"] = str(m.get("title", "")) + " (tampered)"
    C.write_canonical(d / "manifest.json", m)  # canonical bytes, but hash now != roots.json
    fail = _first_fail(_run(d))
    assert fail.name == "manifest_hash"


def test_tampered_result_artifact(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "tamper-result")
    a = C.read_json(d / "analysis.json")
    a["primary_effect"]["point_estimate_micro"] = "999999"  # cook the result
    C.write_canonical(d / "analysis.json", a)
    fail = _first_fail(_run(d))
    # result hash in roots.json no longer matches; seam still intact so this is the divergence.
    assert fail.name == "result_artifact_hash"


def test_seam_break_analysis_roots_ne_evidence(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "seam-break")
    a = C.read_json(d / "analysis.json")
    a["evidence_epoch_roots"] = ["00" * 32]  # analysis claims evidence it did not consume
    C.write_canonical(d / "analysis.json", a)
    C.resync_result_hash(d)  # self-consistent attacker: the seam is the only remaining fault
    fail = _first_fail(_run(d))
    assert fail.name == "result_artifact_hash"
    assert "SEAM BREAK" in fail.summary


def test_duplicate_evidence_leaf(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "dup-leaf")
    cols = C.read_parquet_columns(d / "evidence" / "epoch-000000.parquet")
    cols["leaf_hash_hex"][1] = cols["leaf_hash_hex"][0]  # replay batch 0 as batch 1
    C.write_parquet_columns(d / "evidence" / "epoch-000000.parquet", cols)
    fail = _first_fail(_run(d))
    assert fail.name == "evidence_epoch_roots"
    assert "DUPLICATE_EVIDENCE_LEAF" in fail.summary


def test_non_monotonic_epoch_index(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "dup-epoch")
    roots = C.read_json(d / "roots.json")
    ep0 = roots["roots"]["evidence_epochs"][0]
    # anchor a second epoch that RE-USES epoch_index 0 (replay of an already-anchored epoch).
    dup = dict(ep0)
    dup["file"] = "evidence/epoch-000001.parquet"
    roots["roots"]["evidence_epochs"].append(dup)
    C.write_canonical(d / "roots.json", roots)
    import shutil
    shutil.copy(d / "evidence" / "epoch-000000.parquet", d / "evidence" / "epoch-000001.parquet")
    fail = _first_fail(_run(d))
    assert fail.name == "evidence_epoch_roots"
    assert "EPOCH_INDEX_NOT_MONOTONIC" in fail.summary


def test_container_digest_mismatch(golden_bundle: Path, tmp_path: Path) -> None:
    d = C.copy_bundle(golden_bundle, tmp_path / "container")
    a = C.read_json(d / "analysis.json")
    a["engine"]["analysis_container_digest"] = "sha256:" + "cd" * 32  # stale/substituted container
    C.write_canonical(d / "analysis.json", a)
    C.resync_result_hash(d)  # self-consistent attacker: the container digest is the only fault
    fail = _first_fail(_run(d))
    assert fail.name == "result_artifact_hash"
    assert "container" in fail.summary.lower()


# ------------------------------------------------------------------ seed-reveal (invariant 1)


def _seed_bundle(src: Path, dst: Path) -> Path:
    """Derive a bundle whose manifest carries the assign-01 seed commitment + design/params,
    so the assignment derivation leg runs against a supplied --seed."""
    d = C.copy_bundle(src, dst)
    va = json.loads((C.VECTORS / "assignment" / "assign-01-bernoulli-p50" / "vector.json")
                    .read_bytes().decode("utf-8"))
    m = C.read_json(d / "manifest.json")
    m["experiment_id"] = va["inputs"]["experiment_id"]
    m["assignment"] = {
        "seed_commitment": {
            "algo": "sha256",
            "scheme": 'sha256("CRP-seed-commit-v1"||seed_32)',
            "commitment_hex": va["step1_seed_commitment"]["seed_commitment_hex"],
        },
        "design": va["inputs"]["design"],
        "params": va["inputs"]["params"],
    }
    C.write_canonical(d / "manifest.json", m)
    # roots.json manifest_hash + analysis experiment_id must follow the rewritten manifest.
    import canonical
    mh = canonical.sha256_hex((d / "manifest.json").read_bytes())
    roots = C.read_json(d / "roots.json")
    roots["manifest_hash"] = mh
    C.write_canonical(d / "roots.json", roots)
    a = C.read_json(d / "analysis.json")
    a["experiment_id"] = va["inputs"]["experiment_id"]
    C.write_canonical(d / "analysis.json", a)
    C.resync_result_hash(d)  # keep the (now-rewritten) analysis.json self-consistent
    prov = C.read_json(d / "provenance.json")
    prov["manifest_hash"] = mh
    C.write_canonical(d / "provenance.json", prov)
    return d


def test_invalid_seed_reveal_rejected(golden_bundle: Path, tmp_path: Path) -> None:
    d = _seed_bundle(golden_bundle, tmp_path / "seed-bad")
    wrong = bytes.fromhex("11" * 32)  # does NOT open the frozen commitment (adv-01)
    fail = _first_fail(_run(d, revealed_seed=wrong))
    assert fail.name == "assignment_root"
    assert "seed_commitment" in fail.summary


def test_correct_seed_reveal_fully_derives_arms(golden_bundle: Path, tmp_path: Path) -> None:
    d = _seed_bundle(golden_bundle, tmp_path / "seed-good")
    correct = bytes(32)  # assign-01 seed
    results = _run(d, revealed_seed=correct)
    assert not [r for r in results if r.status == FAIL]
    asg = next(r for r in results if r.name == "assignment_root")
    assert "reproduced from the revealed seed" in asg.summary


# ------------------------------------------------------------------ shared adversarial fixtures


@pytest.mark.parametrize(
    "fixture_file",
    sorted(p.name for p in ADV_DIR.glob("adv-*.json")),
)
def test_shared_adversarial_fixture_rejected(fixture_file: str) -> None:
    fx = json.loads((ADV_DIR / fixture_file).read_bytes().decode("utf-8"))
    verdict = evaluate_fixture(fx)
    assert verdict.rejected, "%s should be rejected: %s" % (fixture_file, verdict.detail)
    assert verdict.code == fx["rejection_code"]


def test_cli_exits_nonzero_on_tamper(golden_bundle: Path, tmp_path: Path) -> None:
    import io

    d = C.copy_bundle(golden_bundle, tmp_path / "cli-nonzero")
    cols = C.read_parquet_columns(d / "rewards.parquet")
    cols["amount_base_units"][0] = "999999999"
    C.write_parquet_columns(d / "rewards.parquet", cols)
    rc = cli_main([str(d)], out=io.StringIO(), err=io.StringIO())
    assert rc != 0
