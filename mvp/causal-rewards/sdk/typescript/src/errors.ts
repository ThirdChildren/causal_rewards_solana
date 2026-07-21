/**
 * Program error-code → human-readable message maps, one per M2 program, plus a
 * helper that turns a raw Anchor/RPC error into a readable `CausalRewardsError`.
 *
 * Codes are the `errors[]` arrays of the four IDLs (Anchor custom errors start at
 * 6000). Kept as explicit tables so the mapping is reviewable and stable even if a
 * caller only has a bare custom-error number from a simulated transaction.
 */

export interface ProgramErrorInfo {
  code: number;
  name: string;
  msg: string;
}

type ErrorTable = Record<number, ProgramErrorInfo>;

function table(entries: Array<[number, string, string]>): ErrorTable {
  const t: ErrorTable = {};
  for (const [code, name, msg] of entries) t[code] = { code, name, msg };
  return t;
}

export const EXPERIMENT_REGISTRY_ERRORS = table([
  [6000, "NotDevnet", "Protocol config cluster is not devnet (Invariant 7)"],
  [6001, "FeeNotZero", "Fee must be hard-zero (Invariant 7)"],
  [6002, "Paused", "Protocol is paused (emergency)"],
  [6003, "WrongStatus", "Experiment is not in the required status for this transition"],
  [6004, "Unauthorized", "Signer is not authorized for this action"],
  [6005, "MultisigThresholdNotMet", "Multisig threshold not met"],
  [6006, "InvalidMultisig", "Invalid multisig configuration"],
  [6007, "InvalidExperimentId", "experiment_id is empty or too long"],
  [6008, "InvalidWindowOrdering", "Window ordering invalid: require active_start <= active_end <= evaluation_deadline"],
  [6009, "FreezeDeadlinePassed", "freeze_by is in the past"],
  [6010, "FreezeWindowClosed", "Freeze deadline has passed; cannot freeze"],
  [6011, "SeedCommitmentMismatch", "Revealed seed does not open the frozen seed commitment (Invariant 1)"],
  [6012, "SeedAlreadyRevealed", "Seed already revealed; assignment cannot be re-chosen"],
  [6013, "CohortAlreadyPublished", "Cohort root already published"],
  [6014, "CohortNotPublished", "Seed must be revealed only after the cohort root is published"],
  [6015, "UnauthorizedCaller", "Caller program is not the registered authority for this transition"],
  [6016, "EvaluationInvalidated", "Evaluation was invalidated by an upheld challenge; resubmit required"],
  [6017, "ChallengeWindowNotElapsed", "Challenge window has not elapsed and challenges remain unresolved"],
  [6018, "OpenChallengesRemain", "Open challenges remain unresolved"],
  [6019, "ClaimWindowNotElapsed", "Claim window has not elapsed"],
  [6020, "MathOverflow", "Checked arithmetic overflow"],
  [6021, "InvalidThreshold", "Threshold must be >= 1 and <= number of signers"],
  [6022, "MintMismatch", "Vault mint does not match experiment mint"],
]);

export const EVIDENCE_REGISTRY_ERRORS = table([
  [6000, "WrongStatus", "Experiment is not Active"],
  [6001, "Unauthorized", "Signer is not the coordinator"],
  [6002, "InvalidCohortId", "cohort_id empty or too long"],
  [6003, "InvalidTimeRange", "time_range invalid: require start < end"],
  [6004, "TimeRangeOutsideActiveWindow", "time_range outside the active window"],
  [6005, "InconsistentCounts", "distinct_signers exceeds total observation count"],
  [6006, "PrevEpochMissing", "previous epoch does not exist (epochs must be monotonic, no gaps)"],
  [6007, "MathOverflow", "Checked arithmetic overflow"],
]);

export const SETTLEMENT_ERRORS = table([
  [6000, "WrongStatus", "Experiment is not in the required status"],
  [6001, "Unauthorized", "Signer not authorized"],
  [6002, "SeedNotRevealed", "Seed has not been revealed"],
  [6003, "ActiveWindowNotEnded", "Active window has not ended"],
  [6004, "EvaluationDeadlinePassed", "Evaluation deadline has passed"],
  [6005, "ContainerDigestMismatch", "Echoed analysis_container_digest does not match the frozen one"],
  [6006, "NoEvidence", "No evidence epoch exists"],
  [6007, "MultisigThresholdNotMet", "Multisig threshold not met"],
  [6008, "AllocationExceedsBudget", "Allocation exceeds budget"],
  [6009, "InvalidMerkleProof", "Merkle proof of the reward leaf is invalid"],
  [6010, "ClaimWindowClosed", "Claim window is closed"],
  [6011, "ClaimWindowNotElapsed", "Claim window has not elapsed"],
  [6012, "WrongVault", "Vault does not match experiment"],
  [6013, "WrongExperiment", "Evaluation/Distribution does not belong to this experiment"],
  [6014, "MintMismatch", "Token mint mismatch"],
  [6015, "MathOverflow", "Checked arithmetic overflow"],
]);

export const CHALLENGE_ERRORS = table([
  [6000, "WrongStatus", "Experiment is not in the required status"],
  [6001, "NoLiveEvaluation", "No live evaluation to challenge"],
  [6002, "ChallengeWindowClosed", "Challenge window is closed"],
  [6003, "BondTooLow", "Bond is below the required minimum"],
  [6004, "AlreadyResolved", "Challenge already resolved"],
  [6005, "MultisigThresholdNotMet", "Multisig threshold not met"],
  [6006, "WrongBondDestination", "Bond destination owner is wrong for this resolution"],
  [6007, "WrongBondVault", "Bond vault does not match challenge"],
  [6008, "WrongExperiment", "Challenge does not belong to this experiment"],
  [6009, "Unauthorized", "Signer not authorized"],
  [6010, "MintMismatch", "Token mint mismatch"],
]);

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
 * Handles both `AnchorError` (`err.error.errorCode.number`) and
 * `SendTransactionError` logs / `err.code`.
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
  // Fall back to parsing `custom program error: 0x...` from logs / message.
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
