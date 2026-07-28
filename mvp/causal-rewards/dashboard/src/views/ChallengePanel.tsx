/**
 * Challenge view — bonded objections and what they did to finality.
 *
 * An empty challenge list is the normal state and is written as such. It is not styled as
 * "all clear": no challenge having been filed is not evidence that a result is correct, and
 * the page says so rather than letting a green void imply it.
 */
import { DataTable } from "../components/DataTable";
import { Chip, Field, Fields, Hash, Note, Section, Vacant } from "../components/primitives";
import { formatBaseUnits } from "../protocol/rewardPolicy";
import type { ExperimentSnapshot } from "../protocol/sources/types";
import type { ChallengeResolution } from "../protocol/types";

const RESOLUTION_LABEL: Record<ChallengeResolution, string> = {
  unset: "open — finality paused",
  upheld: "upheld",
  dismissed: "dismissed",
  refunded: "bond refunded",
  unknown: "unrecognised resolution code",
};

const RESOLUTION_TONE: Record<ChallengeResolution, "wax" | "develop" | "null" | "latent"> = {
  unset: "wax",
  upheld: "develop",
  dismissed: "null",
  refunded: "latent",
  unknown: "latent",
};

export function ChallengePanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const challenges = snapshot.challenges;
  const open = snapshot.experiment.openChallenges;
  const bondRequired = snapshot.experiment.manifest?.authorities.challengeBondBaseUnits ?? null;

  return (
    <div className="panel stack-lg">
      <Note>
        <strong>A challenge pauses finality.</strong> Anyone can post a bond against a submitted
        evaluation. While any challenge is open the distribution cannot be finalised and no
        reward can be claimed. The bond exists to price frivolous objections, not to gate who is
        allowed to object.
        {bondRequired ? (
          <>
            {" "}
            The frozen bond for this experiment is{" "}
            <strong>{formatBaseUnits(bondRequired)}</strong> base units.
          </>
        ) : null}
      </Note>

      {open !== null ? (
        <div className="row">
          <Chip tone={open > 0 ? "wax" : "latent"}>
            {open > 0 ? `${open} open — finality paused` : "no open challenges"}
          </Chip>
          {snapshot.experiment.evaluationValid !== null ? (
            <Chip tone={snapshot.experiment.evaluationValid ? "develop" : "null"}>
              evaluation marked {snapshot.experiment.evaluationValid ? "valid" : "invalid"}
            </Chip>
          ) : null}
        </div>
      ) : null}

      {challenges.length === 0 ? (
        <Vacant title="No challenge records in this source">
          {snapshot.source.kind === "bundle"
            ? "Challenges are on-chain accounts, so an audit bundle never carries them. Connect a devnet RPC source to read the Challenge accounts for this experiment."
            : "No challenge has been filed against this evaluation. That is not evidence the result is correct — it only means nobody has posted a bond against it."}
        </Vacant>
      ) : (
        <Section title={`${challenges.length} challenge record${challenges.length === 1 ? "" : "s"}`}>
          <DataTable
            source="Challenge accounts"
            columns={[
              {
                key: "challenger",
                header: "challenger",
                render: (c) => <Hash value={c.challenger} chars={16} />,
              },
              {
                key: "bond_amount_base_units",
                header: "bond",
                numeric: true,
                render: (c) => formatBaseUnits(c.bondAmountBaseUnits),
              },
              { key: "reason_code", header: "reason code", numeric: true, render: (c) => c.reasonCode },
              {
                key: "resolution",
                header: "resolution",
                render: (c) => (
                  <Chip tone={RESOLUTION_TONE[c.resolution]}>
                    {RESOLUTION_LABEL[c.resolution]}
                  </Chip>
                ),
              },
              {
                key: "bond_vault",
                header: "bond vault",
                render: (c) => <Hash value={c.bondVault} chars={12} />,
              },
            ]}
            rows={challenges}
            rowKey={(c, i) => `${c.challenger}-${i}`}
            emptyMessage="No challenge records."
          />
          <Fields>
            <Field label="Total bonded">
              {formatBaseUnits(
                challenges
                  .reduce(
                    (sum, c) =>
                      /^\d+$/.test(c.bondAmountBaseUnits)
                        ? sum + BigInt(c.bondAmountBaseUnits)
                        : sum,
                    0n,
                  )
                  .toString(),
              )}{" "}
              base units{" "}
              <span style={{ color: "var(--ink-faint)" }}>(summed from the rows above)</span>
            </Field>
          </Fields>
        </Section>
      )}
    </div>
  );
}
