---
name: toolchain
description: Installed Solana/Anchor toolchain versions and the exact build/test commands + PATH for the on-chain programs
metadata:
  type: reference
---

# Toolchain (installed 2026-07-20)

- **solana-cli 4.1.1** (Agave), platform-tools v1.54, includes `solana-test-validator`, `cargo-build-sbf`, `cargo-test-sbf`, `solana-keygen`.
  Lives at `/home/stephl0xff/.local/share/solana/install/active_release/bin`.
- **anchor-cli 1.1.2** at `~/.cargo/bin/anchor` (installed via `cargo install --locked anchor-cli --version 1.1.2`).
- **cargo/rustc 1.93.0** host toolchain at `~/.cargo/bin`.
- Pin on-chain crates: `anchor-lang`/`anchor-spl` **1.1.2**, `solana-program` **4.0**.

**PATH for any build/test shell** (cwd resets between bash calls — export every time):
```
export PATH="/home/stephl0xff/.local/share/solana/install/active_release/bin:$HOME/.cargo/bin:$PATH"
```

Network to `release.solana.com` was blocked but `release.anza.xyz`, github, crates.io, npm all reachable. Anza install script: `curl -sSfL https://release.anza.xyz/stable/install | sh`.

Anchor workspace root: `mvp/causal-rewards/` (Anchor.toml, Cargo workspace, programs/, tests/).
`crp-crypto` shared crate is host-testable with plain `cargo test` (uses `sha2`, no SBF needed) — fastest way to prove determinism against `test-vectors/` without a validator.
