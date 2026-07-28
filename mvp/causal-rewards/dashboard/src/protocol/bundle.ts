/**
 * Parse an audit bundle (`bundle_layout_version` 1.0.0) into the dashboard view model.
 *
 * The bundle is the content-addressed source of truth; this module only *reads* it. It never
 * recomputes a root and never presents a root as verified — `roots.json` is an untrusted
 * published claim, exactly as the verifier CLI treats it. The UI says so on screen.
 *
 * Slot contract (ratified, `docs/m3-integration-and-spec-round.md` §1):
 *   rewards.parquet         = the on-chain reward leaf set (what the reward root commits)
 *   rewards_detail.parquet  = supplementary per-(cohort, recipient) detail, NOT committed
 *   analysis.json           = the causal-engine artifact; its CJSON hash is result_artifact_hash
 */
import { readLogicalTable } from "./parquet";
import { assertCohortLevelColumns } from "./privacy";
import type {
  AssignmentRow,
  BundleFiles,
  CohortResultRow,
  DistributionView,
  EvidenceEpochView,
  FrozenManifest,
  ProvenanceRecord,
  PublishedRoots,
  ResultView,
  RewardLeafView,
  RewardPolicyRaw,
  SensitivityRow,
} from "./types";

const dec = new TextDecoder();

function readJson(files: BundleFiles, path: string): Record<string, unknown> | null {
  const b = files.get(path);
  if (!b) return null;
  return JSON.parse(dec.decode(b)) as Record<string, unknown>;
}

function obj(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}
function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : fallback;
}
function strOrNull(v: unknown): string | null {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : null;
}
function strArray(v: unknown): string[] {
  return Array.isArray(v) ? v.map((x) => str(x)) : [];
}
function strRecord(v: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [k, val] of Object.entries(obj(v))) out[k] = typeof val === "string" ? val : JSON.stringify(val);
  return out;
}

// ---------------------------------------------------------------------------- manifest

