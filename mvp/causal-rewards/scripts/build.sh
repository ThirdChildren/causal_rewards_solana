#!/usr/bin/env bash
# Build all four programs (.so) and (re)generate their IDLs.
#
# NOTE: `anchor build` builds each program in an ISOLATED cargo invocation, which is
# required here: experiment-registry is both a program AND a dependency of the three
# satellites (via the `cpi` feature). A single workspace `cargo build-sbf` would let
# cargo feature-unification enable `no-entrypoint` on experiment-registry and produce
# an entrypoint-less stub. Per-program builds avoid that.
#
# IDLs are generated per program because the batch IDL build cross-links anchor-spl
# types; the per-program path is reliable. Output IDLs land in target/idl/ and are
# copied to the committed idl/ directory for the SDK.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Building program binaries (.so)"
anchor build --no-idl

echo "==> Generating IDLs"
for p in experiment_registry evidence_registry settlement challenge; do
  anchor idl build -p "$p" -o "target/idl/$p.json"
done

echo "==> Publishing IDLs to committed idl/"
mkdir -p idl
cp target/idl/*.json idl/

echo "==> Done."
ls -la target/deploy/*.so idl/*.json
