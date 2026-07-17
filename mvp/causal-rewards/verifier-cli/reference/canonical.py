"""Canonical serialization + hashing reference implementation.

This is the PROPOSED canonical form (see ../docs/canonical-serialization.md).
It is intentionally small and auditable. Zero network access, zero wall-clock,
zero unseeded randomness.

Core rules enforced here (all subject to protocol-architect ratification):

  * Canonical JSON is a strict subset of RFC 8785 (JCS): UTF-8, no insignificant
    whitespace, object keys sorted by UTF-16 code-unit order, minimal string
    escaping.
  * NO JSON number tokens are permitted in a hashed artifact. Every numeric
    value MUST be carried as a JSON string (decimal integer string, or a
    scaled fixed-point integer string). This deliberately removes any reliance
    on IEEE-754 / ES6 number canonicalization -- the one place JCS is
    language-dependent. The serializer REJECTS Python int/float to make the
    rule mechanical rather than a convention.
  * All string values and object keys are Unicode-NFC normalized before
    serialization.
"""

from __future__ import annotations

import hashlib
import unicodedata
from typing import Any

__all__ = ["canonical_json_bytes", "sha256", "sha256_hex"]


def sha256(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    """Serialize ``obj`` to canonical UTF-8 bytes.

    Accepts only: dict, list, str, bool, None. int/float are rejected on
    purpose (see module docstring). This guarantees the output contains no
    JSON number tokens.
    """
    out = bytearray()
    _ser(obj, out)
    return bytes(out)


def _ser(o: Any, out: bytearray) -> None:
    # bool must be checked before int, since bool is a subclass of int.
    if o is True:
        out += b"true"
    elif o is False:
        out += b"false"
    elif o is None:
        out += b"null"
    elif isinstance(o, str):
        _ser_str(o, out)
    elif isinstance(o, dict):
        _ser_obj(o, out)
    elif isinstance(o, (list, tuple)):
        _ser_arr(o, out)
    elif isinstance(o, (int, float)):
        raise TypeError(
            "numbers are forbidden in hashed artifacts; carry the value as a "
            "decimal or scaled-integer STRING instead (got %r)" % (o,)
        )
    else:
        raise TypeError("unserializable type: %r" % (type(o),))


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
    # Normalize keys (NFC) and sort by UTF-16 code-unit order (RFC 8785).
    # Comparing the utf-16-be byte encodings orders by UTF-16 code units.
    items = []
    seen = set()
    for k in d.keys():
        if not isinstance(k, str):
            raise TypeError("object keys must be strings, got %r" % (type(k),))
        nk = unicodedata.normalize("NFC", k)
        if nk in seen:
            raise ValueError("duplicate object key after NFC normalization: %r" % (nk,))
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


# Two-char escapes required/allowed by RFC 8785 minimal escaping.
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
    s = unicodedata.normalize("NFC", s)
    out += b'"'
    for ch in s:
        cp = ord(ch)
        esc = _SHORT_ESCAPES.get(cp)
        if esc is not None:
            out += esc
        elif cp < 0x20:
            out += ("\\u%04x" % cp).encode("ascii")
        else:
            out += ch.encode("utf-8")
    out += b'"'
