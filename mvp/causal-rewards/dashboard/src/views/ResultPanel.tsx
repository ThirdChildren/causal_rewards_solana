/**
 * Result view — the causal estimate, its uncertainty, and everything that qualifies it.
 *
 * Three rules this page is built around:
 *
 *  - **Invariant 6.** The standing caveat is rendered at the top, not buried at the bottom:
 *    on-chain checks bind commitments and settlement; they do not make the causal claim true.
 *    The page never uses the words "proven" or "verified" about the effect itself.
 *  - **Invariant 8.** A null distribution, a zero conservative bound, or a low-power run is a
 *    first-class outcome with its own headline and its own reasons — never an error banner,
 *    never an empty state, never hidden behind a happier number.
 *  - **Nothing derived.** Every number comes from `analysis.json` as committed. The dashboard
 *    does not re-estimate, re-round, or re-judge the engine's own sensitivity verdicts.
 */
import { DataTable } from "../components/DataTable";
import { EffectReadout } from "../components/EffectReadout";
import { Absent, Chip, Field, Fields, Hash, Note, Section, Vacant } from "../components/primitives";
import {
  describeConservativeRule,
  describeMultiplicity,
  formatBaseUnits,
  formatScaled,
  microToDecimalString,
} from "../protocol/rewardPolicy";
import type { ExperimentSnapshot } from "../protocol/sources/types";
import type { CohortResultRow } from "../protocol/types";

const isZeroPayout = (r: CohortResultRow) =>
  r.conservativeS === "0" || r.conservativeS === null || r.allocationBaseUnits === "0";

