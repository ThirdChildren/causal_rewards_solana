"""ed25519 verification (RFC 8032), dependency-free reference path.

Why a pure-Python verifier at all: the evidence service must be auditable and runnable in a
minimal container with no native extensions, and signature *verification* is a pure function
with no determinism hazards. Batch signatures are one per batch (hundreds per epoch, not
millions), so the pure-Python path is fast enough for the anchored artifact path.

An optional accelerated backend (``cryptography``) is used when available and MUST agree with
the reference path on every input; ``tests/test_ed25519.py`` is the parity gate. Verification
is a boolean predicate, so "agreement" means identical accept/reject, not identical bytes.

Signature verification only — this module never generates keys or signatures (no RNG lives in
any artifact-producing path, invariant 2). Test fixtures that need a signature use RFC-8032
DETERMINISTIC signing via ``sign_deterministic`` (test-only, seeded by a fixed 32-byte key).
"""

from __future__ import annotations

import hashlib

__all__ = ["verify", "sign_deterministic", "public_key_from_secret", "ACCELERATED"]

# --- curve constants (RFC 8032 / edwards25519) ---
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)
_By = 4 * pow(5, _P - 2, _P) % _P


def _x_recover(y: int) -> int:
    xx = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P)
    x = pow(xx, (_P + 3) // 8, _P)
    if (x * x - xx) % _P != 0:
        x = (x * _I) % _P
    if x % 2 != 0:
        x = _P - x
    return x


_Bx = _x_recover(_By)
_B = (_Bx % _P, _By % _P, 1, (_Bx * _By) % _P)


def _edwards_add(p: tuple[int, int, int, int], q: tuple[int, int, int, int]):
    x1, y1, z1, t1 = p
    x2, y2, z2, t2 = q
    a = (y1 - x1) * (y2 - x2) % _P
    b = (y1 + x1) * (y2 + x2) % _P
    c = t1 * 2 * _D * t2 % _P
    dd = z1 * 2 * z2 % _P
    e, f, g, h = b - a, dd - c, dd + c, b + a
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _edwards_double(p: tuple[int, int, int, int]):
    return _edwards_add(p, p)


def _scalarmult(p: tuple[int, int, int, int], e: int):
    q = (0, 1, 1, 0)
    while e > 0:
        if e & 1:
            q = _edwards_add(q, p)
        p = _edwards_double(p)
        e >>= 1
    return q


def _point_compress(p: tuple[int, int, int, int]) -> bytes:
    x, y, z, _t = p
    zinv = pow(z, _P - 2, _P)
    x = x * zinv % _P
    y = y * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(s: bytes):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = (y >> 255) & 1
    y &= (1 << 255) - 1
    if y >= _P:
        return None
    x = _x_recover(y)
    if x == 0 and sign:
        return None
    if x & 1 != sign:
        x = _P - x
    return (x, y, 1, x * y % _P)


def _sha512_int(b: bytes) -> int:
    return int.from_bytes(hashlib.sha512(b).digest(), "little")


def _verify_pure(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _point_decompress(public_key)
    if a is None:
        return False
    rs = signature[:32]
    r = _point_decompress(rs)
    if r is None:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _L:
        return False
    h = _sha512_int(rs + public_key + message) % _L
    sb = _scalarmult(_B, s)
    ha = _scalarmult(a, h)
    rha = _edwards_add(r, ha)
    # cofactored check: [8]sB == [8](R + [h]A)
    for _ in range(3):
        sb = _edwards_double(sb)
        rha = _edwards_double(rha)
    return _point_compress(sb) == _point_compress(rha)


try:  # pragma: no cover - availability depends on the container
    from cryptography.exceptions import InvalidSignature as _InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PublicKey as _Ed25519PublicKey,
    )

    ACCELERATED = True
except Exception:  # pragma: no cover
    ACCELERATED = False


def _verify_accel(public_key: bytes, message: bytes, signature: bytes) -> bool:  # pragma: no cover
    if len(public_key) != 32 or len(signature) != 64:
        return False
    try:
        _Ed25519PublicKey.from_public_bytes(public_key).verify(signature, message)
        return True
    except (_InvalidSignature, ValueError):
        return False


def verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """Return True iff ``signature`` is a valid ed25519 signature of ``message``.

    Never raises on malformed input — a bad key/signature length is simply ``False``, so the
    caller decides the rejection code.
    """
    if ACCELERATED:
        return _verify_accel(public_key, message, signature)
    return _verify_pure(public_key, message, signature)


def verify_pure(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """The dependency-free path, exposed for the backend-parity test."""
    return _verify_pure(public_key, message, signature)


# --- test-fixture helpers (deterministic; NOT used in any artifact-producing path) ---


def _secret_expand(secret: bytes) -> tuple[int, bytes]:
    if len(secret) != 32:
        raise ValueError("secret key must be 32 bytes")
    h = hashlib.sha512(secret).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def public_key_from_secret(secret: bytes) -> bytes:
    """Derive the 32-byte public key from a FIXED 32-byte secret (fixtures only)."""
    a, _ = _secret_expand(secret)
    return _point_compress(_scalarmult(_B, a))


def sign_deterministic(secret: bytes, message: bytes) -> bytes:
    """RFC-8032 deterministic signature (fixtures only; no RNG, byte-stable for goldens)."""
    a, prefix = _secret_expand(secret)
    pub = _point_compress(_scalarmult(_B, a))
    r = _sha512_int(prefix + message) % _L
    rp = _point_compress(_scalarmult(_B, r))
    h = _sha512_int(rp + pub + message) % _L
    s = (r + h * a) % _L
    return rp + int.to_bytes(s, 32, "little")
