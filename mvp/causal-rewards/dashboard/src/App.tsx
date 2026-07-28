/**
 * The dashboard shell.
 *
 * Reads exactly one thing — an `ExperimentSnapshot` from a `ProtocolDataSource` — so the same
 * five views render an offline audit bundle and live devnet accounts without branching. The
 * source is chosen once, here; no view knows or cares which it got.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { ExportPanel } from "./components/ExportPanel";
import { Chip, Note } from "./components/primitives";
import { SealBlock } from "./components/SealBlock";
import { BundleDataSource } from "./protocol/sources/bundleSource";
import type {
  ExperimentSnapshot,
  ExperimentSummary,
  ProtocolDataSource,
} from "./protocol/sources/types";
import { sealState } from "./protocol/stateMachine";
import { ChallengePanel } from "./views/ChallengePanel";
import { ClaimPanel } from "./views/ClaimPanel";
import { EvidencePanel } from "./views/EvidencePanel";
import { ExperimentPanel } from "./views/ExperimentPanel";
import { ResultPanel } from "./views/ResultPanel";

const TABS = ["experiment", "evidence", "result", "challenges", "claims"] as const;
export type TabId = (typeof TABS)[number];

const TAB_LABEL: Record<TabId, string> = {
  experiment: "Experiment",
  evidence: "Evidence",
  result: "Result",
  challenges: "Challenges",
  claims: "Claims",
};

function tabFromHash(): TabId {
  const h = window.location.hash.replace(/^#/, "");
  return (TABS as readonly string[]).includes(h) ? (h as TabId) : "experiment";
}

export function App({ source }: { source?: ProtocolDataSource }) {
  const dataSource = useMemo(() => source ?? new BundleDataSource(), [source]);
  const [list, setList] = useState<ExperimentSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<ExperimentSnapshot | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<TabId>(() => tabFromHash());

  useEffect(() => {
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    let live = true;
    dataSource
      .listExperiments()
      .then((xs) => {
        if (!live) return;
        setList(xs);
        setSelected((cur) => cur ?? xs[0]?.experimentId ?? null);
      })
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [dataSource]);

  useEffect(() => {
    if (!selected) return;
    let live = true;
    setSnapshot(null);
    setError(null);
    dataSource
      .loadExperiment(selected)
      .then((s) => live && setSnapshot(s))
      .catch((e: unknown) => live && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      live = false;
    };
  }, [dataSource, selected]);

  const selectTab = useCallback((t: TabId) => {
    setTab(t);
    window.location.hash = t;
  }, []);

  const manifest = snapshot?.experiment.manifest ?? null;
  const seal = snapshot
    ? sealState(snapshot.experiment.status, snapshot.experiment.revealedSeedHex)
    : null;

  return (
    <>
      <header className="topbar">
        <div className="topbar__inner">
          <div className="wordmark">
            Causal Rewards <span>· public audit</span>
          </div>
          <div className="row">
            <span className="cluster-chip">{dataSource.network.cluster}</span>
            {list && list.length > 0 ? (
              <>
                <label className="visually-hidden" htmlFor="experiment-picker">
                  Choose an experiment
                </label>
                <select
                  id="experiment-picker"
                  className="picker"
                  value={selected ?? ""}
                  onChange={(e) => setSelected(e.target.value)}
                >
                  {list.map((x) => (
                    <option key={x.experimentId} value={x.experimentId}>
                      {x.title}
                    </option>
                  ))}
                </select>
              </>
            ) : null}
          </div>
        </div>
      </header>

      <main className="shell">
        {error ? (
          <div style={{ paddingTop: "var(--s6)" }}>
            <Note tone="danger">
              Could not read from this source: {error}. The dashboard is a convenience layer —
              the published bundle and <code>crp-verify</code> do not depend on it being up.
            </Note>
          </div>
        ) : null}

        {!snapshot && !error ? (
          <div style={{ paddingTop: "var(--s7)" }}>
            <p className="eyebrow">loading</p>
            <p className="prose">Reading committed artifacts…</p>
          </div>
        ) : null}

        {snapshot && seal ? (
          <>
            <div className="masthead stack">
              <p className="eyebrow">pre-registered experiment</p>
              <h1>{manifest?.title || snapshot.experiment.experimentId}</h1>
              <div className="masthead__meta">
                <span>{snapshot.experiment.experimentId}</span>
                <span>spec {manifest?.specVersion ?? "—"}</span>
                <span>
                  read from{" "}
                  {snapshot.source.kind === "bundle"
                    ? "a published audit bundle"
                    : "Solana " + snapshot.source.network.cluster}
                </span>
              </div>
            </div>

            <SealBlock
              manifestHashHex={snapshot.experiment.manifestHashHex}
              seedCommitmentHex={manifest?.seedCommitment.commitmentHex ?? null}
              revealedSeedHex={snapshot.experiment.revealedSeedHex}
              seal={seal}
            />

            {snapshot.warnings.length > 0 ? (
              <div className="stack" style={{ marginTop: "var(--s5)" }}>
                {snapshot.warnings.map((w) => (
                  <Note key={w}>{w}</Note>
                ))}
              </div>
            ) : null}

            <nav className="tabs" role="tablist" aria-label="Experiment sections">
              {TABS.map((t) => (
                <button
                  key={t}
                  type="button"
                  role="tab"
                  id={`tab-${t}`}
                  aria-selected={tab === t}
                  aria-controls={`panel-${t}`}
                  onClick={() => selectTab(t)}
                >
                  {TAB_LABEL[t]}
                  <span className="count">{tabCount(t, snapshot)}</span>
                </button>
              ))}
            </nav>

            <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
              {tab === "experiment" ? <ExperimentPanel snapshot={snapshot} /> : null}
              {tab === "evidence" ? <EvidencePanel snapshot={snapshot} /> : null}
              {tab === "result" ? <ResultPanel snapshot={snapshot} /> : null}
              {tab === "challenges" ? <ChallengePanel snapshot={snapshot} /> : null}
              {tab === "claims" ? <ClaimPanel snapshot={snapshot} /> : null}
            </div>

            <div style={{ marginTop: "var(--s7)" }}>
              <ExportPanel snapshot={snapshot} />
            </div>

            <footer className="footer stack">
              <div className="row">
                <Chip tone="wax">{dataSource.network.cluster} only</Chip>
                <Chip tone="latent">no fees · no token · no mainnet</Chip>
              </div>
              <p className="prose" style={{ margin: 0 }}>
                This page displays only values the protocol commits. It is a convenience layer
                over public, content-addressed artifacts: if it disappears, every claim on it
                stays checkable with <code>crp-verify</code> against the published bundle.
              </p>
            </footer>
          </>
        ) : null}
      </main>
    </>
  );
}

function tabCount(tab: TabId, s: ExperimentSnapshot): string {
  switch (tab) {
    case "evidence":
      return s.evidence.length ? String(s.evidence.length) : "";
    case "result":
      return s.result.present ? String(s.result.cohorts.length + s.result.excluded.length) : "";
    case "challenges":
      return s.challenges.length ? String(s.challenges.length) : "";
    case "claims":
      return s.distribution.leaves.length ? String(s.distribution.leaves.length) : "";
    default:
      return s.assignment.length ? String(s.assignment.length) : "";
  }
}
