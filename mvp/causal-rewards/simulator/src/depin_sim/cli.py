"""Command-line entry point for the simulator alpha.

Usage:
    python -m depin_sim.cli run     --scenario scenarios/baseline_alpha.json [--seed 0x..] [--out DIR]
    python -m depin_sim.cli hash    --scenario scenarios/baseline_alpha.json [--seed 0x..]

``run`` writes the artifact bundle and prints the content hash. ``hash`` prints ONLY the
content hash (used by the determinism check to compare two runs of the same seed).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from depin_sim.config import load_scenario
from depin_sim.export import write_bundle
from depin_sim.run import run_scenario


def _resolve(scenario_path: str, seed: str | None):
    cfg = load_scenario(scenario_path)
    if seed is not None:
        cfg = _with_seed(cfg, seed)
    return cfg


def _with_seed(cfg, seed: str):
    import dataclasses

    return dataclasses.replace(cfg, seed=seed)


def _cmd_run(args: argparse.Namespace) -> int:
    cfg = _resolve(args.scenario, args.seed)
    result = run_scenario(cfg)
    out_dir = args.out or f"out/{cfg.name}"
    paths = write_bundle(result, out_dir)
    print(f"scenario:      {cfg.name}")
    print(f"design:        {cfg.design}")
    print(f"seed:          {cfg.seed}")
    print(f"content_hash:  {result.content_hash}")
    print(f"bundle_dir:    {Path(out_dir).resolve()}")
    for name, p in paths.items():
        print(f"  {name:14s} {p}")
    return 0


def _cmd_hash(args: argparse.Namespace) -> int:
    cfg = _resolve(args.scenario, args.seed)
    result = run_scenario(cfg)
    print(result.content_hash)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="depin_sim", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("run", "hash"):
        sp = sub.add_parser(name)
        sp.add_argument("--scenario", required=True, help="path to a scenario JSON file")
        sp.add_argument("--seed", default=None, help="override the committed seed (hex or string)")
        if name == "run":
            sp.add_argument("--out", default=None, help="output bundle directory")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "hash":
        return _cmd_hash(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
