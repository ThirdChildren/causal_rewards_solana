"""Single-encoder bridge to the ratified reference implementation.

The verifier RE-USES the one canonical encoder in this repository —
``verifier-cli/reference/`` — it does NOT re-implement canonical JSON, the Merkle
construction, the assignment derivation, the evidence trees, or the reward leaf.
Any drift between the verifier and the conformance oracle is therefore impossible
by construction (the reference modules import each other by bare top-level name, so
the reference directory is prepended to ``sys.path`` exactly once, here).

Override the location with ``CRP_REFERENCE_DIR`` (used when the verifier runs from
an installed wheel outside the repo tree, e.g. on an auditor's clean machine).
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
    "module_fingerprint",
]


def _locate_reference_dir() -> Path:
    env = os.environ.get("CRP_REFERENCE_DIR")
    if env:
        p = Path(env).resolve()
        if not (p / "canonical.py").is_file():
            raise RuntimeError("CRP_REFERENCE_DIR=%s does not contain canonical.py" % (p,))
        return p
    # src/crp_verifier/_ref.py -> crp_verifier -> src -> verifier-cli
    verifier_cli = Path(__file__).resolve().parents[2]
    p = verifier_cli / "reference"
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
    """SHA-256 of each reference module's source bytes — records the exact oracle bytes."""
    out: dict[str, str] = {}
    mods: list[ModuleType] = [canonical, merkle, evidence, assignment, reward]
    for m in mods:
        src = Path(m.__file__).resolve()  # type: ignore[arg-type]
        out[src.name] = canonical.sha256_hex(src.read_bytes())
    return out
