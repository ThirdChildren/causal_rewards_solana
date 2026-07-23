"""``provenance.json`` — how this bundle was produced.

Contents are per CLAUDE.md: source commit, container digest, package versions, execution
timestamp.

The determinism problem with provenance
---------------------------------------
``execution_timestamp`` is, by construction, wall-clock — and invariant 2 forbids wall-clock in
any artifact-producing path. Both are satisfied by making the timestamp an **explicit caller
input**, never a ``time.time()`` read inside this package, and by **excluding provenance.json
from the bundle content hash**:

* ``bundle_content_hash`` covers the DATA files (manifest, tables, roots, analysis) — it is a
  pure function of the inputs and is what two independent runs must agree on.
* ``provenance.json`` is metadata ABOUT the run and is hashed separately as
  ``provenance_hash``; it legitimately differs between two runs of the same inputs.

So: same inputs on two machines ⇒ identical ``bundle_content_hash``, differing
``provenance_hash``. A verifier compares the former and reads the latter. Nothing in this
module ever calls the clock; ``BuildContext.execution_timestamp`` must be supplied (the CLI
takes ``--execution-timestamp``, and ``SOURCE_DATE_EPOCH`` is honored for reproducible builds).
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from . import _ref

__all__ = ["BuildContext", "provenance_object", "package_versions", "detect_source_commit"]

#: Packages whose exact version can change bundle BYTES (level-2 determinism). Pinned in
#: requirements.txt; recorded here so a byte difference is always explainable.
_TRACKED_PACKAGES = ("pyarrow", "cryptography")


def package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in _TRACKED_PACKAGES:
        try:
            from importlib.metadata import version as _version

            versions[name] = _version(name)
        except Exception:
            versions[name] = "absent"
    return versions


def detect_source_commit(repo_dir: Path | None = None) -> str:
    """Best-effort ``git rev-parse HEAD``; ``"unknown"`` when git/repo is unavailable.

    Callers that need a guaranteed value pass ``source_commit`` explicitly — the bundle must
    be buildable inside a container that has no ``.git`` directory.
    """
    cwd = str(repo_dir) if repo_dir is not None else None
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        commit = out.stdout.strip()
        return commit if commit else "unknown"
    except Exception:  # pragma: no cover
        return "unknown"


@dataclass(frozen=True)
class BuildContext:
    """Everything about the RUN (as opposed to the data). All values are caller-supplied.

    ``execution_timestamp`` is a canonical unsigned integer STRING of unix seconds. It is
    never read from the clock inside this package. If omitted, ``SOURCE_DATE_EPOCH`` is used,
    else the sentinel ``"0"`` — an unset timestamp is visible rather than fabricated.
    """

    source_commit: str
    container_digest: str
    execution_timestamp: str
    builder: str = "crp-evidence"
    notes: Mapping[str, str] = field(default_factory=dict)

    @staticmethod
    def from_env(
        *,
        source_commit: str | None = None,
        container_digest: str | None = None,
        execution_timestamp: str | None = None,
        repo_dir: Path | None = None,
    ) -> "BuildContext":
        ts = execution_timestamp or os.environ.get("SOURCE_DATE_EPOCH") or "0"
        return BuildContext(
            source_commit=source_commit or detect_source_commit(repo_dir),
            container_digest=container_digest
            or os.environ.get("CRP_CONTAINER_DIGEST", "unpinned"),
            execution_timestamp=str(ts),
        )


def provenance_object(
    ctx: BuildContext,
    *,
    bundle_layout_version: str,
    spec_version: str,
    parquet_writer_settings: Mapping[str, Any],
    ingest_flags: Mapping[str, Any],
    reference_fingerprint: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build the ``provenance.json`` object (CJSON-serializable: strings, lists, dicts only)."""
    return {
        "builder": ctx.builder,
        "bundle_layout_version": bundle_layout_version,
        "container_digest": ctx.container_digest,
        "determinism": {
            "level1_logical": (
                "canonical_content_hash per table = SHA-256(CJSON(logical rows)); "
                "environment-independent, this is the comparison of record"
            ),
            "level2_physical": (
                "parquet file bytes are byte-identical within the pinned container "
                "(pyarrow embeds its own version in created_by)"
            ),
            "provenance_excluded_from_bundle_content_hash": "true",
        },
        "execution_timestamp": ctx.execution_timestamp,
        "ingest_flags": {k: str(v) for k, v in sorted(ingest_flags.items())},
        "notes": {k: str(v) for k, v in sorted(ctx.notes.items())},
        "package_versions": {k: str(v) for k, v in sorted(package_versions().items())},
        "parquet_writer_settings": {
            k: str(v) for k, v in sorted(parquet_writer_settings.items())
        },
        "platform": {
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
            "system": platform.system(),
        },
        "reference_implementation": {
            "path": "verifier-cli/reference",
            "module_sha256": dict(
                sorted((reference_fingerprint or _ref.module_fingerprint()).items())
            ),
        },
        "source_commit": ctx.source_commit,
        "spec_version": spec_version,
        "sys_version": sys.version.split()[0],
    }
