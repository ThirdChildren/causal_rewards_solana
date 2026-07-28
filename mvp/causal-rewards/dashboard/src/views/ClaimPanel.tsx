/**
 * Claim view — the distribution root and who can claim what.
 *
 * Recipients are 32-byte pubkeys, which the protocol commits and this page shows. It shows
 * nothing else about them: no cohort membership is joined onto a recipient here, because
 * that is a device-level fact and invariant 5 keeps device-level facts out of a public view.
 *
 * A distribution with zero leaves renders as a distribution, not as an empty state.
 */
import { DataTable } from "../components/DataTable";
import { Absent, Chip, Field, Fields, Hash, Note, Section, Vacant } from "../components/primitives";
import { formatBaseUnits, shareOf } from "../protocol/rewardPolicy";
import type { ExperimentSnapshot } from "../protocol/sources/types";

export function ClaimPanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const d = snapshot.distribution;
  const summary = snapshot.result.rewardSummary;
  const rootsAgree =
    d.rewardRootHex && summary?.rewardRootHex ? d.rewardRootHex === summary.rewardRootHex : null;

  if (!d.present) {
    return (
      <div className="panel">
        <Vacant title="No distribution yet">
          A distribution appears once <code>finalize_distribution</code> anchors the reward root,
          which cannot happen while a challenge is open. Until then nothing is claimable.
        </Vacant>
      </div>
    );
  }

  const zeroDistribution = d.leaves.length === 0 || d.leafTotalBaseUnits === "0";

  return (
    <div className="panel stack-lg">
      {zeroDistribution ? (
        <Section title="This distribution pays nothing" eyebrow="finalised, and empty on purpose">
          <div className="row">
            <Chip tone="null">0 claimable leaves</Chip>
          </div>
          <p className="prose">
            The reward root was compiled from the frozen rules and came out empty: no cohort
            cleared its conservative bound, or too few cohorts met the frozen minimum-sample
            rule. There is nothing to claim, the budget is untouched, and this page is showing
            you the actual finalised state rather than an error.
          </p>
        </Section>
      ) : null}

      <Section title="Distribution" eyebrow="what settlement is bound to">
        <Fields>
          <Field label="Reward root">
            <Hash value={d.rewardRootHex} chars={64} />
          </Field>
          <Field label="Agrees with the result artifact">
            {rootsAgree === null ? (
              <Absent why="one of the two roots is not published by this source" />
            ) : rootsAgree ? (
              <Chip tone="develop">yes — same root in analysis.json and settlement</Chip>
            ) : (
              <Chip tone="danger">
                no — the analysis and the distribution name different roots
              </Chip>
            )}
          </Field>
          <Field label="Total allocated on-chain">
            {d.totalAllocatedBaseUnits ? (
              `${formatBaseUnits(d.totalAllocatedBaseUnits)} base units`
            ) : (
              <Absent why="the Distribution account is not readable from this source" />
            )}
          </Field>
          <Field label="Total across published leaves">
            {formatBaseUnits(d.leafTotalBaseUnits)} base units{" "}
            <span style={{ color: "var(--ink-faint)" }}>
              (summed from the {d.leaves.length} leaves below)
            </span>
          </Field>
          <Field label="Unallocated">
            {d.unallocatedBaseUnits ? (
              `${formatBaseUnits(d.unallocatedBaseUnits)} base units`
            ) : summary?.recoverableBaseUnits ? (
              `${formatBaseUnits(summary.recoverableBaseUnits)} base units (recoverable, per the frozen policy)`
            ) : (
              <Absent why="not published by this source" />
            )}
          </Field>
          <Field label="Claim window ends">
            {d.claimWindowEnd ? (
              new Date(Number(d.claimWindowEnd) * 1000).toISOString().replace(".000Z", "Z")
            ) : (
              <Absent why="on-chain claim state is not part of an audit bundle" />
            )}
          </Field>
        </Fields>
      </Section>

      <Section title="Reward leaves" eyebrow="one leaf per recipient">
        <p className="prose">
          These are the leaves the reward root commits to. Claiming proves membership against
          that root; each leaf is single-use. Whether a leaf has already been claimed is an
          on-chain fact, so a bundle-only read shows it as unknown rather than guessing.
        </p>
        <DataTable
          source="rewards.parquet"
          caption={`${d.leaves.length} reward leaf/leaves.`}
          columns={[
            { key: "leaf_index", header: "#", numeric: true, render: (l) => l.leafIndex },
            {
              key: "recipient_hex",
              header: "recipient",
              render: (l) => <Hash value={l.recipientHex} chars={16} />,
            },
            {
              key: "amount_base_units",
              header: "amount (base units)",
              numeric: true,
              render: (l) => formatBaseUnits(l.amountBaseUnits),
            },
            {
              key: "share",
              header: "share",
              numeric: true,
              render: (l) => {
                const s = shareOf(l.amountBaseUnits, d.leafTotalBaseUnits);
                return s === null ? "—" : `${(s * 100).toFixed(2)}%`;
              },
            },
            {
              key: "leaf_hash_hex",
              header: "leaf hash",
              render: (l) => <Hash value={l.leafHashHex} chars={10} />,
            },
            {
              key: "claimed",
              header: "claimed",
              render: (l) =>
                l.claimed === null ? (
                  <span style={{ color: "var(--ink-faint)" }}>unknown from this source</span>
                ) : l.claimed ? (
                  "yes"
                ) : (
                  "not yet"
                ),
            },
          ]}
          rows={d.leaves}
          rowKey={(l) => `${l.leafIndex}-${l.leafHashHex}`}
          isZero={(l) => l.amountBaseUnits === "0"}
          emptyMessage="The reward root commits to no leaves. Nothing is claimable, and nothing was spent."
        />
      </Section>

      <Note>
        <strong>Recipients are pubkeys and nothing else.</strong> This dashboard does not join a
        recipient to a cohort, a location, or a device. Settlement is the only place a device
        signer appears, and it appears as a key.
      </Note>
    </div>
  );
}
