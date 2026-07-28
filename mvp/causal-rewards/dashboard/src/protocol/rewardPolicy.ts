/**
 * The reward-policy ADAPTER — the single seam between the UI and reward-policy semantics.
 *
 * Why this file exists: a v1.2 reward-policy decision (multiplicity regime / curve floor,
 * see `docs/m3-integration-and-spec-round.md` §2) is pending at the time of writing. The UI
 * must not bake in a regime or hardcode curve parameters, or that decision forces a rewrite.
 *
 * Rules for this module:
 *  - Read reward-policy semantics ONLY from the frozen manifest. Never from a constant here.
 *  - When a field the UI would like does not exist in the frozen spec version, say so
 *    explicitly ("not a frozen field in spec v1.0.0") rather than inventing or defaulting.
 *  - Never recompute a payout. Payout amounts come from the committed reward leaf set.
 *
 * When v1.2 lands, the only edits should be inside this file: new field names to read and
 * new labels. The views consume the descriptors below and do not know the field names.
 */
import type { FrozenManifest, RewardPolicyRaw } from "./types";

export type MultiplicityRegime =
  | "none"
  | "bonferroni"
  | "sidak"
  | "benjamini_hochberg"
  | "unspecified";

export interface MultiplicityDescriptor {
  regime: MultiplicityRegime;
  label: string;
  /** The manifest path we read it from, or null when the field does not exist in this spec. */
  sourceField: string | null;
  /** Shown next to the label. Honest about what the frozen manifest does and does not pin. */
  note: string;
}

/**
 * Field names the manifest may carry a multiplicity regime under, in priority order.
 * v1.0.0 carries none of these — the descriptor then reports `unspecified`, which is the
 * truth, not a placeholder.
 */
const MULTIPLICITY_PATHS: Array<[string, (m: FrozenManifest) => unknown]> = [
  ["analysis_plan.multiplicity_regime", (m) => rawAnalysis(m)["multiplicity_regime"]],
  ["analysis_plan.multiple_testing_correction", (m) => rawAnalysis(m)["multiple_testing_correction"]],
  ["reward_policy.multiplicity_regime", (m) => m.rewardPolicy.extra["multiplicity_regime"]],
];

function rawAnalysis(m: FrozenManifest): Record<string, unknown> {
  const a = m.unmodeled["analysis_plan"];
  return a && typeof a === "object" ? (a as Record<string, unknown>) : {};
}

const REGIME_LABEL: Record<MultiplicityRegime, string> = {
  none: "Per-cohort tests, no family-wise correction",
  bonferroni: "Bonferroni family-wise correction",
  sidak: "Šidák family-wise correction",
  benjamini_hochberg: "Benjamini–Hochberg false-discovery-rate control",
  unspecified: "Not pinned by the frozen manifest",
};

export function describeMultiplicity(manifest: FrozenManifest | null): MultiplicityDescriptor {
  if (!manifest) {
    return {
      regime: "unspecified",
      label: REGIME_LABEL.unspecified,
      sourceField: null,
      note: "No frozen manifest available from this source.",
    };
  }
  for (const [path, get] of MULTIPLICITY_PATHS) {
    const v = get(manifest);
    if (typeof v === "string" && v.length > 0) {
      const key = v.toLowerCase().replace(/[-\s]/g, "_") as MultiplicityRegime;
      const regime: MultiplicityRegime = key in REGIME_LABEL ? key : "unspecified";
      return {
        regime,
        label: regime === "unspecified" ? `${v} (not modelled by this dashboard)` : REGIME_LABEL[regime],
        sourceField: path,
        note: `Frozen in the manifest at ${path}.`,
      };
    }
  }
  return {
    regime: "unspecified",
    label: REGIME_LABEL.unspecified,
    sourceField: null,
    note:
      `Spec version ${manifest.specVersion} has no multiplicity field. Each cohort's ` +
      `one-sided test is applied independently, with no family-wise or false-discovery ` +
      `correction. Read the conservative bounds accordingly.`,
  };
}

export interface CurveBreakpoint {
  /** Conservative effect on the frozen micro scale, as committed (string, never a float). */
  xMicro: string;
  /** Reward in mint base units, as committed. */
  yBaseUnits: string;
}

export interface CurveDescriptor {
  type: string;
  hash: string;
  breakpoints: CurveBreakpoint[];
  monotonic: boolean;
  /** Null when the manifest pins no floor; a v1.2 curve floor would surface here. */
  floorMicro: string | null;
}

export function describeCurve(policy: RewardPolicyRaw): CurveDescriptor {
  const breakpoints = policy.rewardCurveBreakpoints.map(([x, y]) => ({
    xMicro: x,
    yBaseUnits: y,
  }));
  const floor = policy.extra["conservative_effect_floor_micro"];
  return {
    type: policy.rewardCurveType,
    hash: policy.rewardCurveHash,
    breakpoints,
    monotonic: policy.rewardCurveType.includes("monotonic"),
    floorMicro: typeof floor === "string" ? floor : null,
  };
}

/**
 * The conservative-payout rule (invariant 3) as displayable text, sourced from the frozen
 * analysis plan. The dashboard states the rule; it does not apply it.
 */
export function describeConservativeRule(manifest: FrozenManifest | null): string {
  if (!manifest) return "conservative_effect = max(0, effect − critical_value × standard_error)";
  const cv = microToDecimalString(manifest.analysisPlan.criticalValueMicro, 6);
  const level = microToDecimalString(manifest.analysisPlan.confidenceLevelMicro, 6);
  return (
    `conservative_effect = max(0, effect − ${cv} × standard_error) ` +
    `(${manifest.analysisPlan.testSidedness.replace(/_/g, " ")}, confidence ${level}, ` +
    `${manifest.analysisPlan.criticalValueReference.replace(/_/g, " ")})`
  );
}

/** Render a micro-scaled integer string as a decimal string. Exact — no float arithmetic. */
export function microToDecimalString(micro: string, scale = 6): string {
  if (!/^-?\d+$/.test(micro)) return micro;
  const neg = micro.startsWith("-");
  const digits = (neg ? micro.slice(1) : micro).padStart(scale + 1, "0");
  const whole = digits.slice(0, digits.length - scale);
  const frac = digits.slice(digits.length - scale).replace(/0+$/, "");
  return `${neg ? "-" : ""}${whole}${frac ? "." + frac : ""}`;
}
