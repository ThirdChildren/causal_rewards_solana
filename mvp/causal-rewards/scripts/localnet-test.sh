#!/usr/bin/env bash
# Full local integration-test flow: build -> start validator -> deploy -> ts-mocha.
#
# We drive solana-test-validator directly instead of `anchor test`, because anchor
# 1.1.2 defaults to the `surfpool` validator (not installed here) and because the
# validator must have SIMD-0500 DEACTIVATED: SIMD-0500 (force-activated on a fresh
# test validator) disables deployment of SBPFv0/v1/v2 programs, and the default
# platform-tools arch is v0. Real devnet does not have SIMD-0500 active, so the
# default build deploys there fine (see scripts/deploy-devnet.sh).
set -euo pipefail
cd "$(dirname "$0")/.."

SIMD_0500=B8JJXCy5amZyWG9r7EnUYLwzXSXTxG7GZ1qZ1qggo83g
RPC=http://127.0.0.1:8899
WALLET="${WALLET:-$HOME/.config/solana/id.json}"

./scripts/build.sh

echo "==> Starting solana-test-validator (SIMD-0500 deactivated)"
pkill -f solana-test-validator 2>/dev/null || true
sleep 2
rm -rf test-ledger
solana-test-validator --reset --quiet --ledger test-ledger \
  --deactivate-feature "$SIMD_0500" &
VALIDATOR_PID=$!
trap 'kill $VALIDATOR_PID 2>/dev/null || true' EXIT

solana config set --url "$RPC" >/dev/null
for i in $(seq 1 40); do solana cluster-version >/dev/null 2>&1 && break; sleep 1; done
solana airdrop 500 >/dev/null 2>&1 || true

echo "==> Deploying programs"
for p in experiment_registry evidence_registry settlement challenge; do
  solana program deploy "target/deploy/$p.so" --program-id "target/deploy/$p-keypair.json"
done

echo "==> Running integration tests"
ANCHOR_PROVIDER_URL="$RPC" ANCHOR_WALLET="$WALLET" \
  npx ts-mocha -p ./tsconfig.json -t 1000000 tests/**/*.ts

echo "==> Running crp-crypto determinism vectors"
cargo test -p crp-crypto
