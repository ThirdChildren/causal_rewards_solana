"""Optional artifact export (Parquet + JSON).

IMPORTANT: Parquet is convenience output for downstream tooling and is NOT the source of the
determinism guarantee — the content hash is computed over ``canonical.py`` bytes, never over
parquet. We still write parquet with fixed column order and no index so it is stable enough
for humans / the causal engine to consume.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from depin_sim.run import RunResult


def _write_parquet(table: dict, path: Path) -> None:
    df = pd.DataFrame(table)
    df = df.reindex(sorted(df.columns), axis=1)  # fixed column order
    df.to_parquet(path, index=False)


def write_bundle(result: RunResult, out_dir: str | Path) -> dict[str, str]:
    """Write the run artifact and tables to ``out_dir``. Returns a map of logical name -> path."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    content = result.artifact["content"]

    paths: dict[str, str] = {}

    artifact_path = out / "run_artifact.json"
    with open(artifact_path, "w", encoding="utf-8") as fh:
        json.dump(result.artifact, fh, sort_keys=True, indent=2, default=_json_default)
    paths["artifact"] = str(artifact_path)

    hash_path = out / "content_hash.txt"
    hash_path.write_text(result.content_hash + "\n", encoding="utf-8")
    paths["content_hash"] = str(hash_path)

    for name in ("sensors", "cells", "cohort_blocks"):
        p = out / f"{name}.parquet"
        _write_parquet(content[name], p)
        paths[name] = str(p)

    return paths


def _json_default(o):
    import numpy as np

    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(f"not JSON serializable: {type(o)!r}")