export function parseManifest(raw: Record<string, unknown>): FrozenManifest {
  const known = new Set([
    "experiment_id",
    "title",
    "description",
    "spec_version",
    "manifest_version",
    "network",
    "created_at",
    "windows",
    "authorities",
    "primary_outcome",
    "estimand",
    "design",
    "treatment",
    "analysis_plan",
    "reward_policy",
    "assignment",
  ]);
  const unmodeled: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(raw)) if (!known.has(k)) unmodeled[k] = v;
  // analysis_plan is kept in `unmodeled` too, so the reward-policy adapter can look for
  // fields a future spec version adds without this parser needing to know their names.
  unmodeled["analysis_plan"] = raw["analysis_plan"];

  const w = obj(raw["windows"]);
  const a = obj(raw["authorities"]);
  const ms = obj(a["authority_multisig"]);
  const po = obj(raw["primary_outcome"]);
  const es = obj(raw["estimand"]);
  const cd = obj(es["cohort_definition"]);
  const tb = obj(es["time_block"]);
  const de = obj(raw["design"]);
  const tr = obj(raw["treatment"]);
  const ap = obj(raw["analysis_plan"]);
  const sc = obj(obj(raw["assignment"])["seed_commitment"]);

  return {
    experimentId: str(raw["experiment_id"]),
    title: str(raw["title"]),
    description: str(raw["description"]),
    specVersion: str(raw["spec_version"]),
    manifestVersion: str(raw["manifest_version"]),
    cluster: str(obj(raw["network"])["cluster"], "unknown"),
    createdAt: str(raw["created_at"]),
    windows: {
      freezeBy: str(w["freeze_by"]),
      activeStart: str(w["active_start"]),
      activeEnd: str(w["active_end"]),
      evaluationDeadline: str(w["evaluation_deadline"]),
      challengeWindowSeconds: str(w["challenge_window_seconds"]),
      claimWindowSeconds: str(w["claim_window_seconds"]),
    },
    authorities: {
      coordinatorPubkey: str(a["coordinator_pubkey"]),
      evaluatorPubkey: str(a["evaluator_pubkey"]),
      multisigThreshold: str(ms["threshold"]),
      multisigSigners: strArray(ms["signers"]),
      challengeBondBaseUnits: str(a["challenge_bond_base_units"]),
    },
    primaryOutcome: {
      metricId: str(po["metric_id"]),
      description: str(po["description"]),
      unitOfMeasure: str(po["unit_of_measure"]),
      improvementDirection: str(po["improvement_direction"]),
    },
    estimand: {
      unitType: str(es["unit_type"]),
      effectDefinition: str(es["effect_definition"]),
      cohortCount: str(cd["cohort_count"]),
      cohortScheme: str(cd["scheme"]),
      spatialResolution: str(cd["spatial_resolution"]),
      blockCount: str(tb["block_count"]),
      blockSeconds: str(tb["block_seconds"]),
    },
    design: {
      template: str(de["template"]),
      eligibleForStrongCausalClaim: de["eligible_for_strong_causal_claim"] === true,
      parameters: strRecord(de["parameters"]),
    },
    treatment: {
      assignmentMethod: str(tr["assignment_method"]),
      treatedFractionMicro: str(tr["treated_fraction_micro"]),
      description: str(tr["description"]),
    },
    analysisPlan: {
      estimator: str(ap["estimator"]),
      standardErrorMethod: str(ap["standard_error_method"]),
      testSidedness: str(ap["test_sidedness"]),
      confidenceLevelMicro: str(ap["confidence_level_micro"]),
      criticalValueMicro: str(ap["critical_value_micro"]),
      criticalValueReference: str(ap["critical_value_reference"]),
      covariateAdjustment: strArray(ap["covariate_adjustment"]),
      sensitivityAnalyses: strArray(ap["sensitivity_analyses"]),
      minimumSample: strRecord(ap["minimum_sample"]),
      analysisContainerDigest: str(ap["analysis_container_digest"]),
    },
    rewardPolicy: parseRewardPolicy(obj(raw["reward_policy"])),
    seedCommitment: {
      algo: str(sc["algo"]),
      scheme: str(sc["scheme"]),
      commitmentHex: str(sc["commitment_hex"]),
    },
    unmodeled,
  };
}

function parseRewardPolicy(rp: Record<string, unknown>): RewardPolicyRaw {
  const curve = obj(rp["reward_curve"]);
  const bps = Array.isArray(curve["breakpoints"])
    ? (curve["breakpoints"] as unknown[]).map((p) => {
        const pair = Array.isArray(p) ? p : [];
        return [str(pair[0]), str(pair[1])] as [string, string];
      })
    : [];
  const known = new Set([
    "budget_base_units",
    "mint",
    "overflow_policy",
    "unused_budget_policy",
    "reward_curve",
    "reward_curve_hash",
    "intra_cohort_split",
    "positive_improvement_transform",
  ]);
  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(rp)) if (!known.has(k)) extra[k] = v;
  return {
    budgetBaseUnits: str(rp["budget_base_units"]),
    mint: str(rp["mint"]),
    overflowPolicy: str(rp["overflow_policy"]),
    unusedBudgetPolicy: str(rp["unused_budget_policy"]),
    rewardCurveType: str(curve["type"]),
    rewardCurveBreakpoints: bps,
    rewardCurveHash: str(rp["reward_curve_hash"]),
    intraCohortSplit: strRecord(rp["intra_cohort_split"]),
    positiveImprovementTransform: strRecord(rp["positive_improvement_transform"]),
    extra,
  };
}

// ------------------------------------------------------------------------------- roots

