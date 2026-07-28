/**
 * The experiment state machine as a rail of stops.
 *
 * Numbering is used here — and only here — because the states genuinely are an ordered
 * sequence the protocol advances through; the number carries information the reader needs.
 * `Challenged` is a loop state, so it is annotated rather than implied to be passed through.
 */
import { STATUS_META, STATUS_ORDER, statusIndex } from "../protocol/stateMachine";
import type { ExperimentStatus, Provenance } from "../protocol/types";

const PROVENANCE_LABEL: Record<Provenance, string> = {
  onchain: "read from the on-chain Experiment account",
  bundle: "inferred from the artifacts this bundle contains",
  derived: "derived from displayed values",
};

export function StatusRail({
  status,
  provenance,
  aborted,
}: {
  status: ExperimentStatus;
  provenance: Provenance;
  aborted?: boolean | null;
}) {
  const current = statusIndex(status);
  return (
    <div>
      <ol className="rail" aria-label="Experiment state">
        {STATUS_ORDER.map((s, i) => {
          const state = i === current ? "current" : i < current ? "reached" : "ahead";
          return (
            <li
              key={s}
              className="rail__stop"
              data-state={state}
              aria-current={state === "current" ? "step" : undefined}
            >
              <span className="n">{String(i + 1).padStart(2, "0")}</span>
              {STATUS_META[s].label}
            </li>
          );
        })}
      </ol>
      <p className="rail__meaning">
        <strong>{STATUS_META[status].label}.</strong> {STATUS_META[status].meaning}{" "}
        <span style={{ color: "var(--ink-faint)" }}>({PROVENANCE_LABEL[provenance]})</span>
        {aborted ? " This experiment was aborted; no distribution is payable." : ""}
      </p>
    </div>
  );
}
