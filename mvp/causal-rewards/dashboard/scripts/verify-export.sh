#!/usr/bin/env bash
# The export's acceptance test, end to end.
#
#   dashboard export path  ->  .zip  ->  unzip  ->  crp-verify  ->  ACCEPT
#
# The dashboard is a convenience layer, so the only meaningful check on its export is whether
# an INDEPENDENT tool accepts the result. This script never inspects the archive itself; it
# hands the bytes to `crp-verify` and reports that verdict.
#
#   scripts/verify-export.sh [bundle-id ...]
#
# Requires the verifier CLI. Either put `crp-verify` on PATH, or point CRP_VERIFY at it:
#   CRP_VERIFY=../verifier-cli/.venv/bin/crp-verify scripts/verify-export.sh
set -euo pipefail

DASHBOARD="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$DASHBOARD/dist-export"
WORK="$OUT/.unzipped"
CRP_VERIFY="${CRP_VERIFY:-$DASHBOARD/../verifier-cli/.venv/bin/crp-verify}"

if [ ! -x "$CRP_VERIFY" ]; then
  if command -v crp-verify >/dev/null 2>&1; then
    CRP_VERIFY="$(command -v crp-verify)"
  else
    echo "verify-export: no crp-verify. Install it (pip install -e ../verifier-cli) or set CRP_VERIFY." >&2
    exit 2
  fi
fi

BUNDLES=("$@")
if [ ${#BUNDLES[@]} -eq 0 ]; then
  BUNDLES=(golden-happy demo-signal demo-null demo-low-power)
fi

rm -rf "$WORK"
mkdir -p "$WORK"
failed=0

for id in "${BUNDLES[@]}"; do
  echo "── $id ─────────────────────────────────────────────"
  zip_path="$(node "$DASHBOARD/scripts/export-bundle.mjs" "$id" | awk '/^archive/ {print $2}')"
  dest="$WORK/$id"
  mkdir -p "$dest"
  unzip -q -o "$zip_path" -d "$dest"
  if "$CRP_VERIFY" "$dest" --onchain "$dest/dashboard-export/onchain-commitments.json" | tail -1; then
    :
  else
    echo "  ^ REJECTED"
    failed=1
  fi
done

if [ "$failed" -ne 0 ]; then
  echo "verify-export: at least one exported bundle was REJECTED" >&2
  exit 1
fi
echo "verify-export: every exported bundle ACCEPTED"
