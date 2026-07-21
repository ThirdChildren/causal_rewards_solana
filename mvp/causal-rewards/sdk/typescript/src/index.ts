/**
 * @causal-rewards/sdk — typed TypeScript client for the Causal Rewards Protocol
 * Solana programs (experiment registry, evidence, settlement, challenge).
 *
 * Thin, IDL-aligned, determinism-safe. The `crypto/` module is the single canonical
 * encoding shared byte-for-byte with the verifier reference and the on-chain
 * `crp-crypto` crate (specs/serialization.md, RATIFIED). Do not add a second encoding.
 *
 * Targets IDL/program version 0.1.0 (Anchor 0.32.1), spec serialization v1.0.0.
 */

export * from "./crypto";
export * from "./programs";
export * from "./pda";
export * from "./errors";
export * from "./accounts";
export * from "./client";
