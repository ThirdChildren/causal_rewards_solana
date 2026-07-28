/**
 * Audit export — and the standing reminder that this button is a convenience, not the source.
 *
 * The availability invariant is a product requirement, not a footnote: if this dashboard is
 * down, verification must be unaffected. So the panel always shows the direct link to the
 * content-addressed bundle and the exact `crp-verify` invocation, whether or not the export
 * button is usable from the current source.
 */
import { useState } from "react";
import {
  buildAuditExport,
  downloadAuditExport,
  EXPORT_META_DIR,
} from "../export/auditExport";
import type { ExperimentSnapshot } from "../protocol/sources/types";
import { Note } from "./primitives";

export function ExportPanel({ snapshot }: { snapshot: ExperimentSnapshot }) {
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const files = snapshot.bundleFiles;
  const canExport = files !== null && files.size > 0;

  function onExport() {
    setError(null);
    setDone(null);
    try {
      const result = buildAuditExport({
        experimentId: snapshot.experiment.experimentId || snapshot.source.id,
        bundleFiles: files!,
        onchainCommitments: snapshot.onchainCommitments,
        bundleUrl: snapshot.bundleUrl,
        bundleLayoutVersion: snapshot.roots?.bundleLayoutVersion ?? null,
      });
      downloadAuditExport(result);
      setDone(`${result.filename} — ${result.paths.length} files`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  const cmd = [
    `unzip crp-audit-bundle_${snapshot.experiment.experimentId || "experiment"}.zip -d bundle/`,
    "pip install -e verifier-cli/",
    `crp-verify bundle/ --onchain bundle/${EXPORT_META_DIR}/onchain-commitments.json`,
  ].join("\n");

  return (
    <div className="export stack">
      <p className="eyebrow">audit export</p>
      <h2 style={{ fontFamily: "var(--font-display)", fontSize: "var(--step-1)" }}>
        Take the evidence with you
      </h2>
      <p className="prose" style={{ margin: 0 }}>
        Download the whole bundle — manifest, assignment, evidence epochs, the result artifact,
        the reward leaf set, and the published roots — as byte-identical copies of the
        content-addressed originals. Then reproduce every root yourself, offline.
      </p>

      <div className="row">
        <button type="button" className="btn" onClick={onExport} disabled={!canExport}>
          Download audit bundle
        </button>
        {snapshot.bundleUrl ? (
          <a className="btn btn--quiet" href={snapshot.bundleUrl}>
            Open the published bundle
          </a>
        ) : null}
      </div>

      {!canExport ? (
        <Note>
          This source reads on-chain accounts, which carry commitments but not the artifacts
          behind them. Fetch the bundle from where the coordinator published it, then verify —
          the on-chain roots shown throughout this dashboard are what you check it against.
        </Note>
      ) : null}

      {done ? (
        <Note tone="caveat">
          <strong>Exported {done}.</strong> Nothing in the archive was re-serialised: the JSON
          and Parquet bytes are the ones the anchored hashes were taken over.
        </Note>
      ) : null}

      {error ? <Note tone="danger">Export refused: {error}</Note> : null}

      <pre className="pre">{cmd}</pre>

      <p className="prose" style={{ margin: 0, fontSize: "var(--step--2)" }}>
        Exit code 0 means every root was reproduced from first principles, with no network
        access and no trust in the coordinator, the evaluator, or this dashboard. It does not
        mean the causal effect is true.
      </p>
    </div>
  );
}
