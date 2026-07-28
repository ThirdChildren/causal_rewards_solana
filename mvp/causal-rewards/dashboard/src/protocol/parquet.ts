/**
 * Read the bundle's Parquet transport in the browser.
 *
 * The audit bundle stores every column as a *string* (see `verifier-cli/src/crp_verifier/
 * bundle.py`, which normalizes to an all-string logical table). We mirror that exactly:
 * values are surfaced as strings and never coerced to JS numbers, so a u64 amount or a
 * micro-scaled effect can never lose precision on the way to the screen.
 */
import { parquetReadObjects } from "hyparquet";

export interface LogicalTable {
  columns: string[];
  rows: Array<Record<string, string>>;
}

function toStringCell(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (typeof v === "string") return v;
  if (typeof v === "bigint") return v.toString();
  if (v instanceof Uint8Array) return new TextDecoder().decode(v);
  return String(v);
}

/** Parse a Parquet file into the same all-string logical table the verifier reads. */
export async function readLogicalTable(bytes: Uint8Array): Promise<LogicalTable> {
  const buf = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
  const raw = (await parquetReadObjects({ file: buf })) as Array<Record<string, unknown>>;
  const columns: string[] = [];
  for (const r of raw) for (const k of Object.keys(r)) if (!columns.includes(k)) columns.push(k);
  const rows = raw.map((r) => {
    const out: Record<string, string> = {};
    for (const c of columns) out[c] = toStringCell(r[c]);
    return out;
  });
  return { columns, rows };
}