export function parseRoots(raw: Record<string, unknown>): PublishedRoots {
  const r = obj(raw["roots"]);
  const epochs = Array.isArray(r["evidence_epochs"]) ? (r["evidence_epochs"] as unknown[]) : [];
  return {
    bundleLayoutVersion: str(raw["bundle_layout_version"]),
    manifestHashHex: str(raw["manifest_hash"]),
    assignmentRootHex: strOrNull(r["assignment_root_hex"]),
    rewardRootHex: strOrNull(r["reward_root_hex"]),
    resultArtifactHashHex: strOrNull(r["result_artifact_hash"]),
    evidenceEpochs: epochs.map((e) => {
      const o = obj(e);
      return {
        epochIndex: Number(str(o["epoch_index"], "0")),
        rootHex: str(o["evidence_epoch_root_hex"]),
        file: str(o["file"]),
      };
    }),
  };
}

export function parseProvenance(raw: Record<string, unknown> | null): ProvenanceRecord | null {
  if (!raw) return null;
  return {
    sourceCommit: strOrNull(raw["source_commit"]),
    containerDigest: strOrNull(raw["container_digest"]),
    executionTimestamp: strOrNull(raw["execution_timestamp"]),
    manifestHashHex: strOrNull(raw["manifest_hash"]),
    note: strOrNull(raw["reference_note"]),
  };
}

// ------------------------------------------------------------------------------ result

/**
 * `analysis.json` → the result view.
 *
 * The engine's schema is normative for content (§1.4) and richer than what any single UI
 * version models. We read the keys we know under both the ratified names and the engine's
 * alternates, and hand the whole object to the UI as `raw` so nothing committed is hidden.
 */
export function parseAnalysis(raw: Record<string, unknown> | null): ResultView {
  if (!raw) {
    return {
      present: false,
      estimand: null,
      specVersion: null,
      engineName: null,
      analysisContainerDigest: null,
      resultArtifactHashHex: null,
      primaryEffect: null,
      evidenceEpochRoots: [],
      rewardSummary: null,
      cohorts: [],
      excluded: [],
      sensitivity: [],
      raw: null,
    };
  }
  const engine = obj(raw["engine"]);
  const pe = obj(raw["primary_effect"] ?? raw["primary_estimate"]);
  const rs = obj(raw["reward_summary"]);

  const cohorts: CohortResultRow[] = [];
  const excluded: CohortResultRow[] = [];
  const cohortSrc = Array.isArray(raw["cohorts"])
    ? (raw["cohorts"] as unknown[])
    : Array.isArray(raw["per_cohort"])
      ? (raw["per_cohort"] as unknown[])
      : [];
  for (const c of cohortSrc) {
    const o = obj(c);
    const row: CohortResultRow = {
      cohortId: str(o["cohort_id"]),
      arm: strOrNull(o["arm"]),
      pointEstimateMicro: strOrNull(o["point_estimate_micro"]),
      standardErrorMicro: strOrNull(o["standard_error_micro"]),
      conservativeEffectMicro: strOrNull(o["conservative_effect_micro"]),
      eligible: typeof o["eligible"] === "boolean" ? (o["eligible"] as boolean) : null,
      exclusionReason: strOrNull(o["exclusion_reason"] ?? o["excluded_reason"]),
      observations: strOrNull(o["observations"] ?? o["n_observations"]),
    };
    if (row.eligible === false || row.exclusionReason) excluded.push(row);
    else cohorts.push(row);
  }
  assertCohortLevelColumns(
    "analysis.json cohort rows",
    cohortSrc.length ? Object.keys(obj(cohortSrc[0])) : [],
  );

  const sensitivity: SensitivityRow[] = [];
  const sensSrc = raw["sensitivity"] ?? raw["sensitivity_analyses"];
  if (Array.isArray(sensSrc)) {
    for (const s of sensSrc) {
      if (typeof s === "string") sensitivity.push({ name: s, detail: "" });
      else {
        const o = obj(s);
        sensitivity.push({
          name: str(o["name"] ?? o["analysis"]),
          detail: str(o["summary"] ?? o["detail"] ?? JSON.stringify(o)),
        });
      }
    }
  } else if (sensSrc && typeof sensSrc === "object") {
    for (const [k, v] of Object.entries(obj(sensSrc))) {
      sensitivity.push({ name: k, detail: typeof v === "string" ? v : JSON.stringify(v) });
    }
  }

  const hasEffect = "point_estimate_micro" in pe;
  return {
    present: true,
    estimand: strOrNull(raw["estimand"]),
    specVersion: strOrNull(raw["spec_version"]),
    engineName: strOrNull(engine["name"]),
    analysisContainerDigest: strOrNull(engine["analysis_container_digest"]),
    resultArtifactHashHex: null, // reproduced by the verifier, never asserted here
    primaryEffect: hasEffect
      ? {
          pointEstimateMicro: str(pe["point_estimate_micro"]),
          standardErrorMicro: str(pe["standard_error_micro"]),
          conservativeEffectMicro: str(pe["conservative_effect_micro"]),
        }
      : null,
    evidenceEpochRoots: strArray(raw["evidence_epoch_roots"]),
    rewardSummary: {
      rewardRootHex: strOrNull(rs["reward_root_hex"]),
      totalBaseUnits: strOrNull(rs["total_base_units"]),
    },
    cohorts,
    excluded,
    sensitivity,
    raw,
  };
}