export function ResultPanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const r = snapshot.result;
  const m = snapshot.experiment.manifest;
  const scale = r.scaleExponent;

  if (!r.present) {
    return (
      <div className="panel">
        <Vacant title="No result artifact yet">
          A result appears once the evaluator submits it and the artifact hash is anchored
          on-chain. Until then there is deliberately nothing to read here: the frozen analysis
          plan on the Experiment tab is the whole of what has been committed.
        </Vacant>
      </div>
    );
  }

  const nullDistribution = r.rewardSummary?.nullDistribution === true;
  const paidLeaves = r.rewardSummary?.leafCount ?? null;
  const zeroPayout =
    nullDistribution || paidLeaves === "0" || r.primaryEffect?.conservativeS === "0";

  return (
    <div className="panel stack-lg">
      <Note tone="caveat">
        <strong>The chain verifies process, not physical truth.</strong>{" "}
        {r.identification.caveat ??
          "On-chain checks bind commitments and settlement only. This estimate is only as valid as the frozen design, the data, and the assumptions recorded in the manifest."}{" "}
        A passing <code>crp-verify</code> run means the published artifacts are internally
        consistent and match what was anchored — not that the effect is real.
      </Note>

      {zeroPayout ? (
        <Section title="This run paid out nothing" eyebrow="a valid result">
          <div className="row">
            <Chip tone="null">null distribution</Chip>
            {paidLeaves ? <Chip tone="null">{paidLeaves} reward leaves</Chip> : null}
          </div>
          <p className="prose">
            The frozen rules compiled no positive payout. That is an outcome the protocol is
            designed to produce and publish, not a failure of the pipeline and not an error in
            this page. The budget is unspent and, under the frozen policy, recoverable.
          </p>
          {r.rewardSummary && r.rewardSummary.nullReasons.length > 0 ? (
            <ul className="prose">
              {r.rewardSummary.nullReasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : null}
        </Section>
      ) : null}

      <Section title="Primary effect" eyebrow={r.estimandUnitType ?? "cohort-level estimand"}>
        {r.primaryEffect ? (
          <EffectReadout
            effect={r.primaryEffect}
            unit={m?.primaryOutcome.unitOfMeasure ?? null}
            improvementDirection={r.improvementDirection ?? m?.primaryOutcome.improvementDirection ?? null}
            conservativeRule={describeConservativeRule(m)}
          />
        ) : (
          <Absent why="this artifact publishes no primary estimate" />
        )}
        {r.estimandStatement ? <p className="prose">{r.estimandStatement}</p> : null}
        {r.primaryEffect?.seMethod ? (
          <p className="prose" style={{ fontSize: "var(--step--2)" }}>
            Standard error method as committed: {r.primaryEffect.seMethod}
          </p>
        ) : null}
      </Section>

      {r.identification.present ? (
        <Section title="Identification" eyebrow="what has to hold for this to mean anything">
          <div className="row">
            <Chip tone={r.identification.supportsStrongCausalClaim ? "develop" : "null"}>
              {r.identification.supportsStrongCausalClaim
                ? "supports the strongest claim this protocol makes"
                : "discovery-only"}
            </Chip>
            {r.identification.perCohortMode ? (
              <Chip tone="latent">per-cohort: {r.identification.perCohortMode}</Chip>
            ) : null}
          </div>
          <ul className="prose">
            {r.identification.assumptions.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </Section>
      ) : null}

      <Section title="Per-cohort results" eyebrow="the payable unit">
        <p className="prose">
          Reward flows from the conservative bound, not the point estimate. A cohort whose bound
          is zero contributes nothing and is shown here anyway — a row that pays nothing is part
          of the record.
        </p>
        <DataTable
          source="analysis.json cohorts"
          caption={`${r.cohorts.length} cohort(s) valued under the frozen rules.`}
          columns={[
            { key: "cohort_id", header: "cohort", render: (c) => <code>{c.cohortId}</code> },
            {
              key: "effect_s",
              header: "effect",
              numeric: true,
              render: (c) => formatScaled(c.effectS, scale),
            },
            {
              key: "standard_error_s",
              header: "std. error",
              numeric: true,
              render: (c) => formatScaled(c.standardErrorS, scale),
            },
            {
              key: "margin_s",
              header: "margin",
              numeric: true,
              render: (c) => formatScaled(c.marginS, scale),
            },
            {
              key: "conservative_effect_s",
              header: "conservative bound",
              numeric: true,
              render: (c) => (
                <span style={{ color: isZeroPayout(c) ? "var(--null)" : "var(--develop)" }}>
                  {formatScaled(c.conservativeS, scale)}
                </span>
              ),
            },
            {
              key: "allocation_base_units",
              header: "allocation",
              numeric: true,
              render: (c) => formatBaseUnits(c.allocationBaseUnits),
            },
            {
              key: "n_observations",
              header: "observations",
              numeric: true,
              render: (c) => c.nObservations ?? "—",
            },
            {
              key: "n_time_blocks",
              header: "blocks (T/C)",
              numeric: true,
              render: (c) =>
                c.nTimeBlocks ? `${c.nTreatedBlocks ?? "?"}/${c.nControlBlocks ?? "?"}` : "—",
            },
          ]}
          rows={r.cohorts}
          rowKey={(c) => c.cohortId}
          isZero={isZeroPayout}
          emptyMessage="This artifact publishes no per-cohort valuations. The primary estimate above is all it commits."
        />
        <Note>
          <strong>Multiple testing.</strong> {describeMultiplicity(m).label}.{" "}
          {describeMultiplicity(m).note}
        </Note>
      </Section>

      <Section title="Excluded from payout" eyebrow="stated, not silently dropped">
        <DataTable
          source="analysis.json excluded cohorts"
          caption={`${r.excluded.length} cohort(s) barred by the frozen rules.`}
          columns={[
            { key: "cohort_id", header: "cohort", render: (c) => <code>{c.cohortId}</code> },
            {
              key: "meets_minimum_sample",
              header: "min. sample",
              render: (c) => (c.meetsMinimumSample === false ? "not met" : "met"),
            },
            {
              key: "identified",
              header: "identified",
              render: (c) => (c.identified === false ? "no" : (c.identificationMode ?? "yes")),
            },
            {
              key: "exclusion_reasons",
              header: "reasons",
              render: (c) => (c.exclusionReasons.length ? c.exclusionReasons.join("; ") : "—"),
            },
            {
              key: "n_observations",
              header: "observations",
              numeric: true,
              render: (c) => c.nObservations ?? "—",
            },
          ]}
          rows={r.excluded}
          rowKey={(c) => c.cohortId}
          isZero={() => true}
          emptyMessage="No cohort was excluded by the frozen rules."
        />

        {r.excludedRecords.byReason.length > 0 || r.excludedRecords.total ? (
          <>
            <p className="prose">
              Records dropped before estimation, counted by reason. Total:{" "}
              <strong>{r.excludedRecords.total ?? "0"}</strong>.
            </p>
            <DataTable
              source="analysis.json excluded_records"
              columns={[
                { key: "reason", header: "reason", render: (e) => <code>{e.reason}</code> },
                { key: "count", header: "records", numeric: true, render: (e) => e.count },
              ]}
              rows={r.excludedRecords.byReason}
              rowKey={(e) => e.reason}
              emptyMessage="No records were dropped before estimation."
            />
          </>
        ) : null}
      </Section>

      {r.balance.present ? (
        <Section title="Covariate balance" eyebrow="did randomisation land where it should">
          <div className="row">
            <Chip tone={r.balance.passed ? "develop" : "null"}>
              {r.balance.passed ? "within the frozen threshold" : "outside the frozen threshold"}
            </Chip>
            {r.balance.gatesPayout === false ? (
              <Chip tone="latent">does not gate payout</Chip>
            ) : null}
          </div>
          <Fields>
            <Field label="Max |SMD|">
              {microToDecimalString(r.balance.maxAbsSmdMicro ?? "")} against a frozen threshold of{" "}
              {microToDecimalString(r.balance.thresholdMicro ?? "")}
            </Field>
            <Field label="Treated share">
              {microToDecimalString(r.balance.treatedShareMicro ?? "")}
            </Field>
          </Fields>
          <DataTable
            source="analysis.json balance covariates"
            columns={[
              { key: "name", header: "covariate", render: (c) => <code>{c.name}</code> },
              {
                key: "smd_micro",
                header: "standardised mean difference",
                numeric: true,
                render: (c) => microToDecimalString(c.smdMicro),
              },
              {
                key: "passed",
                header: "within threshold",
                render: (c) => (c.passed === false ? "no" : "yes"),
              },
            ]}
            rows={r.balance.covariates}
            rowKey={(c) => c.name}
            isZero={(c) => c.passed === false}
            emptyMessage="No covariates were checked for balance."
          />
        </Section>
      ) : null}

      <Section title="Sensitivity" eyebrow="pre-registered robustness checks">
        {r.sensitivity.length === 0 ? (
          <p className="prose">This artifact publishes no sensitivity analyses.</p>
        ) : (
          <div className="grid-2">
            {r.sensitivity.map((s) => (
              <article key={s.name} className="card stack">
                <div className="row">
                  <h3 style={{ fontSize: "var(--step-0)", margin: 0, fontWeight: 600 }}>
                    <code>{s.name}</code>
                  </h3>
                  {s.status ? (
                    <Chip tone={s.status === "ok" ? "develop" : "null"}>{s.status}</Chip>
                  ) : null}
                  {s.kind ? <Chip tone="latent">{s.kind}</Chip> : null}
                </div>
                {s.note ? (
                  <p className="prose" style={{ margin: 0 }}>
                    {s.note}
                  </p>
                ) : null}
                {Object.keys(s.values).length > 0 ? (
                  <Fields>
                    {Object.entries(s.values).map(([k, v]) => (
                      <Field key={k} label={k}>
                        <code>{v}</code>
                      </Field>
                    ))}
                  </Fields>
                ) : null}
              </article>
            ))}
          </div>
        )}
      </Section>

      <Section title="Reward compilation" eyebrow="from bounds to a root">
        {r.rewardSummary ? (
          <Fields>
            <Field label="Reward root">
              <Hash value={r.rewardSummary.rewardRootHex} chars={64} />
            </Field>
            <Field label="Budget">{formatBaseUnits(r.rewardSummary.budgetBaseUnits)} base units</Field>
            <Field label="Allocated to leaves">
              {formatBaseUnits(r.rewardSummary.totalLeafBaseUnits)} base units across{" "}
              {r.rewardSummary.leafCount ?? "?"} leaves
            </Field>
            <Field label="Recoverable">
              {formatBaseUnits(r.rewardSummary.recoverableBaseUnits)} base units
            </Field>
            <Field label="Eligible cohorts">
              {r.rewardSummary.nEligibleCohorts ?? <Absent why="not published by this artifact" />}
            </Field>
            <Field label="Scaled to budget">
              {r.rewardSummary.scaledToBudget === null
                ? "—"
                : r.rewardSummary.scaledToBudget
                  ? "yes — the curve's total exceeded the frozen budget and was scaled down"
                  : "no"}
            </Field>
          </Fields>
        ) : (
          <Absent why="this artifact publishes no reward summary" />
        )}
      </Section>

      <Section title="Provenance" eyebrow="what produced this artifact">
        <Fields>
          <Field label="Engine">
            {r.engineName ?? "—"} {r.engineVersion ?? ""}
          </Field>
          <Field label="Analysis container">
            <Hash value={r.analysisContainerDigest} chars={24} />
          </Field>
          <Field label="Spec version">
            <code>{r.specVersion ?? "—"}</code>
          </Field>
          {snapshot.provenance ? (
            <>
              <Field label="Source commit">
                <Hash value={snapshot.provenance.sourceCommit} chars={20} />
              </Field>
              <Field label="Recorded note">{snapshot.provenance.note ?? "—"}</Field>
            </>
          ) : null}
        </Fields>
      </Section>
    </div>
  );
}
