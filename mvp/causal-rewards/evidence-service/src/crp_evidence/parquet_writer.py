"""Byte-stable Parquet writing.

Two-level determinism (read this before changing any writer setting)
--------------------------------------------------------------------
**Level 1 — logical (unconditional).** Every table also gets a
``canonical_content_hash`` = SHA-256 over ``CJSON`` of the ordered column names and the ordered
rows, produced by the one ratified encoder. This hash depends on nothing but the data and is
identical on any machine, any Python, any pyarrow. It is what ``roots.json`` /
``manifest.json`` commit to, and it is what an independent verifier should compare. Parquet
bytes are a transport, not the commitment.

**Level 2 — physical (within the pinned container).** With the writer settings pinned below,
two fresh processes produce BYTE-IDENTICAL Parquet files, so the bundle hash is stable too.
This holds within one pinned environment; pyarrow embeds its own version in the file's
``created_by`` field, so a different pyarrow build changes the bytes while leaving level 1
untouched. That is exactly why level 1 exists.

Pinned writer settings and why each one is load-bearing
-------------------------------------------------------
``version="2.6"``            fixed format version; the default tracks the library.
``compression="zstd"``,      zstd is deterministic for a fixed level; the level MUST be
``compression_level=3``      pinned because the default has changed across releases.
``use_dictionary=False``     dictionary encoding makes page bytes depend on insertion order
                             of distinct values; disabling it removes that coupling.
``write_statistics=False``   min/max/null statistics are redundant here and are one more
                             encoder-version-sensitive byte region.
``data_page_size``,          fixed page/row-group/batch sizes, so file layout depends only on
``row_group_size``,          the data, never on memory pressure or chunking of the input.
``write_batch_size``
``data_page_version="2.0"``  pinned page format.
``store_schema=True``        embeds the Arrow schema so a reader recovers exact types.

Additionally: **all columns are UTF-8 strings.** No integers, no floats, no timestamps, no
booleans, no categoricals, no index column. Numeric quantities travel as canonical
integer-scaled decimal STRINGS, exactly as in the hashed artifacts (serialization.md §2). This
kills every remaining nondeterminism class at once — integer width, float formatting, locale,
timezone, and the "parquet embedded a write timestamp" failure mode (there is no timestamp
column and no wall-clock is ever read on this path).

**Row order is never the caller's insertion order.** Callers pass rows already in the
canonical leaf-sort order of the corresponding Merkle tree; ``Table`` records that order's
name in ``sort_order`` and it is published in the manifest.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from . import _ref
from .errors import EvidenceRejected, RejectionCode

__all__ = ["PARQUET_WRITER_SETTINGS", "Table", "TableDigest", "write_table", "table_bytes"]

#: Pinned, published in provenance.json. Changing any value here changes every bundle's
#: physical bytes and MUST come with a bundle_layout_version bump.
PARQUET_WRITER_SETTINGS: dict[str, Any] = {
    "version": "2.6",
    "compression": "zstd",
    "compression_level": 3,
    "use_dictionary": False,
    "write_statistics": False,
    "data_page_size": 1048576,
    "row_group_size": 1048576,
    "write_batch_size": 1024,
    "data_page_version": "2.0",
    "store_schema": True,
}


@dataclass(frozen=True)
class Table:
    """An all-string, order-pinned logical table."""

    name: str
    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]
    sort_order: str

    @staticmethod
    def from_records(
        name: str,
        columns: Sequence[str],
        records: Sequence[Mapping[str, Any]],
        sort_order: str,
    ) -> "Table":
        """Build from dict records. Missing keys are a hard error, never a silent null.

        Every value is coerced with ``str()`` and must already be in canonical form — this is
        a projection step, not a formatting step. A ``float`` value is rejected outright: a
        float reaching a bundle table means someone skipped the integer-scaling boundary.
        """
        cols = tuple(columns)
        rows: list[tuple[str, ...]] = []
        for i, rec in enumerate(records):
            row: list[str] = []
            for c in cols:
                if c not in rec:
                    raise EvidenceRejected(
                        RejectionCode.SCHEMA_INVALID,
                        "table %r row %d is missing column %r" % (name, i, c),
                    )
                v = rec[c]
                if isinstance(v, float):
                    raise EvidenceRejected(
                        RejectionCode.SCHEMA_INVALID,
                        "table %r column %r carries a float (%r); bundle tables are all-string "
                        "with integer-scaled decimals (serialization.md §2)" % (name, c, v),
                    )
                if v is None:
                    raise EvidenceRejected(
                        RejectionCode.SCHEMA_INVALID,
                        "table %r column %r is null in row %d; bundle tables have no nulls "
                        "(use an explicit sentinel string so absence is committed)" % (name, c, i),
                    )
                row.append(str(v))
            rows.append(tuple(row))
        return Table(name=name, columns=cols, rows=tuple(rows), sort_order=sort_order)

    def canonical_object(self) -> dict[str, Any]:
        """The CJSON-hashable logical view (level-1 determinism)."""
        return {
            "columns": list(self.columns),
            "name": self.name,
            "rows": [list(r) for r in self.rows],
            "sort_order": self.sort_order,
        }

    def canonical_content_hash(self) -> str:
        return _ref.sha256_hex(_ref.canonical_json_bytes(self.canonical_object()))

    def to_arrow(self) -> pa.Table:
        arrays = [
            pa.array([r[i] for r in self.rows], type=pa.string())
            for i in range(len(self.columns))
        ]
        return pa.Table.from_arrays(arrays, names=list(self.columns))


@dataclass(frozen=True)
class TableDigest:
    """What the bundle manifest records for one table file."""

    name: str
    path: str
    row_count: int
    sha256_hex: str
    canonical_content_hash: str
    sort_order: str
    columns: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_content_hash": self.canonical_content_hash,
            "columns": list(self.columns),
            "path": self.path,
            "row_count": str(self.row_count),
            "sha256": self.sha256_hex,
            "sort_order": self.sort_order,
        }


def table_bytes(table: Table) -> bytes:
    """Serialize a table to Parquet bytes with the pinned settings (no filesystem)."""
    buf = io.BytesIO()
    pq.write_table(table.to_arrow(), buf, **PARQUET_WRITER_SETTINGS)
    return buf.getvalue()


def write_table(table: Table, path: Path, *, rel_path: str | None = None) -> TableDigest:
    """Write a table to ``path`` and return its digest record."""
    data = table_bytes(table)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return TableDigest(
        name=table.name,
        path=rel_path if rel_path is not None else path.name,
        row_count=len(table.rows),
        sha256_hex=_ref.sha256_hex(data),
        canonical_content_hash=table.canonical_content_hash(),
        sort_order=table.sort_order,
        columns=table.columns,
    )
