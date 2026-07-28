/**
 * The small vocabulary every view is built from.
 *
 * Two rules encoded here rather than left to each view:
 *  - `Chip` has no "success"/"error" tone. A null result gets `null` (neutral slate), never
 *    `danger` — invariant 8: a zero payout is a valid outcome, not a failure.
 *  - `Hash` always renders the full value in the DOM (truncation is visual only), so a
 *    screen reader, a copy, or a text search gets the whole committed digest.
 */
import { useState, type ReactNode } from "react";

export type Tone = "wax" | "develop" | "null" | "latent" | "danger";

export function Chip({
  tone = "latent",
  children,
}: {
  tone?: Tone;
  children: ReactNode;
}) {
  return (
    <span className="chip" data-tone={tone}>
      {children}
    </span>
  );
}

export function Eyebrow({ children }: { children: ReactNode }) {
  return <p className="eyebrow">{children}</p>;
}

export function Note({
  tone,
  children,
}: {
  tone?: "caveat" | "null" | "danger";
  children: ReactNode;
}) {
  return (
    <div className="note" data-tone={tone} role={tone === "danger" ? "alert" : undefined}>
      {children}
    </div>
  );
}

/** A monospace commitment. Truncated on screen, complete in the DOM, one click to copy. */
export function Hash({ value, chars = 12 }: { value: string | null; chars?: number }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="mono">—</span>;
  const short = value.length > chars * 2 + 1 ? `${value.slice(0, chars)}…${value.slice(-4)}` : value;
  return (
    <button
      type="button"
      className="mono"
      title={`${value} (click to copy)`}
      aria-label={`Copy ${value}`}
      style={{
        background: "none",
        border: 0,
        padding: 0,
        font: "inherit",
        cursor: "pointer",
        color: "inherit",
      }}
      onClick={() => {
        void navigator.clipboard?.writeText(value);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1400);
      }}
    >
      <span aria-hidden="true">{copied ? "copied" : short}</span>
      <span className="visually-hidden">{value}</span>
    </button>
  );
}

export function Fields({ children }: { children: ReactNode }) {
  return <dl className="fields">{children}</dl>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </>
  );
}

/** A value the source did not carry. Says so, rather than showing a plausible blank. */
export function Absent({ why }: { why: string }) {
  return (
    <span style={{ color: "var(--ink-faint)" }} title={why}>
      not in this source
    </span>
  );
}

export function Section({
  title,
  eyebrow,
  children,
}: {
  title: string;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <section className="section">
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h2>{title}</h2>
      <div className="stack">{children}</div>
    </section>
  );
}

/**
 * An empty region that is empty *because the protocol has nothing there yet* — a distinct
 * thing from a failure. Always names what would fill it and when.
 */
export function Vacant({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="card stack">
      <h3 style={{ fontSize: "var(--step-0)", fontWeight: 600 }}>{title}</h3>
      <p className="prose" style={{ margin: 0 }}>
        {children}
      </p>
    </div>
  );
}
