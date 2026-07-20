#!/usr/bin/env bash
# Reproducible devnet deploy for the Causal Rewards Protocol programs.
# DEVNET ONLY (Invariant 7). Never point this at mainnet.
set -euo pipefail

cd "$(dirname "$0")/.."

CLUSTER="${CLUSTER:-devnet}"
if [[ "$CLUSTER" != "devnet" ]]; then
  echo "Refusing to deploy: this MVP is devnet-only (Invariant 7). CLUSTER=$CLUSTER" >&2
  exit 1
fi

echo "==> Using cluster: $CLUSTER"
solana config set --url "https://api.$CLUSTER.solana.com" >/dev/null

WALLET="${WALLET:-$HOME/.config/solana/id.json}"
echo "==> Wallet: $(solana address -k "$WALLET")"
solana airdrop 2 -k "$WALLET" || echo "airdrop may be rate-limited; ensure the wallet is funded"

echo "==> Building"
anchor build --no-idl
for p in experiment_registry evidence_registry settlement challenge; do
  anchor idl build -p "$p" -o "target/idl/$p.json"
done

echo "==> Deploying programs"
anchor deploy --provider.cluster "$CLUSTER" --provider.wallet "$WALLET"

echo "==> Publishing (initializing) IDLs on-chain"
for p in experiment_registry evidence_registry settlement challenge; do
  PID=$(python3 -c "import json;print(json.load(open('target/idl/$p.json'))['address'])")
  anchor idl init "$PID" -f "target/idl/$p.json" --provider.cluster "$CLUSTER" --provider.wallet "$WALLET" \
    || anchor idl upgrade "$PID" -f "target/idl/$p.json" --provider.cluster "$CLUSTER" --provider.wallet "$WALLET"
done

echo "==> Done. Program ids:"
for p in experiment_registry evidence_registry settlement challenge; do
  echo "  $p: $(python3 -c "import json;print(json.load(open('target/idl/$p.json'))['address'])")"
done
