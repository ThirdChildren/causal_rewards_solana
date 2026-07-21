/**
 * Program error-code → human-readable message maps, one per M2 program, plus a
 * helper that turns a raw Anchor/RPC error into a readable `CausalRewardsError`.
 *
 * The tables are derived DIRECTLY from the four published IDL `errors[]` arrays at
 * module load, so they can never drift from the on-chain interface the SDK is built
 * against — re-copying the IDLs (which the SDK build does) updates the mapping
 * automatically. Anchor custom errors start at 6000.
 */

import experimentRegistryIdl from "./idl/experiment_registry.json";
import evidenceRegistryIdl from "./idl/evidence_registry.json";
import settlementIdl from "./idl/settlement.json";
import challengeIdl from "./idl/challenge.json";

export interface ProgramErrorInfo {
  code: number;
  name: string;
  msg: string;
}

type ErrorTable = Record<number, ProgramErrorInfo>;

interface IdlErrorEntry {
  code: number;
  name: string;
  msg?: string;
}

function tableFromIdl(errors: IdlErrorEntry[] | undefined): ErrorTable {
  const t: ErrorTable = {};
  for (const e of errors ?? []) {
    t[e.code] = { code: e.code, name: e.name, msg: e.msg ?? e.name };
  }
  return t;
}

export const EXPERIMENT_REGISTRY_ERRORS = tableFromIdl(
  (experimentRegistryIdl as { errors?: IdlErrorEntry[] }).errors,
);
export const EVIDENCE_REGISTRY_ERRORS = tableFromIdl(
  (evidenceRegistryIdl as { errors?: IdlErrorEntry[] }).errors,
);
export const SETTLEMENT_ERRORS = tableFromIdl(
  (settlementIdl as { errors?: IdlErrorEntry[] }).errors,
);
export const CHALLENGE_ERRORS = tableFromIdl(
  (challengeIdl as { errors?: IdlErrorEntry[] }).errors,
);

export type ProgramName = "experimentRegistry" | "evidenceRegistry" | "settlement" | "challenge";

export const ERROR_TABLES: Record<ProgramName, ErrorTable> = {
  experimentRegistry: EXPERIMENT_REGISTRY_ERRORS,
  evidenceRegistry: EVIDENCE_REGISTRY_ERRORS,
  settlement: SETTLEMENT_ERRORS,
  challenge: CHALLENGE_ERRORS,
};

/** Look up a custom error by program + code. Returns undefined if unknown. */
export function lookupProgramError(
  program: ProgramName,
  code: number,
): ProgramErrorInfo | undefined {
  return ERROR_TABLES[program][code];
}

/** A decoded program error with the readable message attached. */
export class CausalRewardsError extends Error {
  constructor(
    readonly program: ProgramName,
    readonly info: ProgramErrorInfo,
    readonly cause?: unknown,
  ) {
    super(`[${program}] ${info.name} (${info.code}): ${info.msg}`);
    this.name = "CausalRewardsError";
  }
}

/**
 * Extract a custom error code from a raw Anchor / web3.js error, if present.
 * Handles `AnchorError` (`err.error.errorCode.number`), a bare `err.code`, and a
 * `custom program error: 0x...` string in the logs/message.
 */
export function extractCustomErrorCode(err: unknown): number | undefined {
  const anyErr = err as {
    error?: { errorCode?: { number?: number } };
    code?: number;
    logs?: string[];
  };
  const anchorNumber = anyErr?.error?.errorCode?.number;
  if (typeof anchorNumber === "number") return anchorNumber;
  if (typeof anyErr?.code === "number" && anyErr.code >= 6000) return anyErr.code;
  const text =
    (Array.isArray(anyErr?.logs) ? anyErr!.logs!.join("\n") : "") +
    "\n" +
    (err instanceof Error ? err.message : String(err));
  const m = text.match(/custom program error: 0x([0-9a-fA-F]+)/);
  if (m) return parseInt(m[1], 16);
  return undefined;
}

/**
 * Map a raw error thrown by a `.rpc()` call to a `CausalRewardsError` for the given
 * program, if it corresponds to a known custom error code. Otherwise returns the
 * original error unchanged so nothing is swallowed.
 */
export function mapProgramError(program: ProgramName, err: unknown): unknown {
  const code = extractCustomErrorCode(err);
  if (code === undefined) return err;
  const info = lookupProgramError(program, code);
  if (!info) return err;
  return new CausalRewardsError(program, info, err);
}
