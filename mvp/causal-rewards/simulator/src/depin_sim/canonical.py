"""Canonical serialization + content hashing.

Determinism is the primary acceptance criterion (CLAUDE.md #2). We hash a CANONICAL, byte-
stable serialization of the run outputs — NOT parquet bytes (parquet embeds library versions /
padding and is not byte-stable).

This serializer conforms to ``specs/serialization.md`` (RATIFIED, owned by protocol-architect,
source of truth) and is **byte-for-byte identical to the ratified reference implementation**
``verifier-cli/reference/canonical.py`` on the shared value domain (strings, keys, booleans,
null, arrays, objects). That parity is what lets the simulator emit a cross-checked golden hash:
the simulator's determinism story reuses the SAME §2/§3/§4 rules as the on-chain manifest /
reward-root hashes and the verifier reference. The `verifier-reproducibility-engineer` re-verifies
this with an independent non-ASCII fixture; the parity test in ``tests/test_canonical.py`` is the
committed anti-drift oracle (it imports the reference and asserts byte equality).

Normative rules honored here (serialization.md §2/§3/§4):

  * **No floating-point in the hashed bytes** (§2, §1). Every real value is integer-scaled:
    ``stored = round_half_even(value * FLOAT_SCALE)`` (banker's rounding applied exactly once,
    at this boundary). ``FLOAT_SCALE`` matches the spec's default *micro* scale (1e6, §2.2).
  * **Canonical JSON** (§3): object keys NFC-normalized then ordered ascending by UTF-16
    code-unit sequence (§3.3, §3.5); two-character-free separators ``,`` and ``:`` with no
    insignificant whitespace (§3.2); duplicate keys after NFC are a hard error (§3.3); UTF-8,
    no BOM.
  * **Minimal string escaping** (§4): ``"`` ``\\`` and the five short controls
    (``\\b \\t \\n \\f \\r``); any other ``U+0000``–``U+001F`` as lowercase ``\\u00xx``; every
    other character — including ``/`` and all non-ASCII — as raw UTF-8 (NOT ``\\u``-escaped).

DIVERGENCE FROM THE REFERENCE (deliberate, single-point, documented): the ratified reference is a
hashed-*protocol-artifact* serializer and therefore FORBIDS every JSON number token (§2 — numbers
must be carried as decimal strings), rejecting ``int``/``float``. The simulator's content hash is
NOT an on-chain protocol artifact; it is an internal determinism check. It carries integer-scaled
values as bare **integer** number tokens (never floats), which keeps the committed ASCII baseline
hash stable and avoids re-encoding every count/scaled-decimal as a string. Consequently the two
encoders are byte-identical **only on number-free payloads** (which is exactly the shared domain
the parity fixtures — and all ``ser-*`` golden vectors — exercise). This module introduces no
*divergent* rule: for every value type the reference accepts, it applies the reference's rules
verbatim; it only additionally accepts integer number tokens.
"""

from __future__ import annotations

import hashlib
import unicodedata
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

import numpy as np

# Global decimal scale for the simulator's hashed content (micro precision, 1e-6).
# Matches the manifest's default *micro* scaling in serialization.md §2.2.
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
    """Recursively convert numpy / nested structures into float-free JSON-canonical primitives.

    After this pass every leaf is one of: ``str``, ``bool``, ``int``, or ``None``; every node is
    a ``dict`` or ``list``. Floats become integer-scaled ``int`` here so no float ever reaches the
    byte serializer.
    """
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


# --- Byte serializer: byte-for-byte identical to verifier-cli/reference/canonical.py on the
# --- shared value domain (str/dict/list/bool/None). Kept in lockstep by the parity test.

# Two-char escapes required by serialization.md §4 (RFC 8785 minimal escaping).
_SHORT_ESCAPES = {
    0x08: b"\\b",
    0x09: b"\\t",
    0x0A: b"\\n",
    0x0C: b"\\f",
    0x0D: b"\\r",
    0x22: b'\\"',
    0x5C: b"\\\\",
}


def _ser_str(s: str, out: bytearray) -> None:
    """Serialize a string: NFC-normalize (§3.5), minimal escaping (§4), raw UTF-8 otherwise."""
    s = unicodedata.normalize("NFC", s)
    out += b'"'
    for ch in s:
        cp = ord(ch)
        esc = _SHORT_ESCAPES.get(cp)
        if esc is not None:
            out += esc
        elif cp < 0x20:
            out += ("\\u%04x" % cp).encode("ascii")  # lowercase hex (§4)
        else:
            out += ch.encode("utf-8")
    out += b'"'


def _ser(o: Any, out: bytearray) -> None:
    # bool must precede int (bool is an int subclass). These branches mirror the reference.
    if o is True:
        out += b"true"
    elif o is False:
        out += b"false"
    elif o is None:
        out += b"null"
    elif isinstance(o, str):
        _ser_str(o, out)
    elif isinstance(o, int):
        # SIMULATOR EXTENSION (see module docstring): float-free content hash carries scaled
        # reals + counts as bare INTEGER number tokens. str(int) is canonical decimal:
        # no leading zeros, sign only on negatives, no "-0" (scale_decimal collapses it).
        out += str(o).encode("ascii")
    elif isinstance(o, dict):
        _ser_obj(o, out)
    elif isinstance(o, (list, tuple)):
        _ser_arr(o, out)
    elif isinstance(o, float):
        # Unreachable after _canon; a float in the byte layer would be a determinism bug.
        raise TypeError("float reached the byte serializer; _canon must integer-scale it first")
    else:
        raise TypeError(f"cannot serialize object of type {type(o)!r}")


def _ser_arr(a: Any, out: bytearray) -> None:
    out += b"["
    first = True
    for item in a:
        if not first:
            out += b","
        first = False
        _ser(item, out)
    out += b"]"


def _ser_obj(d: dict, out: bytearray) -> None:
    # NFC-normalize keys (§3.5) and sort by UTF-16 code-unit order (§3.3): comparing the
    # utf-16-be byte encodings orders by UTF-16 code units. Duplicate keys after NFC are a
    # hard error (§3.3 — never last-wins).
    items: list[tuple[str, Any]] = []
    seen: set[str] = set()
    for k in d.keys():
        if not isinstance(k, str):
            raise TypeError(f"object keys must be strings, got {type(k)!r}")
        nk = unicodedata.normalize("NFC", k)
        if nk in seen:
            raise ValueError(f"duplicate object key after NFC normalization: {nk!r}")
        seen.add(nk)
        items.append((nk, d[k]))
    items.sort(key=lambda kv: kv[0].encode("utf-16-be"))

    out += b"{"
    first = True
    for k, v in items:
        if not first:
            out += b","
        first = False
        _ser_str(k, out)
        out += b":"
        _ser(v, out)
    out += b"}"


def canonical_bytes(payload: dict) -> bytes:
    """Serialize a payload dict to canonical UTF-8 bytes (CJSON per serialization.md §2/§3/§4)."""
    canon = _canon(payload)
    out = bytearray()
    _ser(canon, out)
    return bytes(out)


def content_hash(payload: dict) -> str:
    """SHA-256 hex digest of the canonical serialization of ``payload``."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