// ----------------------------------------------------------------------------- tables

export async function parseAssignment(files: BundleFiles): Promise<AssignmentRow[]> {
  const b = files.get("assignment.parquet");
  if (!b) return [];
  const t = await readLogicalTable(b);
  assertCohortLevelColumns("assignment.parquet", t.columns);
  return t.rows.map((r) => ({
    cohortId: r["cohort_id"] ?? "",
    arm: r["arm"] ?? "",
    leafHashHex: r["leaf_hash_hex"] ?? "",
  }));
}

export async function parseRewardLeaves(files: BundleFiles): Promise<RewardLeafView[]> {
  const b = files.get("rewards.parquet");
  if (!b) return [];
  const t = await readLogicalTable(b);
  assertCohortLevelColumns("rewards.parquet", t.columns);
  return t.rows.map((r) => ({
    leafIndex: r["leaf_index"] ?? "",
    recipientHex: r["recipient_hex"] ?? "",
    amountBaseUnits: r["amount_base_units"] ?? "",
    leafHashHex: r["leaf_hash_hex"] ?? "",
    claimed: null,
  }));
}

export async function parseEvidenceEpochs(
  files: BundleFiles,
  roots: PublishedRoots,
): Promise<EvidenceEpochView[]> {
  const out: EvidenceEpochView[] = [];
  for (const e of roots.evidenceEpochs) {
    const b = files.get(e.file);
    let leafCount: number | null = null;
    if (b) {
      const t = await readLogicalTable(b);
      assertCohortLevelColumns(e.file, t.columns);
      leafCount = t.rows.length;
    }
    out.push({
      epochIndex: e.epochIndex,
      rootHex: e.rootHex,
      file: e.file,
      leafCount,
      cohortId: null,
      timeStart: null,
      timeEnd: null,
      signerSetRootHex: null,
      observationsRootHex: null,
      acceptedCount: null,
      rejectedCount: null,
      distinctSigners: null,
      contentHashHex: null,
      producer: null,
    });
  }
  return out;
}

export function distributionFromBundle(
  roots: PublishedRoots,
  leaves: RewardLeafView[],
): DistributionView {
  let total = 0n;
  let ok = true;
  for (const l of leaves) {
    if (!/^\d+$/.test(l.amountBaseUnits)) {
      ok = false;
      break;
    }
    total += BigInt(l.amountBaseUnits);
  }
  return {
    present: leaves.length > 0 || roots.rewardRootHex !== null,
    rewardRootHex: roots.rewardRootHex,
    totalAllocatedBaseUnits: null,
    unallocatedBaseUnits: null,
    claimWindowEnd: null,
    leaves,
    leafTotalBaseUnits: ok ? total.toString() : null,
  };
}

export { readJson as readBundleJson };
