"""Shared fixtures: assemble the golden bundle once and expose tamper helpers.

Every adversarial bundle is DERIVED from the one real assembled bundle so the only
difference from a passing bundle is the specific tamper under test — the first point of
divergence the verifier reports is therefore exactly the injected fault.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pytest

VERIFIER_CLI = Path(__file__).resolve().parents[1]
REPO = VERIFIER_CLI.parent
FIXTURES = VERIFIER_CLI / "fixtures"
REFERENCE = VERIFIER_CLI / "reference"
VECTORS = REPO / "test-vectors"

for p in (str(VERIFIER_CLI / "src"), str(REFERENCE)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_builder():
    spec = importlib.util.spec_from_file_location(
        "build_golden_bundle", FIXTURES / "build_golden_bundle.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


BUILDER = _load_builder()


@pytest.fixture(scope="session")
def golden_bundle(tmp_path_factory: pytest.TempPathFactory) -> Path:
    dest = tmp_path_factory.mktemp("golden") / "golden-happy"
    return BUILDER.build(dest)


# --------------------------------------------------------------------------- tamper helpers


def copy_bundle(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    return dst


def read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def write_canonical(path: Path, obj: Any) -> None:
    import canonical  # from reference on sys.path

    path.write_bytes(canonical.canonical_json_bytes(obj))


def write_parquet_columns(path: Path, columns: dict[str, list[str]]) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.table({k: pa.array(v, type=pa.string()) for k, v in columns.items()})
    pq.write_table(table, path, compression="none", write_statistics=False)


def resync_result_hash(bundle_dir: Path) -> None:
    """Rewrite roots.json.result_artifact_hash to match the current analysis.json bytes.

    Models a *self-consistent* attacker who cooks analysis.json AND updates the anchor, so a
    tamper test isolates the targeted guard (seam / container) instead of tripping the plain
    result-hash comparison first.
    """
    import canonical

    rah = canonical.sha256_hex((bundle_dir / "analysis.json").read_bytes())
    roots = read_json(bundle_dir / "roots.json")
    roots["roots"]["result_artifact_hash"] = rah
    write_canonical(bundle_dir / "roots.json", roots)


def read_parquet_columns(path: Path) -> dict[str, list[str]]:
    import pyarrow.parquet as pq

    t = pq.read_table(path)
    return {name: [str(x) for x in t.column(i).to_pylist()] for i, name in enumerate(t.column_names)}
