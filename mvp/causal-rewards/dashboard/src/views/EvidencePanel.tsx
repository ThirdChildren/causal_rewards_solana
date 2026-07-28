/**
 * Evidence view — the anchored epochs, and nothing behind them.
 *
 * This is the page where invariant 5 is most at risk, so it is enforced rather than assumed:
 * observations exist only as a Merkle root and a count. There is no drill-down to a reading,
 * a device, or a location, because those never enter a bundle or a Solana account in the
 * first place. If an epoch table ever grows a column that looks device-level or
 * location-precise, `DataTable` refuses to render it.
 */
import { DataTable } from "../components/DataTable";
import { Absent, Field, Fields, Hash, Note, Section, Vacant } from "../components/primitives";
import type { ExperimentSnapshot } from "../protocol/sources/types";
import type { EvidenceEpochView } from "../protocol/types";

function instant(seconds: string | null): string {
  if (!seconds || !/^\d+$/.test(seconds)) return "—";
  const d = new Date(Number(seconds) * 1000);
  return Number.isNaN(d.getTime()) ? seconds : d.toISOString().replace(".000Z", "Z");
}

function EpochCard({ epoch }: { epoch: EvidenceEpochView }) {
  const accepted = epoch.batches.reduce(
    (n, b) => n + (b.acceptedCount && /^\d+$/.test(b.acceptedCount) ? Number(b.acceptedCount) : 0),
    0,
  );
  const rejected = epoch.batches.reduce(
    (n, b) => n + (b.rejectedCount && /^\d+$/.test(b.rejectedCount) ? Number(b.rejectedCount) : 0),
    0,
  );

  return (
    <section className="section">
      <p className="eyebrow">epoch {String(epoch.epochIndex).padStart(6, "0")}</p>
      <h2>
        <Hash value={epoch.rootHex} chars={24} />
      </h2>
      <div className="stack">
        <Fields>
          <Field label="Epoch root">
            <Hash value={epoch.rootHex} chars={64} />
          </Field>
          <Field label="Reproduced from">
            {epoch.file ? (
              <>
                <code>{epoch.file}</code> — {epoch.leafCount ?? "?"} leaves
              </>
            ) : (
              <Absent why="on-chain accounts carry the root, not the leaf table" />
            )}
          </Field>
          {epoch.timeStart || epoch.timeEnd ? (
            <Field label="Time range">
              {instant(epoch.timeStart)} → {instant(epoch.timeEnd)}
            </Field>
          ) : null}
          {epoch.signerSetRootHex ? (
            <Field label="Signer-set commitment">
              <Hash value={epoch.signerSetRootHex} chars={32} />
            </Field>
          ) : null}
          {epoch.observationsRootHex ? (
            <Field label="Observations commitment">
              <Hash value={epoch.observationsRootHex} chars={32} />
            </Field>
          ) : null}
          {epoch.producer ? (
            <Field label="Posted by">
              <Hash value={epoch.producer} chars={20} />
            </Field>
          ) : null}
          {epoch.batches.length > 0 ? (
            <Field label="Aggregate">
              {accepted} accepted, {rejected} rejected across {epoch.batches.length} signed batches
            </Field>
          ) : null}
        </Fields>

        <DataTable
          source={epoch.file ?? `evidence epoch ${epoch.epochIndex}`}
          caption="Signed batch headers, in the leaf-hash order the epoch root is built from. Each row commits to a set of observations; the observations themselves are never published."
          columns={[
            { key: "cohort_id", header: "cohort", render: (b) => <code>{b.cohortId ?? "—"}</code> },
            {
              key: "time_start",
              header: "from",
              render: (b) => instant(b.timeStart),
            },
            { key: "time_end", header: "to", render: (b) => instant(b.timeEnd) },
            {
              key: "signer_set_root_hex",
              header: "signer set",
              render: (b) => (
                <>
                  <Hash value={b.signerSetRootHex} chars={8} />{" "}
                  <span style={{ color: "var(--ink-faint)" }}>×{b.signerCount ?? "?"}</span>
                </>
              ),
            },
            {
              key: "observations_root_hex",
              header: "observations",
              render: (b) => (
                <>
                  <Hash value={b.observationsRootHex} chars={8} />{" "}
                  <span style={{ color: "var(--ink-faint)" }}>×{b.observationLeafCount ?? "?"}</span>
                </>
              ),
            },
            { key: "accepted_count", header: "accepted", numeric: true, render: (b) => b.acceptedCount ?? "—" },
            { key: "rejected_count", header: "rejected", numeric: true, render: (b) => b.rejectedCount ?? "—" },
            {
              key: "leaf_hash_hex",
              header: "leaf hash",
              render: (b) => <Hash value={b.leafHashHex} chars={8} />,
            },
          ]}
          rows={epoch.batches}
          rowKey={(b) => b.leafHashHex}
          emptyMessage="This epoch publishes leaf hashes only. The root is still fully reproducible from them."
        />
      </div>
    </section>
  );
}

export function EvidencePanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const epochs = snapshot.evidence;

  return (
    <div className="panel stack-lg">
      <Note>
        <strong>Evidence is anchored, not published.</strong> An epoch commits to a set of signed
        observation batches through a Merkle root. Raw telemetry, device identities and exact
        coordinates stay off-chain and out of the audit bundle by design — what you can check is
        that the anchored evidence is the same evidence the analysis consumed.
      </Note>

      {epochs.length === 0 ? (
        <Vacant title="No evidence epochs yet">
          Epochs appear here once <code>post_evidence_epoch</code> anchors the first batch root.
          An experiment in Draft or Frozen has none, and that is the expected state.
        </Vacant>
      ) : (
        <>
          <Section title={`${epochs.length} anchored epoch${epochs.length === 1 ? "" : "s"}`} eyebrow="append-only">
            <p className="prose">
              Epoch indices advance strictly. The verifier rebuilds each root from the published
              leaf hashes and rejects a duplicated or out-of-order leaf, so a replayed epoch
              cannot pass.
            </p>
          </Section>
          {epochs.map((e) => (
            <EpochCard key={`${e.epochIndex}-${e.rootHex}`} epoch={e} />
          ))}
          {snapshot.result.evidenceEpochRoots.length > 0 ? (
            <Section title="Evidence ↔ result seam" eyebrow="what the analysis actually consumed">
              <p className="prose">
                The result artifact names the epoch roots it was computed over. If these differ
                from the roots above, the analysis consumed different evidence than the bundle
                anchors, and <code>crp-verify</code> rejects the bundle.
              </p>
              <DataTable
                source="analysis.json evidence_epoch_roots"
                columns={[
                  {
                    key: "root",
                    header: "root bound by the analysis",
                    render: (r: string) => <Hash value={r} chars={64} />,
                  },
                ]}
                rows={snapshot.result.evidenceEpochRoots}
                rowKey={(r) => r}
                emptyMessage="The result artifact binds no epoch roots."
              />
            </Section>
          ) : null}
        </>
      )}
    </div>
  );
}
