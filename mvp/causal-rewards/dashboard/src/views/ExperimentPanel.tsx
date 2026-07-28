/**
 * Experiment view — the frozen pre-registration, in full.
 *
 * Everything on this page was fixed before any outcome data was analysed. The page's job is
 * to make that checkable, so it shows the frozen values verbatim (windows as committed
 * strings, authorities as pubkeys, the reward curve as its committed breakpoints and hash)
 * rather than a friendly summary that could paper over a change.
 */
import { DataTable } from "../components/DataTable";
import { Absent, Field, Fields, Note, Section } from "../components/primitives";
import { Hash } from "../components/primitives";
import { StatusRail } from "../components/StatusRail";
import {
  describeConservativeRule,
  describeCurve,
  describeMultiplicity,
  formatBaseUnits,
  microToDecimalString,
} from "../protocol/rewardPolicy";
import type { ExperimentSnapshot } from "../protocol/sources/types";

/** Unix seconds as committed → a readable UTC instant, with the raw value kept visible. */
function whenUtc(seconds: string | null): string {
  if (!seconds || !/^\d+$/.test(seconds)) return "—";
  const d = new Date(Number(seconds) * 1000);
  if (Number.isNaN(d.getTime())) return seconds;
  return `${d.toISOString().replace(".000Z", "Z")} (${seconds})`;
}

function duration(seconds: string | null): string {
  if (!seconds || !/^\d+$/.test(seconds)) return "—";
  const n = Number(seconds);
  const days = Math.floor(n / 86400);
  const hours = Math.floor((n % 86400) / 3600);
  const parts = [days ? `${days}d` : "", hours ? `${hours}h` : ""].filter(Boolean);
  return `${parts.join(" ") || `${n}s`} (${seconds}s)`;
}

