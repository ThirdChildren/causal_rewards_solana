"""Deterministic seed derivation.

The committed seed is a hex string (conceptually a 32-byte on-chain commitment preimage,
e.g. the reveal of ``assignment_seed_commitment`` in the frozen manifest). Every random
draw in the simulator descends from this single value via numpy ``SeedSequence`` spawning.

Why SeedSequence spawning: it gives statistically independent, reproducible child streams
per component. Adding a NEW component at the END of the spawn order does not perturb the
draws of existing components, so scenarios stay stable as the simulator grows. The spawn
order below is therefore a CONTRACT — do not reorder or insert in the middle.

NOTE (interface): the seed -> treatment-assignment mapping is deliberately NOT here. It
lives in ``assignment.py`` behind a single function so it can later be swapped for the
canonical seed->assignment derivation ratified by verifier-reproducibility-engineer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np

# Fixed, ordered list of random streams. Order is a determinism contract (see module doc).
# Append-only: new streams go at the end.
_STREAM_ORDER: tuple[str, ...] = (
    "network",       # sensor placement, cell attributes
    "quality",       # per-sensor hardware quality
    "sybil",         # sybil selection / grouping
    "faults",        # per-sensor per-time-block faults
    "demand",        # demand shift over time blocks
    "observations",  # signed-observation counts
    "outcome",       # cohort x time-block outcome (held-out RMSE) draws
    "assignment",    # reserved for assignment (consumed via assignment.py)
)


def normalize_seed(seed: str) -> int:
    """Map a committed-seed string to a stable non-negative integer.

    Accepts an optional ``0x`` / ``sha256:`` prefix and hex digits, OR an arbitrary
    string (hashed with sha256). This keeps the alpha flexible while staying fully
    deterministic. The canonical on-chain form (32-byte hex) passes through the hex path.
    """
    s = seed.strip()
    for prefix in ("sha256:", "0x", "0X"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    try:
        return int(s, 16)
    except ValueError:
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
        return int(digest, 16)


@dataclass(frozen=True)
class RngBundle:
    """A fixed set of independent, reproducible generators keyed by stream name."""

    _generators: dict[str, np.random.Generator]

    def stream(self, name: str) -> np.random.Generator:
        if name not in self._generators:
            raise KeyError(
                f"unknown rng stream {name!r}; known streams: {sorted(self._generators)}"
            )
        return self._generators[name]


def build_rng_bundle(seed: str) -> RngBundle:
    """Derive every simulator random stream from the single committed seed."""
    root = np.random.SeedSequence(normalize_seed(seed))
    children = root.spawn(len(_STREAM_ORDER))
    generators = {
        name: np.random.Generator(np.random.PCG64(child))
        for name, child in zip(_STREAM_ORDER, children)
    }
    return RngBundle(generators)
