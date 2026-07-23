"""Single-encoder bridge to the ratified reference implementation.

THERE IS EXACTLY ONE CANONICAL ENCODER IN THIS REPOSITORY:
``verifier-cli/reference/canonical.py``. This module makes that code importable from the
evidence service **by path** — it does not copy, re-implement, or wrap its byte semantics.
Any drift between the service and the conformance oracle is therefore impossible by
construction rather than by test (the tests still assert it, defensively).

The reference modules import each other by top-level name (``from canonical import ...``),
so the reference directory is prepended to ``sys.path`` once, here.

Override the location with ``CRP_REFERENCE_DIR`` (used when the service is installed
outside the repo tree, e.g. in the analysis container).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import ModuleType

__all__ = [
    "reference_dir",
    "canonical",
    "merkle",
    "evidence",
    "assignment",
    "reward",
    "canonical_json_bytes",
    "sha256",
    "sha256_hex",
]


def _locate_reference_dir() -> Path:
    env = os.environ.get("CRP_REFERENCE_DIR")
    if env:
        p = Path(env).resolve()
        if not (p / "canonical.py").is_file():
            raise RuntimeError(
                "CRP_REFERENCE_DIR=%s does not contain canonical.py" % (p,)
            )
        return p
    # src/crp_evidence/_ref.py -> crp_evidence -> src -> evidence-service -> <repo root>
    repo_root = Path(__file__).resolve().parents[3]
    p = repo_root / "verifier-cli" / "reference"
    if not (p / "canonical.py").is_file():
        raise RuntimeError(
            "cannot locate verifier-cli/reference (looked in %s); set CRP_REFERENCE_DIR" % (p,)
        )
    return p


reference_dir: Path = _locate_reference_dir()

if str(reference_dir) not in sys.path:
    sys.path.insert(0, str(reference_dir))

import canonical as canonical  # noqa: E402  (path set above)
import merkle as merkle  # noqa: E402
import evidence as evidence  # noqa: E402
import assignment as assignment  # noqa: E402
import reward as reward  # noqa: E402

canonical_json_bytes = canonical.canonical_json_bytes
sha256 = canonical.sha256
sha256_hex = canonical.sha256_hex


def module_fingerprint() -> dict[str, str]:
    """SHA-256 of each reference module's source bytes.

    Recorded in ``provenance.json`` so a bundle names the exact oracle bytes it was built
    against. If the reference changes, every bundle built after it is distinguishable.
    """
    out: dict[str, str] = {}
    mods: list[ModuleType] = [canonical, merkle, evidence, assignment, reward]
    for m in mods:
        src = Path(m.__file__).resolve()  # type: ignore[arg-type]
        out[src.name] = canonical.sha256_hex(src.read_bytes())
    return out
