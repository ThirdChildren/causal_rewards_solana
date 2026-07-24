"""Read an audit bundle DIRECTORY off disk — the only thing the verifier trusts.

Offline and dependency-light: the sole non-stdlib import is ``pyarrow`` (to read the
Parquet transport). Everything hashed or root-derived flows back through the one
ratified encoder in ``verifier-cli/reference/`` (via :mod:`_ref`). This module does no
verification — it is pure I/O and shape-loading. The recompute lives in :mod:`checks`.

A bundle on disk (``bundle_layout_version`` 1.0.0)::

    manifest.json          frozen manifest, verbatim canonical bytes
    participants.parquet   participant set (participant-leaf order)
    assignment.parquet     cohort -> arm (cohort_id UTF-16 asc)
    evidence/
      epoch-<NNNNNN>.parquet   one table per epoch (leaf_hash asc)
      findings.json
      missingness.json
    analysis.json          causal engine artifact (may be absent = evidence-only)
    rewards.parquet        reward leaf set (may be absent = evidence-only)
    roots.json             every Merkle root + the file index
    provenance.json        source commit, container digest, timestamp (EXCLUDED from hashes)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class BundleError(Exception):
    """Structural problem reading the bundle (a missing/unreadable required file)."""


@dataclass(frozen=True)
class ParquetTable:
    """A logical, all-string table as read back from a Parquet file, in stored row order."""

    columns: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]

    def column(self, name: str) -> list[str]:
        i = self.columns.index(name)
        return [r[i] for r in self.rows]

    def dict_rows(self) -> list[dict[str, str]]:
        return [dict(zip(self.columns, r)) for r in self.rows]


class Bundle:
    """A bundle directory. Lazily reads files; caches raw bytes so hashes are stable."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root = Path(root_dir)
        if not self.root.is_dir():
            raise BundleError("bundle path is not a directory: %s" % self.root)
        self._bytes_cache: dict[str, bytes] = {}

    # -- raw bytes -----------------------------------------------------------------
    def has(self, rel: str) -> bool:
        return (self.root / rel).is_file()

    def raw(self, rel: str) -> bytes:
        if rel not in self._bytes_cache:
            p = self.root / rel
            if not p.is_file():
                raise BundleError("required bundle file is missing: %s" % rel)
            self._bytes_cache[rel] = p.read_bytes()
        return self._bytes_cache[rel]

    # -- json ----------------------------------------------------------------------
    def json(self, rel: str) -> Any:
        try:
            return json.loads(self.raw(rel).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BundleError("bundle file %s is not valid UTF-8 JSON: %s" % (rel, exc)) from exc

    # -- parquet -------------------------------------------------------------------
    def parquet(self, rel: str) -> ParquetTable:
        import pyarrow.parquet as pq  # local import: keeps --help fast, deps obvious

        p = self.root / rel
        if not p.is_file():
            raise BundleError("required bundle table is missing: %s" % rel)
        t = pq.read_table(p)
        cols = tuple(t.column_names)
        pylists = [t.column(i).to_pylist() for i in range(t.num_columns)]
        n = t.num_rows
        rows = tuple(
            tuple("" if pylists[c][r] is None else str(pylists[c][r]) for c in range(len(cols)))
            for r in range(n)
        )
        return ParquetTable(columns=cols, rows=rows)

    # -- convenience accessors for the well-known slots ----------------------------
    @property
    def roots(self) -> Any:
        return self.json("roots.json")

    @property
    def manifest(self) -> Any:
        return self.json("manifest.json")

    def evidence_epoch_files(self) -> list[str]:
        """Epoch parquet paths named in ``roots.json`` (ascending epoch order), authoritative."""
        out: list[str] = []
        for e in self.roots["roots"]["evidence_epochs"]:
            out.append(str(e["file"]))
        return out