export function ExperimentPanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const { experiment } = snapshot;
  const m = experiment.manifest;

  return (
    <div className="panel stack-lg">
      <StatusRail
        status={experiment.status}
        provenance={experiment.statusProvenance}
        aborted={experiment.aborted}
      />

      {!m ? (
        <Note tone="danger">
          This source published no <code>manifest.json</code>, so nothing on this page is
          frozen state. Fetch the content-addressed bundle directly and verify it before
          relying on anything shown elsewhere in this dashboard.
        </Note>
      ) : (
        <>
          <Section title="What was measured" eyebrow="frozen before any data was analysed">
            <p className="prose">{m.description}</p>
            <Fields>
              <Field label="Primary outcome">
                {m.primaryOutcome.description}
                <br />
                <code>{m.primaryOutcome.metricId}</code> in{" "}
                <code>{m.primaryOutcome.unitOfMeasure}</code>, improvement ={" "}
                <code>{m.primaryOutcome.improvementDirection}</code>
              </Field>
              <Field label="Estimand">{m.estimand.effectDefinition}</Field>
              <Field label="Experimental unit">
                <code>{m.estimand.unitType}</code> — {m.estimand.cohortCount} cohorts by{" "}
                {m.estimand.cohortScheme} ({m.estimand.spatialResolution}), {m.estimand.blockCount}{" "}
                blocks of {m.estimand.blockSeconds}s
              </Field>
              <Field label="Design">
                <code>{m.design.template}</code>, assignment{" "}
                <code>{m.treatment.assignmentMethod}</code> at treated fraction{" "}
                {microToDecimalString(m.treatment.treatedFractionMicro)}
                {m.design.eligibleForStrongCausalClaim
                  ? " — eligible for the strongest causal claim this protocol supports"
                  : " — NOT eligible for the strongest causal claim; results are discovery-only"}
              </Field>
              <Field label="Design parameters">
                {Object.entries(m.design.parameters).length === 0 ? (
                  <Absent why="the frozen manifest lists no design parameters" />
                ) : (
                  <ul style={{ margin: 0, paddingLeft: "1.1rem" }}>
                    {Object.entries(m.design.parameters).map(([k, v]) => (
                      <li key={k}>
                        <code>{k}</code> = <code>{v}</code>
                      </li>
                    ))}
                  </ul>
                )}
              </Field>
            </Fields>
            <Note tone="caveat">
              The unit of analysis is a geographic cohort within a time block, never an
              individual device. No individual device's counterfactual is claimed or paid on.
            </Note>
          </Section>

          <Section title="Frozen analysis plan" eyebrow="pinned before the seed was revealed">
            <Fields>
              <Field label="Estimator">
                <code>{m.analysisPlan.estimator}</code>, standard errors{" "}
                <code>{m.analysisPlan.standardErrorMethod}</code>
              </Field>
              <Field label="Conservative rule">
                <code>{describeConservativeRule(m)}</code>
              </Field>
              <Field label="Covariate adjustment">
                {m.analysisPlan.covariateAdjustment.length === 0 ? (
                  <Absent why="no covariates were frozen" />
                ) : (
                  m.analysisPlan.covariateAdjustment.map((c) => <code key={c}>{c} </code>)
                )}
              </Field>
              <Field label="Pre-registered sensitivity">
                {m.analysisPlan.sensitivityAnalyses.length === 0 ? (
                  <Absent why="no sensitivity analyses were frozen" />
                ) : (
                  m.analysisPlan.sensitivityAnalyses.map((c) => <code key={c}>{c} </code>)
                )}
              </Field>
              <Field label="Minimum sample rule">
                {Object.entries(m.analysisPlan.minimumSample).map(([k, v]) => (
                  <span key={k}>
                    <code>{k}</code> = {v}{" "}
                  </span>
                ))}
              </Field>
              <Field label="Multiple testing">
                {(() => {
                  const mult = describeMultiplicity(m);
                  return (
                    <>
                      {mult.label}
                      <br />
                      <span style={{ color: "var(--ink-soft)" }}>{mult.note}</span>
                    </>
                  );
                })()}
              </Field>
              <Field label="Analysis container">
                <Hash value={m.analysisPlan.analysisContainerDigest} chars={24} />
              </Field>
            </Fields>
          </Section>

          <Section title="Reward policy" eyebrow="frozen curve, frozen budget">
            <Fields>
              <Field label="Budget">
                {formatBaseUnits(m.rewardPolicy.budgetBaseUnits)} base units of mint{" "}
                <Hash value={m.rewardPolicy.mint} chars={10} />
              </Field>
              <Field label="Unused budget">
                <code>{m.rewardPolicy.unusedBudgetPolicy}</code> — a zero or partial payout does
                not burn the budget
              </Field>
              <Field label="Overflow">
                <code>{m.rewardPolicy.overflowPolicy}</code>
              </Field>
              <Field label="Intra-cohort split">
                {Object.entries(m.rewardPolicy.intraCohortSplit).map(([k, v]) => (
                  <span key={k}>
                    <code>{k}</code> = <code>{v}</code>{" "}
                  </span>
                ))}
              </Field>
              <Field label="Curve hash">
                <Hash value={describeCurve(m.rewardPolicy).hash} chars={24} />
              </Field>
            </Fields>
            <DataTable
              source="frozen reward curve"
              caption={
                <>
                  Frozen reward curve (<code>{describeCurve(m.rewardPolicy).type}</code>). The
                  conservative bound goes in on the left; the cohort's budget share comes out on
                  the right.
                </>
              }
              columns={[
                {
                  key: "conservative_effect",
                  header: "conservative bound",
                  numeric: true,
                  render: (b) => microToDecimalString(b.xMicro),
                },
                {
                  key: "reward_base_units",
                  header: "reward (base units)",
                  numeric: true,
                  render: (b) => formatBaseUnits(b.yBaseUnits),
                },
              ]}
              rows={describeCurve(m.rewardPolicy).breakpoints}
              rowKey={(b) => b.xMicro}
              emptyMessage="The frozen manifest pins no curve breakpoints."
            />
          </Section>

          <Section title="Windows and authorities" eyebrow="who may act, and until when">
            <Fields>
              <Field label="Freeze by">{whenUtc(m.windows.freezeBy)}</Field>
              <Field label="Active window">
                {whenUtc(m.windows.activeStart)} → {whenUtc(m.windows.activeEnd)}
              </Field>
              <Field label="Evaluation deadline">{whenUtc(m.windows.evaluationDeadline)}</Field>
              <Field label="Challenge window">
                {duration(m.windows.challengeWindowSeconds)}
                {experiment.challengeWindowEnd
                  ? ` — ends ${whenUtc(experiment.challengeWindowEnd)}`
                  : ""}
              </Field>
              <Field label="Claim window">
                {duration(m.windows.claimWindowSeconds)}
                {experiment.claimWindowEnd ? ` — ends ${whenUtc(experiment.claimWindowEnd)}` : ""}
              </Field>
              <Field label="Coordinator">
                <Hash value={m.authorities.coordinatorPubkey} chars={20} />
              </Field>
              <Field label="Evaluator">
                <Hash value={m.authorities.evaluatorPubkey} chars={20} />
              </Field>
              <Field label="Authority multisig">
                {m.authorities.multisigThreshold} of {m.authorities.multisigSigners.length}
                <ul style={{ margin: "var(--s1) 0 0", paddingLeft: "1.1rem" }}>
                  {m.authorities.multisigSigners.map((s) => (
                    <li key={s}>
                      <Hash value={s} chars={20} />
                    </li>
                  ))}
                </ul>
              </Field>
              <Field label="Challenge bond">
                {formatBaseUnits(m.authorities.challengeBondBaseUnits)} base units
              </Field>
            </Fields>
          </Section>

          <Section title="Cohort assignment" eyebrow="derived from the committed seed">
            <Fields>
              <Field label="Assignment root">
                <Hash value={experiment.cohortRootHex} chars={64} />
              </Field>
              <Field label="Cohorts published">
                {experiment.cohortCount ?? <Absent why="this source publishes no cohort count" />}
              </Field>
              <Field label="Seed commitment scheme">
                <code>{m.seedCommitment.scheme || "—"}</code>
              </Field>
            </Fields>
            <DataTable
              source="assignment.parquet"
              caption="Every cohort's arm, with the leaf hash the assignment root is built from. Cohort-level only — no device appears in this table."
              columns={[
                { key: "cohort_id", header: "cohort", render: (r) => <code>{r.cohortId}</code> },
                { key: "arm", header: "arm", render: (r) => r.arm },
                {
                  key: "leaf_hash_hex",
                  header: "leaf hash",
                  render: (r) => <Hash value={r.leafHashHex} />,
                },
              ]}
              rows={snapshot.assignment}
              rowKey={(r) => r.cohortId}
              emptyMessage="No assignment table in this source. The cohort root alone still pins the assignment; fetch the bundle to see the leaves."
            />
          </Section>
        </>
      )}
    </div>
  );
}
