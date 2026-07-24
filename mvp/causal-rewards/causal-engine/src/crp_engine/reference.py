"""Single-encoder bridge to the RATIFIED conformance oracle (``verifier-cli/reference/``).

The causal engine MUST NOT contain a second canonical-JSON encoder, a second Merkle
implementation, or a second reward-leaf byte layout. `specs/serialization.md` is normative and
`verifier-cli/reference/{canonical,merkle,reward,assignment}.py` is the conformance oracle for it.
This module loads those modules *by path* and re-exports them, so every byte the engine hashes is
produced by the same code the verifier CLI runs.

Resolution order for the reference directory:

1. ``$CRP_REFERENCE_DIR`` (used by the pinned container, which copies the reference in),
2. ``<repo-root>/verifier-cli/reference`` relative to this file,
3. ``<sys.prefix>/share/crp/reference`` (installed layout).

If none exist, import fails loudly. A silent fallback to a local re-implementation is exactly the
failure mode this module exists to prevent.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Final

__all__ = [
    "REFERENCE_DIR",
    "canonical_json_bytes",
    "sha256",
    "sha256_hex",
    "merkle_root",
    "leaf_hash",
    "node_hash",
    "DOMAIN_REWARD",
    "EMPTY_ROOT",
    "RewardLeaf",
    "reward_leaf_content",
    "reward_leaf_hash",
    "aggregate_contributions",
    "compile_reward_leaves",
    "reward_root",
    "cohort_prf",
    "derive_assignment",
    "seed_commitment",
    "switchback_phase",
    "parse_composite_cohort_id",
    "round_half_even_div",
    "reference_source_digest",
]

_MODULE_NAMES: Final = ("canonical", "merkle", "reward", "assignment", "evidence")


def _candidate_dirs() -> list[Path]:
    out: list[Path] = []
    env = os.environ.get("CRP_REFERENCE_DIR")
    if env:
        out.append(Path(env))
    # <repo>/causal-engine/src/crp_engine/reference.py -> parents[3] == <repo>
    out.append(Path(__file__).resolve().parents[3] / "verifier-cli" / "reference")
    out.append(Path(sys.prefix) / "share" / "crp" / "reference")
    return out


def _resolve_reference_dir() -> Path:
    tried: list[str] = []
    for cand in _candidate_dirs():
        tried.append(str(cand))
        if (cand / "canonical.py").is_file() and (cand / "reward.py").is_file():
            return cand.resolve()
    raise ImportError(
        "cannot locate the ratified reference implementation "
        "(verifier-cli/reference). Set $CRP_REFERENCE_DIR. Tried: " + "; ".join(tried)
    )


REFERENCE_DIR: Final[Path] = _resolve_reference_dir()


def _load(name: str) -> ModuleType:
    """Import ``<REFERENCE_DIR>/<name>.py`` under a namespaced module key.

    The reference modules import each other as top-level names (``from canonical import
    sha256``), so REFERENCE_DIR must be importable. We prepend it to ``sys.path`` once, then
    register each module under BOTH its bare name (so its siblings resolve) and a namespaced
    alias (so the engine's own modules are never shadowed).
    """
    if str(REFERENCE_DIR) not in sys.path:
        sys.path.insert(0, str(REFERENCE_DIR))
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, REFERENCE_DIR / (name + ".py"))
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise ImportError("cannot load reference module %r" % name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    sys.modules["crp_engine._ref_" + name] = mod
    spec.loader.exec_module(mod)
    return mod


_canonical = _load("canonical")
_merkle = _load("merkle")
_reward = _load("reward")
_assignment = _load("assignment")

# --- canonical serialization (serialization.md §2/§3) -------------------------------------
canonical_json_bytes = _canonical.canonical_json_bytes
sha256 = _canonical.sha256
sha256_hex = _canonical.sha256_hex

# --- merkle (serialization.md §6.1-§6.4) --------------------------------------------------
merkle_root = _merkle.merkle_root
leaf_hash = _merkle.leaf_hash
node_hash = _merkle.node_hash
DOMAIN_REWARD = _merkle.DOMAIN_REWARD
EMPTY_ROOT = _merkle.EMPTY_ROOT

# --- reward tree (serialization.md §6.6, RATIFIED v1.1) -----------------------------------
RewardLeaf = _reward.RewardLeaf
reward_leaf_content = _reward.reward_leaf_content
reward_leaf_hash = _reward.reward_leaf_hash
aggregate_contributions = _reward.aggregate_contributions
compile_reward_leaves = _reward.compile_reward_leaves
reward_root = _reward.reward_root

# --- assignment derivation (serialization.md §7) ------------------------------------------
cohort_prf = _assignment.cohort_prf
derive_assignment = _assignment.derive_assignment
seed_commitment = _assignment.seed_commitment
switchback_phase = _assignment.switchback_phase
parse_composite_cohort_id = _assignment.parse_composite_cohort_id
round_half_even_div = _assignment.round_half_even_div


def reference_source_digest() -> str:
    """sha256 over the reference module sources, in fixed name order.

    Recorded in ``provenance.json`` so an auditor can prove which oracle revision produced the
    committed bytes. Deterministic: fixed file order, raw bytes, no wall-clock.
    """
    h = __import__("hashlib").sha256()
    for name in _MODULE_NAMES:
        p = REFERENCE_DIR / (name + ".py")
        if not p.is_file():
            continue
        h.update(name.encode("ascii"))
        h.update(b"\x00")
        h.update(p.read_bytes())
        h.update(b"\x00")
    return "sha256:" + h.hexdigest()
