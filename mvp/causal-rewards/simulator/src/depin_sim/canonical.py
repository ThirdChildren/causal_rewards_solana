"""Canonical serialization + content hashing.

Determinism is the primary acceptance criterion (CLAUDE.md #2). We hash a CANONICAL, byte-
stable serialization of the run outputs — NOT parquet bytes (parquet embeds library versions /
padding and is not byte-stable).

This serializer conforms to ``specs/serialization.md`` (owned by protocol-architect, source of
truth), so the simulator's determinism story reuses the SAME rules as the on-chain manifest /
reward-root hashes. Key normative rules honored here:

  * NO floating-point in the hashed bytes (serialization.md §1.2). Every real value is
    integer-scaled: ``stored = round_half_even(value * FLOAT_SCALE)`` (§1.3, banker's rounding
    applied exactly once, at this boundary). ``FLOAT_SCALE`` is recorded in the payload.
  * Provisional canonical JSON (serialization.md §2): object keys sorted ascending by Unicode
    code point, two-char separators, minimal whitespace, integers only, UTF-8, SHA-256 hex.

NOTE: serialization.md §3 (RATIFIED) is still pending. If the ratified byte-level algorithm
differs from the provisional one, THIS module is the single place to reconcile, and any
committed golden hashes here are regenerated in the same change. Coordinate with
protocol-architect and verifier-reproducibility-engineer before freezing a golden hash.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import numpy as np

# Global decimal scale for the simulator's hashed content (micro precision, 1e-6).
# Analogous to the manifest's per-field ``*_micro`` scaling in serialization.md §1.3.
FLOAT_SCALE = 1_000_000


def scale_decimal(x: float, scale: int = FLOAT_SCALE) -> int:
    """Integer-scale a real value with round-half-to-even, the protocol's sole rounding rule.

    Uses Decimal(repr(x)) so the scaling is a deterministic function of the float64 value
    (repr is the shortest round-tripping string) rather than of float*int drift.
    """
    xf = float(x)
    if not np.isfinite(xf):
        raise ValueError(f"non-finite value {xf!r} cannot be canonicalized")
    d = Decimal(repr(xf)) * scale
    q = d.quantize(Decimal(1), rounding=ROUND_HALF_EVEN)
    i = int(q)
    return 0 if i == 0 else i  # collapse a possible -0


def _canon(obj: Any) -> Any:
    """Recursively convert numpy / nested structures into float-free JSON-canonical primitives."""
    if isinstance(obj, dict):
        return {str(k): _canon(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_canon(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _canon(obj.tolist())
    if isinstance(obj, (bool, np.bool_)):
        return bool(obj)
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        return scale_decimal(float(obj))  # -> integer, no float enters the bytes
    if obj is None or isinstance(obj, str):
        return obj
    raise TypeError(f"cannot canonicalize object of type {type(obj)!r}")


def canonical_bytes(payload: dict) -> bytes:
    """Serialize a payload dict to canonical bytes (provisional CJSON per serialization.md §2)."""
    canon = _canon(payload)
    text = json.dumps(
        canon,
        sort_keys=True,          # ascending by code point (RFC 8785 / serialization.md §2)
        ensure_ascii=True,
        separators=(",", ":"),   # no insignificant whitespace
        allow_nan=False,         # defense in depth: no NaN/Inf tokens
    )
    return text.encode("utf-8")


def content_hash(payload: dict) -> str:
    """SHA-256 hex digest of the canonical serialization of ``payload``."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
