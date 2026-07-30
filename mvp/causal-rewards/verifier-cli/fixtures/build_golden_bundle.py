"""Assemble a REAL audit bundle out of the ratified golden test-vectors + reference encoder.

This is not a synthetic mock: every table row and every root written here is the exact
byte-content the shared ``test-vectors/`` fixtures pin (which the on-chain programs, the
causal engine, the backend pipeline and the SDKs are all checked against). The verifier,
run over the assembled bundle, then RE-DERIVES those same roots from first principles —
so a green run is an end-to-end reproduction, not a tautology.

The happy-path bundle binds, in one audit bundle:

* ``manifest.json``        PINNED v1.1 manifest bytes (fixtures/pinned/…) canonical -> 74e0bb82…
* ``assignment.parquet``   assign-01-bernoulli-p50 leaves           -> c229b5cc…
* ``evidence/epoch-*``     evidence-01 / -02 / -03 ordered leaves   -> a13e1cdc / e45697c8 / 1010891b
* ``analysis.json``        binds the 3 epoch roots (the seam) + reward root
* ``rewards.parquet``      reward-01-multi-recipient-ordering       -> a9c35cf4…
* ``roots.json``           every anchored root + the file index
* ``provenance.json``      source commit / container digest / fixed timestamp (no clock)

Run ``python build_golden_bundle.py <dest>`` to (re)generate the committed happy-path
bundle. Adversarial variants are derived from it by :mod:`build_adversarial` in the tests.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

# Locate the reference encoder (single source of canonical bytes) and the repo root.
FIXTURES_DIR = Path(__file__).resolve().parent
VERIFIER_CLI = FIXTURES_DIR.parent
REPO = VERIFIER_CLI.parent
REFERENCE = VERIFIER_CLI / "reference"
if str(REFERENCE) not in sys.path:
    sys.path.insert(0, str(REFERENCE))

import canonical  # noqa: E402
import merkle  # noqa: E402

VECTORS = REPO / "test-vectors"

MANIFEST_HASH_PREFIX = "74e0bb82"
EXPERIMENT_ID = "env-sensors-pilot-001"

# PIN (task #8): frozen v1.1 manifest bytes for the golden-happy bundle. Sourced from a
# dedicated pinned fixture — NOT from the live specs/examples/manifest.example.json, which
# protocol-architect advanced to v1.2 (ba632e8a). The golden bundle stays at 74e0bb82 until
# the v1.2 fan-out migration (task #8) deliberately regenerates it.
PINNED_MANIFEST_V1_1 = FIXTURES_DIR / "pinned" / "manifest.golden-happy.v1_1.json"


def _load(rel: str) -> Any:
    return json.loads((VECTORS / rel).read_bytes().decode("utf-8"))


def _write_parquet(path: Path, columns: dict[str, list[str]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({name: pa.array(vals, type=pa.string()) for name, vals in columns.items()})
    path.parent.mkdir(parents=True, exist_ok=True)
    # Deterministic write settings; the verifier reads only logical content, so verdict is
    # independent of these, but a stable file keeps the committed fixture byte-reproducible.
    pq.write_table(table, path, compression="none", write_statistics=False)


def _epoch_leaf_hashes(vector_rel: str) -> list[str]:
    """Ordered ``leaf_hash_hex`` list from an evidence vector (already ascending)."""
    v = _load(vector_rel)
    return [str(l["leaf_hash_hex"]) for l in v["ordered_leaves"]]


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def build(dest: Path) -> Path:
    """Assemble the happy-path bundle at ``dest`` (recreated). Returns ``dest``."""
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)

    # -- manifest.json: canonical bytes of the PINNED v1.1 manifest (golden 74e0bb82) ------
    # PIN (task #8): the golden-happy bundle is a FROZEN v1.1 audit bundle and must stay
    # reproducible at manifest 74e0bb82 (CJSON 3852 bytes). We deliberately DO NOT read the
    # live specs/examples/manifest.example.json here: protocol-architect ratified v1.2 (adds
    # design.parameters.missingness_policy), moving that mutable spec example to ba632e8a
    # (3886 bytes). A golden fixture must be PINNED, not regenerated from a source file that
    # can drift under it. The v1.2 fan-out migration (task #8) is the ONLY thing that should
    # advance this bundle from 74e0bb82 -> ba632e8a; until then this pin holds it at v1.1.
    manifest = json.loads(PINNED_MANIFEST_V1_1.read_bytes().decode("utf-8"))
    manifest_bytes = canonical.canonical_json_bytes(manifest)
    manifest_hash = canonical.sha256_hex(manifest_bytes)
    _assert(manifest_hash.startswith(MANIFEST_HASH_PREFIX),
            "manifest hash drifted from golden: %s" % manifest_hash)
    (dest / "manifest.json").write_bytes(manifest_bytes)

    # -- assignment.parquet: assign-01 leaves -> c229b5cc… --------------------------------
    va = _load("assignment/assign-01-bernoulli-p50/vector.json")
    a_leaves = va["step4_leaves"]["leaves"]
    assignment_root = str(va["step5_assignment_root"]["assignment_root_hex"])
    _write_parquet(
        dest / "assignment.parquet",
        {
            "cohort_id": [str(l["cohort_id"]) for l in a_leaves],
            "arm": [str(l["arm"]) for l in a_leaves],
            "prf_u64": [str(l["prf_u64"]) for l in a_leaves],
            "leaf_hash_hex": [str(l["leaf_hash_hex"]) for l in a_leaves],
        },
    )

    # -- evidence epoch: evidence-01 batch-epoch tree -> a13e1cdc… ------------------------
    # Only the batch-epoch vector (evidence-01) is a genuine EPOCH tree: its leaves are
    # signed batch headers ordered by leaf_hash — exactly the ordering the epoch check
    # enforces. evidence-02/-03 are signer-set / observation SUB-trees ordered by a be32
    # key (not leaf_hash) and belong INSIDE a batch, not as epochs; the verifier reproduces
    # those two roots through the reference oracle in the golden-roots conformance test.
    evidence_specs = [("evidence/evidence-01-epoch-multibatch.json", "a13e1cdc")]
    epoch_entries: list[dict[str, str]] = []
    epoch_roots: list[str] = []
    for i, (rel, prefix) in enumerate(evidence_specs):
        leaf_hashes = _epoch_leaf_hashes(rel)
        root = merkle.merkle_root_from_hashes([bytes.fromhex(h) for h in leaf_hashes]).hex()
        _assert(root.startswith(prefix), "evidence epoch %d root drift: %s" % (i, root))
        fname = "evidence/epoch-%06d.parquet" % i
        _write_parquet(dest / fname, {"leaf_hash_hex": leaf_hashes})
        epoch_entries.append({"epoch_index": str(i), "file": fname, "evidence_epoch_root_hex": root})
        epoch_roots.append(root)

    # -- rewards.parquet: reward-01 leaves -> a9c35cf4… ----------------------------------
    vr = _load("reward/reward-01-multi-recipient-ordering.json")
    r_leaves = vr["leaves"]
    reward_root = str(vr["reward_root_hex"])
    _write_parquet(
        dest / "rewards.parquet",
        {
            "leaf_index": [str(l["leaf_index"]) for l in r_leaves],
            "recipient_hex": [str(l["recipient_hex"]) for l in r_leaves],
            "amount_base_units": [str(l["amount_base_units"]) for l in r_leaves],
            "leaf_hash_hex": [str(l["leaf_hash_hex"]) for l in r_leaves],
        },
    )

    # -- analysis.json: binds the epoch roots (the evidence<->result seam) + reward root --
    container_digest = str((manifest.get("analysis_plan") or {}).get("analysis_container_digest"))
    analysis = {
        "spec_version": "1.1.0",
        "experiment_id": EXPERIMENT_ID,
        "engine": {"analysis_container_digest": container_digest, "name": "crp-causal-engine"},
        "estimand": "cohort_ate_rmse_delta",
        "evidence_epoch_roots": epoch_roots,
        "primary_effect": {
            "point_estimate_micro": "125000",
            "standard_error_micro": "40000",
            "conservative_effect_micro": "59200",
        },
        "reward_summary": {"reward_root_hex": reward_root, "total_base_units": "250"},
    }
    analysis_bytes = canonical.canonical_json_bytes(analysis)
    result_artifact_hash = canonical.sha256_hex(analysis_bytes)
    (dest / "analysis.json").write_bytes(analysis_bytes)

    # -- roots.json: the untrusted claim the verifier must reproduce ----------------------
    roots = {
        "bundle_layout_version": "1.0.0",
        "manifest_hash": manifest_hash,
        "roots": {
            "assignment_root_hex": assignment_root,
            "evidence_epochs": epoch_entries,
            "reward_root_hex": reward_root,
            "result_artifact_hash": result_artifact_hash,
        },
    }
    (dest / "roots.json").write_bytes(canonical.canonical_json_bytes(roots))

    # -- provenance.json: EXCLUDED from hashes; fixed timestamp (no wall-clock) -----------
    provenance = {
        "source_commit": "0000000000000000000000000000000000000000",
        "container_digest": container_digest,
        "execution_timestamp": "0",
        "manifest_hash": manifest_hash,
        "reference_note": "roots reproduced from ratified test-vectors via verifier-cli/reference",
    }
    (dest / "provenance.json").write_bytes(canonical.canonical_json_bytes(provenance))

    return dest


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    dest = Path(args[0]) if args else (FIXTURES_DIR / "bundles" / "golden-happy")
    build(dest.resolve())
    print("assembled golden bundle at %s" % dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
