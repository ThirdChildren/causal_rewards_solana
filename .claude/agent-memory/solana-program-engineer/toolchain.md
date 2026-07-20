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

## Build/deploy gotchas (M2, all resolved — see scripts/)

- **Use `anchor build` (per-program isolated), NOT workspace `cargo build-sbf`.** experiment-registry is both a program AND a dependency of the 3 satellites (via `cpi`/`no-entrypoint` feature). A single workspace SBF build lets cargo feature-unification enable `no-entrypoint` on experiment-registry → 544-byte entrypoint-less stub that fails deploy with "ELF/Entrypoint" errors. `anchor build` compiles each program separately and avoids this.
- **IDL: generate per program** (`anchor idl build -p <name> -o target/idl/<name>.json`). The batch `anchor build` IDL step cross-links anchor-spl types and fails with `insert_types`/`DISCRIMINATOR not found for Mint/TokenAccount`. Fix that made batch work too: each satellite's `idl-build` feature must include `experiment-registry/idl-build` (which pulls `anchor-spl/idl-build`). IDLs published to committed `idl/` dir (target/ is gitignored).
- **CpiContext API in anchor 1.1.2**: `CpiContext::new(program_id: Pubkey, accounts)` / `new_with_signer(program_id, accounts, seeds)` — pass `program.key()` (a Pubkey), NOT `.to_account_info()`. anchor-spl `token::transfer` hardcodes `spl_token::ID` internally.
- **Enum for `#[account]` fields**: fieldless enums must have NO explicit discriminants (`Draft = 0`) or borsh derive fails; plain `Draft, Frozen, ...` works and `as u8` still casts.
- **Local validator**: anchor 1.1.2 defaults to `surfpool` (not installed) → run `solana-test-validator` directly. It force-activates SIMD-0500 (disables SBPFv0/v1/v2 deploy) while default platform-tools arch is v0 → deploy fails "sbpf_version not enabled". For local tests start with `--deactivate-feature B8JJXCy5amZyWG9r7EnUYLwzXSXTxG7GZ1qZ1qggo83g`. Real devnet has no SIMD-0500, so default build deploys there. `scripts/localnet-test.sh` and `scripts/build.sh` encode all of this.
- Boxing accounts (`Box<Account<..>>`) fixes SBF "Stack offset exceeded 4096" (hit in challenge `OpenChallenge` with two `init` token accounts).
