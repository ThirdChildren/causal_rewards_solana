#!/usr/bin/env python3
"""Assemble REAL audit bundles for the dashboard to render, using the actual causal engine.

Why this exists: `verifier-cli/fixtures/bundles/golden-happy` is a genuine verified bundle,
but its `analysis.json` is the minimal seam-binding shape. The dashboard has to render the
*normative* engine artifact — per-cohort conservative bounds, exclusions, balance,
sensitivity — and, critically, a NULL result (invariant 8) as a first-class outcome rather
than an error. So we run `crp_engine` for real and assemble bundles around its output.

Nothing here is mocked. Every root is produced by the ratified reference encoder in
`verifier-cli/reference/`, and each assembled bundle is expected to pass `crp-verify`.
This script only READS `causal-engine/` and `verifier-cli/`; it writes only into
`dashboard/fixtures/bundles/`.

Determinism: the only entropy is the committed seed. No wall-clock, no OS randomness.

Usage (from the repo root, needs the causal-engine venv for numpy/pandas/pyarrow/scipy):

    causal-engine/.venv/bin/python dashboard/scripts/build_demo_bundles.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DASHBOARD = HERE.parent
REPO = DASHBOARD.parent
ENGINE_SRC = REPO / "causal-engine" / "src"
REFERENCE = REPO / "verifier-cli" / "reference"
SPECS = REPO / "specs"
DEST_ROOT = DASHBOARD / "fixtures" / "bundles"

for p in (str(ENGINE_SRC), str(REFERENCE)):
    if p not in sys.path:
        sys.path.insert(0, p)

import canonical  # noqa: E402  (verifier-cli/reference)
import evidence as ref_evidence  # noqa: E402
import merkle  # noqa: E402
from assignment import (  # noqa: E402
    CohortAssignment,
    derive_assignment,
    seed_commitment,
)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from crp_engine.demo import build_manifest, build_participants  # noqa: E402
from crp_engine.manifest import Manifest  # noqa: E402
from crp_engine.run import analyze, write_all  # noqa: E402

PARQUET_KW = dict(compression="none", write_statistics=False)


# ---------------------------------------------------------------------------- scenarios

class Scenario:
    def __init__(self, bundle_id: str, experiment_id: str, title: str, description: str,
                 true_effect: float, seed_hex: str, noise: float = 0.04,
                 min_observations_per_cohort: str = "2000") -> None:
        self.bundle_id = bundle_id
        self.experiment_id = experiment_id
        self.title = title
        self.description = description
        self.true_effect = true_effect
        self.noise = noise
        self.min_observations_per_cohort = min_observations_per_cohort
        self.seed = bytes.fromhex(seed_hex)


def build_noisy_panel(seed: bytes, *, n_cohorts: int = 24, n_blocks: int = 24,
                      true_effect: float = 0.12, noise: float = 0.04):
    """`crp_engine.demo.build_panel` with the within-block noise exposed.

    Identical draw order to the engine's own demo panel, so the null scenarios differ from the
    signal scenario only in the two parameters we vary — not in how the data were generated.
    """
    import numpy as np
    import pandas as pd

    rng = np.random.default_rng(int.from_bytes(seed[-8:], "big"))
    rows = []
    for c in range(n_cohorts):
        cohort_shock = float(rng.normal(0.0, 0.30))
        phase = int(rng.integers(0, 2))
        eff = true_effect * float(rng.lognormal(0.0, 0.25))
        for t in range(n_blocks):
            treated = ((t + phase) % 2) == 1
            rows.append(
                {
                    "cohort_id": "geo%02d" % c,
                    "time_block": t,
                    "arm": "treatment" if treated else "control",
                    "outcome": 1.0
                    + cohort_shock
                    - (eff if treated else 0.0)
                    + float(rng.normal(0.0, noise)),
                    "n_units": int(6 + rng.integers(0, 10)),
                    "n_observations": int(200 + rng.integers(0, 200)),
                }
            )
    return pd.DataFrame(rows)


SCENARIOS = [
    Scenario(
        bundle_id="demo-signal",
        experiment_id="env-sensors-demo-signal",
        title="Sensor additionality — measurable effect",
        description=(
            "Switchback-shaped shadow-mode evaluation of whether including a geo-cohort's "
            "signed observations causes a reduction in held-out prediction error. The live "
            "prediction service is never degraded. Cohort-level estimand only."
        ),
        true_effect=0.12,
        seed_hex="00" * 24 + "0123456789abcdef",
    ),
    Scenario(
        bundle_id="demo-null",
        experiment_id="env-sensors-demo-null",
        title="Sensor additionality — no detectable effect",
        description=(
            "The same frozen design applied to a period with no true effect. The pooled "
            "estimate is indistinguishable from zero, and almost every cohort's conservative "
            "bound is zero, so almost the whole budget stays recoverable. The few cohorts that "
            "do clear their bound are what per-cohort testing without a family-wise correction "
            "looks like on null data — read the multiplicity note alongside the table."
        ),
        true_effect=0.0,
        noise=1.20,
        seed_hex="00" * 24 + "fedcba9876543210",
    ),
    Scenario(
        bundle_id="demo-low-power",
        experiment_id="env-sensors-demo-low-power",
        title="Sensor additionality — underpowered period",
        description=(
            "A period in which too few cohorts met the frozen minimum-sample rule. The frozen "
            "analysis plan requires 10 eligible cohorts; below that the engine compiles a null "
            "distribution by design rather than paying out on an underpowered estimate."
        ),
        true_effect=0.12,
        noise=0.04,
        min_observations_per_cohort="9000",
        seed_hex="00" * 24 + "0f1e2d3c4b5a6978",
    ),
]


# ------------------------------------------------------------------------------ helpers

def write_parquet(path: Path, columns: dict[str, list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.table({k: pa.array(v, type=pa.string()) for k, v in columns.items()})
    pq.write_table(table, path, **PARQUET_KW)


def build_scenario_manifest(sc: Scenario) -> dict:
    """The demo manifest, re-pinned to this scenario's seed commitment and derivation params.

    `assignment.design` / `assignment.params` are the machine-readable derivation descriptor
    the verifier needs to re-derive every arm from the revealed seed. The manifest schema does
    not yet pin a canonical location for them (known SPEC GAP, tracked by protocol-architect);
    without them `crp-verify` downgrades the assignment check to structural-only. We include
    them so the freeze-before-reveal leg (invariant 1) actually runs on these bundles.
    """
    example = json.loads((SPECS / "examples" / "manifest.example.json").read_bytes().decode())
    obj = build_manifest(example)
    obj["experiment_id"] = sc.experiment_id
    obj["title"] = sc.title
    obj["description"] = sc.description
    obj["network"] = {"cluster": "devnet"}
    obj["analysis_plan"]["minimum_sample"]["min_observations_per_cohort"] = (
        sc.min_observations_per_cohort
    )
    treat_ppm = str(int(obj["treatment"]["treated_fraction_micro"]))
    obj["assignment"] = {
        "seed_commitment": {
            "algo": "sha256",
            "scheme": 'sha256("CRP-seed-commit-v1"||seed_32)',
            "commitment_hex": seed_commitment(sc.seed).hex(),
        },
        "design": "bernoulli",
        "params": {"treat_fraction_ppm": treat_ppm},
    }
    return obj


def build_evidence_epochs(sc: Scenario, cohort_ids: list[str], dest: Path,
                          n_epochs: int = 2) -> tuple[list[dict], list[str]]:
    """One epoch tree per anchored evidence epoch, over schema-shaped signed batch headers.

    The epoch parquet carries the batch-header fields the Evidence view renders (cohort,
    time range, signer-set and observation sub-commitments, accepted/rejected counts) next to
    the `leaf_hash_hex` the verifier reproduces the root from. Every one of those is
    cohort-level or a commitment — invariant 5 holds by construction: no raw observation and
    no coordinate ever enters a bundle slot.
    """
    entries: list[dict] = []
    roots: list[str] = []
    block_seconds = 3600
    start_ts = 1721001600
    for epoch_index in range(n_epochs):
        batches = []
        for i, cid in enumerate(cohort_ids):
            byte = bytes([(epoch_index * 37 + i * 11 + 3) % 256])
            signer_pk = ref_evidence.b58encode(byte + bytes(31))
            sig_byte = "%02x" % ((epoch_index * 53 + i * 29 + 7) % 256)
            t0 = start_ts + epoch_index * block_seconds * 12
            batches.append(
                {
                    "spec_version": "1.0.0",
                    "experiment_id": sc.experiment_id,
                    "epoch_index": str(epoch_index),
                    "cohort_id": cid,
                    "time_range": {"start": str(t0), "end": str(t0 + block_seconds * 12)},
                    "signer_set_commitment": {
                        "algo": "sha256",
                        "merkle_root_hex": ref_evidence.signer_subtree(
                            [
                                ref_evidence.b58encode(
                                    bytes([(i * 7 + d * 31 + epoch_index + 1) % 256]) + bytes(31)
                                )
                                for d in range(5)
                            ]
                        )[0].hex(),
                        "signer_count": "5",
                        "leaf_scheme": "sha256(0x00||'signer'||signer_pubkey_be32)",
                    },
                    "observations_commitment": {
                        "algo": "sha256",
                        "merkle_root_hex": ref_evidence.observation_subtree(
                            [
                                canonical.sha256_hex(
                                    b"obs|%s|%d|%d" % (cid.encode(), epoch_index, k)
                                )
                                for k in range(8)
                            ]
                        )[0].hex(),
                        "leaf_count": "8",
                        "leaf_scheme": "sha256(0x00||'obs'||observation_commitment_be32)",
                    },
                    "aggregate_summary": {
                        "accepted_count": str(180 + (i * 13 + epoch_index * 5) % 40),
                        "rejected_count": str((i * 3 + epoch_index) % 7),
                        "distinct_signers": "5",
                    },
                    "batch_signature": {
                        "algo": "ed25519",
                        "signer_pubkey": signer_pk,
                        "header_hash_hex": sig_byte * 32,
                        "signature_hex": sig_byte * 64,
                    },
                }
            )
        root, records = ref_evidence.epoch_tree(batches)
        by_hash = {canonical.sha256_hex(canonical.canonical_json_bytes(b)): b for b in batches}
        # `records` are already leaf_hash-ascending; re-associate each to its batch header.
        ordered: list[dict] = []
        for rec in records:
            cb = bytes.fromhex(rec["leaf_canonical_bytes_hex"]) if "leaf_canonical_bytes_hex" in rec else None
            if cb is not None:
                ordered.append(json.loads(cb.decode()))
            else:
                ordered.append(None)  # filled below
        if any(o is None for o in ordered):
            # Reconstruct order by recomputing each batch's leaf hash.
            pairs = []
            for b in batches:
                cb = canonical.canonical_json_bytes(b)
                lh = canonical.sha256(bytes([0x00]) + b"CRP:evidence:v1" + cb).hex()
                pairs.append((lh, b))
            pairs.sort(key=lambda p: p[0])
            ordered = [b for _, b in pairs]
        del by_hash

        rel = "evidence/epoch-%06d.parquet" % epoch_index
        write_parquet(
            dest / rel,
            {
                "leaf_hash_hex": [r["leaf_hash_hex"] for r in records],
                "cohort_id": [b["cohort_id"] for b in ordered],
                "epoch_index": [b["epoch_index"] for b in ordered],
                "time_start": [b["time_range"]["start"] for b in ordered],
                "time_end": [b["time_range"]["end"] for b in ordered],
                "signer_set_root_hex": [
                    b["signer_set_commitment"]["merkle_root_hex"] for b in ordered
                ],
                "signer_count": [b["signer_set_commitment"]["signer_count"] for b in ordered],
                "observations_root_hex": [
                    b["observations_commitment"]["merkle_root_hex"] for b in ordered
                ],
                "observation_leaf_count": [
                    b["observations_commitment"]["leaf_count"] for b in ordered
                ],
                "accepted_count": [b["aggregate_summary"]["accepted_count"] for b in ordered],
                "rejected_count": [b["aggregate_summary"]["rejected_count"] for b in ordered],
                "distinct_signers": [b["aggregate_summary"]["distinct_signers"] for b in ordered],
                "batch_signer_pubkey": [b["batch_signature"]["signer_pubkey"] for b in ordered],
            },
        )
        entries.append(
            {
                "epoch_index": str(epoch_index),
                "file": rel,
                "evidence_epoch_root_hex": root.hex(),
            }
        )
        roots.append(root.hex())
    return entries, roots


def build_bundle(sc: Scenario) -> Path:
    dest = DEST_ROOT / sc.bundle_id
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    work = dest / ".work"
    work.mkdir()

    manifest_obj = build_scenario_manifest(sc)
    manifest_bytes = canonical.canonical_json_bytes(manifest_obj)
    manifest_hash = canonical.sha256_hex(manifest_bytes)
    (dest / "manifest.json").write_bytes(manifest_bytes)
    (work / "manifest.json").write_bytes(manifest_bytes)

    panel = build_noisy_panel(sc.seed, true_effect=sc.true_effect, noise=sc.noise)
    participants = build_participants(sc.seed)
    panel.to_parquet(work / "panel.parquet", index=False)
    participants.to_parquet(work / "participants.parquet", index=False)

    cohort_ids = sorted(set(panel["cohort_id"].tolist()))

    # -- evidence epochs first: the engine BINDS their roots into analysis.json (the seam) --
    epoch_entries, epoch_roots = build_evidence_epochs(sc, cohort_ids, dest)

    # -- assignment.parquet: arms re-derivable from the committed seed (invariant 1) --------
    assigns = derive_assignment(
        sc.seed,
        sc.experiment_id,
        cohort_ids,
        manifest_obj["assignment"]["design"],
        manifest_obj["assignment"]["params"],
    )
    leaf_bytes = []
    rows = {"cohort_id": [], "arm": [], "prf_u64": [], "leaf_hash_hex": []}
    for a in assigns:
        lb = canonical.canonical_json_bytes({"arm": a.arm, "cohort_id": a.cohort_id})
        leaf_bytes.append(lb)
        rows["cohort_id"].append(a.cohort_id)
        rows["arm"].append(a.arm)
        rows["prf_u64"].append(str(a.prf_u64))
        rows["leaf_hash_hex"].append(merkle.leaf_hash(merkle.DOMAIN_ASSIGNMENT, lb).hex())
    write_parquet(dest / "assignment.parquet", rows)
    assignment_root = merkle.merkle_root(leaf_bytes, merkle.DOMAIN_ASSIGNMENT).hex()

    # -- participants.parquet: cohort-level contribution weights only ----------------------
    write_parquet(
        dest / "participants.parquet",
        {
            "cohort_id": [str(v) for v in participants["cohort_id"]],
            "recipient_hex": [str(v) for v in participants["recipient_hex"]],
            "accepted_observations": [str(v) for v in participants["accepted_observations"]],
            "quality_adjusted_observations": [
                str(v) for v in participants["quality_adjusted_observations"]
            ],
        },
    )

    # -- the real engine run ---------------------------------------------------------------
    manifest = Manifest.from_path(work / "manifest.json")
    run = analyze(
        manifest,
        work / "panel.parquet",
        work / "participants.parquet",
        seed=sc.seed,
        evidence_epoch_roots=tuple(epoch_roots),
    )
    write_all(run, work / "artifacts", source_commit="")

    for name in ("analysis.json", "rewards.parquet", "rewards_detail.parquet"):
        src = work / "artifacts" / name
        if src.exists():
            shutil.copyfile(src, dest / name)

    analysis_bytes = (dest / "analysis.json").read_bytes()
    result_artifact_hash = canonical.sha256_hex(analysis_bytes)
    reward_root = run.compilation.reward_root_hex

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

    container_digest = manifest_obj["analysis_plan"]["analysis_container_digest"]
    (dest / "provenance.json").write_bytes(
        canonical.canonical_json_bytes(
            {
                "source_commit": "0" * 40,
                "container_digest": container_digest,
                "execution_timestamp": "0",
                "manifest_hash": manifest_hash,
                "result_artifact_hash": result_artifact_hash,
                "reference_note": (
                    "assembled by dashboard/scripts/build_demo_bundles.py from a real "
                    "crp-engine run; every root produced by verifier-cli/reference"
                ),
            }
        )
    )

    shutil.rmtree(work)
    s1 = run.compilation.stage1
    print(
        "%-14s manifest %s  reward_root %s  leaves %d  null=%s"
        % (
            sc.bundle_id,
            manifest_hash[:12],
            (reward_root or "")[:12],
            run.compilation.leaf_count,
            s1.null_distribution,
        )
    )
    return dest


def main() -> int:
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    for sc in SCENARIOS:
        build_bundle(sc)
    print("bundles written to %s" % DEST_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
