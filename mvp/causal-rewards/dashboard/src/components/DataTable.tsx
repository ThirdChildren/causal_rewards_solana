/**
 * A tabular renderer for committed rows.
 *
 * It runs every column name through the privacy gate before rendering (invariant 5): if a
 * future bundle grows a `latitude` or `device_serial` column, this throws rather than
 * quietly painting it on a public page. The gate is the same one the audit export uses, so
 * "what you can see" and "what you can download" cannot drift apart.
 */
import type { ReactNode } from "react";
import { assertCohortLevelColumns } from "../protocol/privacy";

export interface Column<T> {
  /** The protocol field name. Checked against the privacy denylist. */
  key: string;
  header: string;
  numeric?: boolean;
  render: (row: T) => ReactNode;
}

export function DataTable<T>({
  source,
  caption,
  columns,
  rows,
  rowKey,
  isZero,
  emptyMessage,
}: {
  /** What this table is, for the privacy error message. */
  source: string;
  caption?: ReactNode;
  columns: Array<Column<T>>;
  rows: readonly T[];
  rowKey: (row: T, i: number) => string;
  /** Marks a row that contributed nothing. Rendered muted, never as an error. */
  isZero?: (row: T) => boolean;
  emptyMessage: string;
}) {
  assertCohortLevelColumns(
    source,
    columns.map((c) => c.key),
  );

  if (rows.length === 0) {
    return <p className="prose">{emptyMessage}</p>;
  }

  return (
    <div className="table-wrap">
      <table className="data">
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col">
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={rowKey(row, i)} data-zero={isZero?.(row) ? "true" : undefined}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? "num" : undefined}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
