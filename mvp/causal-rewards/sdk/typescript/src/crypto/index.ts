/**
 * Determinism-safe canonical crypto for the Causal Rewards Protocol.
 *
 * Every function here is the TypeScript leg of the SINGLE canonical encoding in
 * `specs/serialization.md` (RATIFIED, spec-v1-frozen), and is byte-for-byte
 * identical to the verifier reference (`verifier-cli/reference/`) and the on-chain
 * `crp-crypto` crate. It is conformance-tested against the golden vectors under
 * `test-vectors/`. There is exactly one canonical encoding; do not add a second.
 */

export * from "./canonical";
export * from "./merkle";
export * from "./assignment";
export * from "./reward";

import { sha256 } from "./canonical";

const ENC = new TextEncoder();
const EXP_ID_DOMAIN = ENC.encode("CRP-exp-id");

/**
 * `experiment_id_hash = SHA-256( "CRP-exp-id" || experiment_id_utf8 )`.
 * This is the value the `experiment` PDA is seeded with and the exact hash the
 * `create_experiment` instruction re-derives and enforces on-chain.
 */
export function experimentIdHash(experimentId: string): Uint8Array {
  return sha256(EXP_ID_DOMAIN, ENC.encode(experimentId));
}
