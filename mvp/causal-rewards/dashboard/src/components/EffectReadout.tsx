/**
 * The primary effect, always shown WITH its uncertainty.
 *
 * Two commitments this component makes and the rest of the UI relies on:
 *
 *  1. The point estimate is never displayed alone. The conservative lower bound — the only
 *     quantity that can move money (invariant 3) — is set at the same size beside it, and
 *     the interval bar shows the margin the conservative rule subtracts.
 *  2. A conservative bound of zero is rendered in the neutral `null` tone with a plain-
 *     language line saying the frozen rule pays nothing. It is not an error state, it is not
 *     hidden, and it is not styled as a failure (invariant 8).
 */
import { formatScaled } from "../protocol/rewardPolicy";
import type { PrimaryEffect } from "../protocol/types";

function toNumber(v: string | null): number | null {
  if (!v || !/^-?\d+$/.test(v)) return null;
  return Number(v);
}

export function EffectReadout({
  effect,
  unit,
  improvementDirection,
  conservativeRule,
}: {
  effect: PrimaryEffect;
  unit: string | null;
  improvementDirection: string | null;
  conservativeRule: string;
}) {
  const s = effect.scaleExponent;
  const positive = effect.conservativeS !== "0" && effect.conservativeS !== "";
  const improvement = effect.improvementS ?? effect.effectS;

  const imp = toNumber(improvement);
  const margin = toNumber(effect.marginS);
  const bound = toNumber(effect.conservativeS);

  return (
    <div className="stack">
      <div className="effect">
        <div className="effect__item">
          <span className="label">Point estimate</span>
          <span className="value">{formatScaled(effect.effectS, s)}</span>
          <span className="unit">
            {unit ?? "frozen outcome unit"}
            {improvementDirection === "decrease"
              ? " · lower is better"
              : improvementDirection === "increase"
                ? " · higher is better"
                : ""}
          </span>
        </div>
        <div className="effect__item">
          <span className="label">Standard error</span>
          <span className="value">±{formatScaled(effect.standardErrorS, s)}</span>
          <span className="unit">
            {effect.nClusters ? `cluster-robust, ${effect.nClusters} clusters` : "cluster-robust"}
          </span>
        </div>
        <div className="effect__item" data-tone={positive ? "develop" : "null"}>
          <span className="label">Conservative bound</span>
          <span className="value">{formatScaled(effect.conservativeS, s)}</span>
          <span className="unit">what the reward curve is applied to</span>
        </div>
      </div>

      {imp !== null && margin !== null && bound !== null ? (
        <IntervalBar improvement={imp} margin={margin} bound={bound} scale={s} />
      ) : null}

      <p className="prose" style={{ margin: 0 }}>
        <code>{conservativeRule}</code>
      </p>

      {positive ? null : (
        <div className="note" data-tone="null">
          <strong>The conservative bound is zero, so the frozen rule pays nothing here.</strong>{" "}
          The point estimate above is not evidence of an effect: once the frozen margin is
          subtracted, the lower confidence bound does not clear zero. This is a valid result,
          published exactly as it came out. Unspent budget stays recoverable.
        </div>
      )}
    </div>
  );
}

/** Improvement estimate, its margin, and where the conservative bound lands relative to 0. */
function IntervalBar({
  improvement,
  margin,
  bound,
  scale,
}: {
  improvement: number;
  margin: number;
  bound: number;
  scale: number;
}) {
  const lo = improvement - margin;
  const hi = improvement + margin;
  const span = Math.max(Math.abs(lo), Math.abs(hi), 1) * 1.15;
  const pct = (v: number) => ((v + span) / (2 * span)) * 100;

  return (
    <div className="interval">
      <p className="eyebrow" style={{ margin: 0 }}>
        improvement ± frozen margin
      </p>
      <div className="interval__track">
        <div
          className="interval__band"
          style={{ left: `${pct(lo)}%`, width: `${pct(hi) - pct(lo)}%` }}
        />
        <div className="interval__zero" style={{ left: "50%" }} />
        <div className="interval__point" style={{ left: `${pct(improvement)}%` }} />
        {bound > 0 ? (
          <div className="interval__bound" style={{ left: `${pct(bound)}%` }} />
        ) : null}
      </div>
      <div className="interval__scale">
        <span>{formatScaled(String(Math.round(-span)), scale)}</span>
        <span>0</span>
        <span>{formatScaled(String(Math.round(span)), scale)}</span>
      </div>
      <p style={{ margin: "var(--s2) 0 0", fontSize: "var(--step--2)", color: "var(--ink-soft)" }}>
        The band is the one-sided margin the frozen analysis plan subtracts. The conservative
        bound is where the band's lower edge meets zero — left of zero, the payout is zero.
      </p>
    </div>
  );
}
