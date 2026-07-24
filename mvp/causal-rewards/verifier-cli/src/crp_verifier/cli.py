"""``crp-verify`` — recompute and check every root in an audit bundle, offline.

Usage::

    crp-verify <bundle-dir> [--seed <64-hex>] [--onchain <commitments.json>]
                            [--golden-manifest-hash <64-hex>] [--json]

The command loads the bundle DIRECTORY, runs every check in :mod:`crp_verifier.checks`
in a fixed order, prints a per-check ``PASS``/``FAIL``/``SKIP`` report with the first point
of divergence on any failure, and exits ``0`` only if no check FAILED (SKIP is not a
failure). Any FAIL, or a structural problem reading the bundle, exits non-zero.

Determinism: the report reads no wall-clock and no RNG. Two runs of the same command on
the same bundle emit byte-identical output, so the verdict itself is reproducible.

No network access is performed anywhere: the only inputs are the bundle directory, the
optional on-chain commitments file, and the pinned reference encoder.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence, TextIO

from . import __version__
from .bundle import Bundle, BundleError
from .checks import CheckResult, FAIL, PASS, SKIP, run_all

_STATUS_MARK = {PASS: "[PASS]", FAIL: "[FAIL]", SKIP: "[SKIP]"}

# Deterministic exit codes.
EXIT_OK = 0
EXIT_VERIFY_FAILED = 1
EXIT_USAGE = 2
EXIT_BUNDLE_ERROR = 3


def _parse_seed(hexstr: str) -> bytes:
    s = hexstr.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    if len(s) != 64 or any(c not in "0123456789abcdef" for c in s):
        raise ValueError("--seed must be 32 bytes as 64 hex chars, got %r" % hexstr)
    return bytes.fromhex(s)


def _load_onchain(path: str) -> Mapping[str, Any]:
    raw = Path(path).read_bytes()
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, Mapping):
        raise ValueError("--onchain file must contain a JSON object of anchor -> value")
    # A bundle-nested {"roots": {...}} or {"onchain": {...}} shape is unwrapped for convenience.
    for key in ("onchain", "commitments", "anchors"):
        if key in obj and isinstance(obj[key], Mapping):
            return {str(k): v for k, v in obj[key].items()}
    return {str(k): v for k, v in obj.items()}


def _render_text(results: Sequence[CheckResult], bundle_path: str) -> list[str]:
    lines: list[str] = []
    lines.append("crp-verify %s" % __version__)
    lines.append("bundle: %s" % bundle_path)
    lines.append("")
    for r in results:
        lines.append("%s %-24s %s" % (_STATUS_MARK.get(r.status, "[????]"), r.name, r.summary))
        for d in r.details:
            lines.append("        - %s" % d)
        if r.status == FAIL and r.divergence is not None:
            field_, expected, got = r.divergence
            lines.append("        ! first divergence @ %s" % field_)
            lines.append("            expected: %s" % expected)
            lines.append("            got:      %s" % got)
    lines.append("")
    n_fail = sum(1 for r in results if r.status == FAIL)
    n_pass = sum(1 for r in results if r.status == PASS)
    n_skip = sum(1 for r in results if r.status == SKIP)
    verdict = "REJECT" if n_fail else "ACCEPT"
    lines.append("verdict: %s  (%d pass, %d fail, %d skip)" % (verdict, n_pass, n_fail, n_skip))
    return lines


def _render_json(results: Sequence[CheckResult], bundle_path: str) -> str:
    n_fail = sum(1 for r in results if r.status == FAIL)
    payload = {
        "verifier_version": __version__,
        "bundle": bundle_path,
        "verdict": "REJECT" if n_fail else "ACCEPT",
        "checks": [
            {
                "name": r.name,
                "status": r.status,
                "summary": r.summary,
                "divergence": (
                    None
                    if r.divergence is None
                    else {"field": r.divergence[0], "expected": r.divergence[1], "got": r.divergence[2]}
                ),
                "details": r.details,
            }
            for r in results
        ],
    }
    # sort_keys + fixed separators => byte-stable output across runs/machines.
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="crp-verify",
        description="Independently recompute and check every root in a Causal Rewards audit "
        "bundle. Offline; trusts only the bundle and the pinned reference encoder.",
    )
    p.add_argument("bundle", help="path to the audit-bundle directory")
    p.add_argument(
        "--seed",
        metavar="HEX",
        default=None,
        help="on-chain revealed assignment seed (64 hex chars). Enables re-derivation of "
        "every arm from the committed seed (invariant 1). Omit for structural-only.",
    )
    p.add_argument(
        "--onchain",
        metavar="JSON",
        default=None,
        help="path to a JSON file of on-chain anchored commitments to cross-check the "
        "reproduced roots against (catches a self-consistent but SUBSTITUTED bundle).",
    )
    p.add_argument(
        "--golden-manifest-hash",
        metavar="HEX",
        default=None,
        help="optional expected manifest hash to additionally assert (release pinning).",
    )
    p.add_argument("--json", action="store_true", help="emit a byte-stable JSON verdict instead of text")
    p.add_argument("--version", action="version", version="crp-verify %s" % __version__)
    return p


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None, err: TextIO | None = None) -> int:
    out = out if out is not None else sys.stdout
    err = err if err is not None else sys.stderr
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        seed = _parse_seed(args.seed) if args.seed is not None else None
    except ValueError as exc:
        print("error: %s" % exc, file=err)
        return EXIT_USAGE

    try:
        onchain = _load_onchain(args.onchain) if args.onchain else None
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("error: cannot read --onchain file: %s" % exc, file=err)
        return EXIT_USAGE

    try:
        bundle = Bundle(args.bundle)
    except BundleError as exc:
        print("error: %s" % exc, file=err)
        return EXIT_BUNDLE_ERROR

    results = run_all(
        bundle,
        revealed_seed=seed,
        onchain=onchain,
        golden_manifest_hash=args.golden_manifest_hash,
    )

    if args.json:
        print(_render_json(results, args.bundle), file=out)
    else:
        for line in _render_text(results, args.bundle):
            print(line, file=out)

    return EXIT_VERIFY_FAILED if any(r.status == FAIL for r in results) else EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
