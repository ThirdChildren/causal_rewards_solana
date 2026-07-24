"""``crp-engine`` command line.

    crp-engine analyze  --manifest M --panel P [--participants X] [--seed HEX] --out DIR
    crp-engine vectors  [--dir test-vectors/reward]     # replay the ratified reward vectors
    crp-engine digest                                   # print the reference-source digest

Every artifact-producing subcommand is a pure function of its inputs plus the committed seed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crp_engine import __version__
from crp_engine.manifest import Manifest
from crp_engine.reference import REFERENCE_DIR, reference_source_digest
from crp_engine.run import analyze, write_all


def _seed(value: str | None) -> bytes:
    if not value:
        return b"\x00" * 32
    s = value[2:] if value.startswith("0x") else value
    raw = bytes.fromhex(s)
    if len(raw) != 32:
        raise SystemExit("seed must be exactly 32 bytes (64 hex chars), got %d" % len(raw))
    return raw


def _epoch_roots(value: str | None) -> tuple[str, ...]:
    """Read the assembler's ordered evidence-epoch roots (JSON array file, or comma list)."""
    if not value:
        return ()
    p = Path(value)
    if p.is_file():
        obj = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(obj, list) or not all(isinstance(x, str) for x in obj):
            raise SystemExit("--evidence-epoch-roots file must be a JSON array of hex strings")
        return tuple(obj)
    return tuple(s for s in (part.strip() for part in value.split(",")) if s)


def _cmd_analyze(args: argparse.Namespace) -> int:
    manifest = Manifest.from_path(args.manifest)
    run = analyze(
        manifest,
        args.panel,
        args.participants or (),
        seed=_seed(args.seed),
        evidence_epoch_roots=_epoch_roots(args.evidence_epoch_roots),
    )
    hashes = write_all(run, args.out, source_commit=args.source_commit or "")
    s1 = run.compilation.stage1
    print("analysis.json          %s" % hashes["analysis.json"])
    print("rewards.canonical.json %s  (leaf set = settlement source)" % hashes["rewards.canonical.json"])
    print("rewards_detail.json    %s" % hashes["rewards_detail.canonical.json"])
    print("reward_root            %s" % run.compilation.reward_root_hex)
    print("identification         %s" % run.panel.identification.value)
    print(
        "cohorts                %d total / %d meet min-sample / %d with a positive conservative bound"
        % (
            len(s1.cohorts),
            s1.n_eligible_cohorts,
            sum(1 for c in s1.cohorts if c.conservative_s > 0),
        )
    )
    print(
        "budget                 %d allocated of %d (leaves: %d, recoverable: %d)"
        % (
            run.compilation.total_leaf_base_units,
            s1.budget_base_units,
            run.compilation.leaf_count,
            s1.budget_base_units - run.compilation.total_leaf_base_units,
        )
    )
    if s1.null_distribution:
        print("NULL DISTRIBUTION — a valid result, not an error:")
        for r in s1.null_reasons:
            print("  * %s" % r)
    return 0


def _cmd_vectors(args: argparse.Namespace) -> int:
    """Replay the ratified reward test vectors through the engine's compiler path."""
    from crp_engine.reward_compiler import (
        DuplicateRecipientError,
        SplitRow,
        finalize_leaves,
        Stage1Result,
    )

    vdir = Path(args.dir)
    index = json.loads((vdir / "index.json").read_text(encoding="utf-8"))
    ok = True
    for entry in index["vectors"]:
        name = entry["name"]
        vec = json.loads((vdir / (name + ".json")).read_text(encoding="utf-8"))
        stage1 = Stage1Result(
            cohorts=(), n_eligible_cohorts=0, min_eligible_cohorts=0,
            null_distribution=False, null_reasons=(), total_alloc_before_cap=0,
            total_budget_allocated=0, budget_base_units=(1 << 64) - 1, scaled_to_budget=False,
        )
        if entry["kind"] == "reward_duplicate_recipient_error":
            leaves = vec["inputs"]["malformed_leaf_set"]
            rows = [
                SplitRow(
                    cohort_id="synthetic",
                    recipient=bytes.fromhex(lf["recipient_hex"]),
                    weight=1, cohort_weight_total=1, cohort_budget_base_units=0,
                    amount_base_units=int(lf["amount_base_units"]),
                )
                for lf in leaves
            ]
            # A conforming compiler AGGREGATES duplicates away, so the malformed set is fed
            # straight to the reference guard, which must reject it.
            from crp_engine.reference import RewardLeaf, reward_root

            try:
                reward_root(
                    [
                        RewardLeaf(
                            bytes.fromhex(lf["recipient_hex"]),
                            int(lf["amount_base_units"]),
                            int(lf["leaf_index"]),
                        )
                        for lf in leaves
                    ]
                )
                print("FAIL %-38s expected rejection %s" % (name, entry["rejection_code"]))
                ok = False
            except ValueError as exc:
                assert "duplicate recipient" in str(exc)
                print("PASS %-38s rejected: %s" % (name, entry["rejection_code"]))
            continue

        rows = [
            SplitRow(
                cohort_id=c["cohort_id"],
                recipient=bytes.fromhex(c["recipient_hex"]),
                weight=1,
                cohort_weight_total=1,
                cohort_budget_base_units=int(c["amount_base_units"]),
                amount_base_units=int(c["amount_base_units"]),
            )
            for c in vec["inputs"]["contributions"]
        ]
        got = finalize_leaves(stage1, rows).reward_root_hex
        want = entry["reward_root_hex"]
        status = "PASS" if got == want else "FAIL"
        ok &= got == want
        print("%s %-38s %s" % (status, name, got))
    return 0 if ok else 1


def _cmd_digest(args: argparse.Namespace) -> int:
    print("engine_version           %s" % __version__)
    print("reference_dir            %s" % REFERENCE_DIR)
    print("reference_source_digest  %s" % reference_source_digest())
    lock = Path(__file__).resolve().parents[2] / "container.lock.json"
    if lock.is_file():
        obj = json.loads(lock.read_text(encoding="utf-8"))
        print("recipe_digest            %s" % obj.get("recipe_digest", ""))
        print("image_digest             %s" % obj.get("image_digest", "<not built>"))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="crp-engine", description=__doc__)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("analyze", help="run the full analysis + reward compilation")
    a.add_argument("--manifest", required=True)
    a.add_argument("--panel", required=True)
    a.add_argument("--participants")
    a.add_argument("--seed", help="32-byte committed seed, hex")
    a.add_argument("--source-commit", default="")
    a.add_argument(
        "--evidence-epoch-roots",
        help="assembler's ordered evidence-epoch roots: a JSON-array file path or a comma list; "
        "echoed verbatim into analysis.json.evidence_epoch_roots",
    )
    a.add_argument("--out", required=True)
    a.set_defaults(fn=_cmd_analyze)

    v = sub.add_parser("vectors", help="replay the ratified reward test vectors")
    v.add_argument(
        "--dir",
        default=str(Path(__file__).resolve().parents[3] / "test-vectors" / "reward"),
    )
    v.set_defaults(fn=_cmd_vectors)

    d = sub.add_parser("digest", help="print engine/reference/container digests")
    d.set_defaults(fn=_cmd_digest)

    args = p.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
