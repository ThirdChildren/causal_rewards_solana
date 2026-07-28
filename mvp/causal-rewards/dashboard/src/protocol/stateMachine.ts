/**
 * The experiment state machine, exactly as `specs/state-machine.md` defines it.
 *
 *   Draft -> Frozen -> Active -> Evaluating -> Challenged -> Final -> Closed
 *
 * `Challenged` is a loop state: `open_challenge` may re-enter it, and the experiment leaves
 * it for `Evaluating` only when `open_challenges` reaches 0 (spec §tx8). `Closed` is also
 * reachable early via `abort_experiment` from any pre-`Final` state, with `aborted = true`.
 *
 * This module is presentation logic only. It never decides state — it labels the state the
 * chain reports.
 */
import type { ExperimentStatus } from "./types";

export const STATUS_ORDER: readonly ExperimentStatus[] = [
  "draft",
  "frozen",
  "active",
  "evaluating",
  "challenged",
  "final",
  "closed",
] as const;

export interface StatusMeta {
  status: ExperimentStatus;
  label: string;
  /** One line, end-user voice: what is true of the experiment while it is in this state. */
  meaning: string;
  /** Is the frozen manifest binding at this point? Drives the seal/reveal treatment. */
  sealed: boolean;
}

export const STATUS_META: Record<ExperimentStatus, StatusMeta> = {
  draft: {
    status: "draft",
    label: "Draft",
    meaning: "The manifest can still change. Nothing is binding yet.",
    sealed: false,
  },
  frozen: {
    status: "frozen",
    label: "Frozen",
    meaning:
      "The manifest hash is committed on-chain. The design, outcome and analysis plan can no longer change.",
    sealed: true,
  },
  active: {
    status: "active",
    label: "Active",
    meaning: "Cohorts are assigned and evidence epochs are being anchored.",
    sealed: true,
  },
  evaluating: {
    status: "evaluating",
    label: "Evaluating",
    meaning: "Evidence is closed. The evaluator submits a result artifact hash and reward root.",
    sealed: true,
  },
  challenged: {
    status: "challenged",
    label: "Challenged",
    meaning:
      "At least one bonded challenge is open. Finality is paused until every challenge is resolved.",
    sealed: true,
  },
  final: {
    status: "final",
    label: "Final",
    meaning: "The reward root is finalized. Recipients can claim within the claim window.",
    sealed: true,
  },
  closed: {
    status: "closed",
    label: "Closed",
    meaning: "Terminal. The claim window has passed or the experiment was aborted.",
    sealed: true,
  },
};

export function statusIndex(status: ExperimentStatus): number {
  return STATUS_ORDER.indexOf(status);
}

/** Has the experiment reached at least `target` on the linear path? */
export function hasReached(status: ExperimentStatus, target: ExperimentStatus): boolean {
  return statusIndex(status) >= statusIndex(target);
}

/**
 * Normalize the SDK's Anchor enum object (`{ frozen: {} }`) to our string union.
 * Throws on an unrecognized variant rather than guessing — a new on-chain state must be
 * modelled deliberately, not rendered as something it is not.
 */
export function statusFromAnchor(value: unknown): ExperimentStatus {
  if (typeof value === "string") {
    const s = value.toLowerCase() as ExperimentStatus;
    if (STATUS_ORDER.includes(s)) return s;
    throw new Error(`unknown ExperimentStatus: ${value}`);
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value as Record<string, unknown>);
    const key = keys[0];
    if (keys.length === 1 && key && STATUS_ORDER.includes(key.toLowerCase() as ExperimentStatus)) {
      return key.toLowerCase() as ExperimentStatus;
    }
  }
  throw new Error(`unknown ExperimentStatus: ${JSON.stringify(value)}`);
}

/**
 * Freeze-before-reveal (invariant 1) as a displayable fact.
 *
 * `sealed` means the manifest is hash-committed on-chain and the assignment seed has NOT
 * been revealed yet: the pre-registration is provably still closed. Once the seed is
 * revealed, the same commitment lets anyone check the reveal opens it.
 */
export interface SealState {
  manifestSealed: boolean;
  seedRevealed: boolean;
  /** Short line for the seal chip. */
  summary: string;
}

export function sealState(status: ExperimentStatus, revealedSeedHex: string | null): SealState {
  const manifestSealed = STATUS_META[status].sealed;
  const seedRevealed = Boolean(revealedSeedHex);
  let summary: string;
  if (!manifestSealed) summary = "Not frozen yet — nothing is binding.";
  else if (!seedRevealed) summary = "Frozen and still sealed. The assignment seed is not revealed.";
  else summary = "Frozen before the seed was revealed. The reveal opens the committed hash.";
  return { manifestSealed, seedRevealed, summary };
}
