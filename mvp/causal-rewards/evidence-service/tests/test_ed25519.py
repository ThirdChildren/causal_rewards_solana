"""ed25519: RFC-8032 vectors + pure/accelerated backend parity."""

from __future__ import annotations

import pytest

from crp_evidence import ed25519

# RFC 8032 §7.1 TEST 1 and TEST 2.
RFC8032 = [
    (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e3970"
        "1cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613"
        "d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
]


@pytest.mark.parametrize("secret_hex,public_hex,msg_hex,sig_hex", RFC8032)
def test_rfc8032_vectors(secret_hex: str, public_hex: str, msg_hex: str, sig_hex: str) -> None:
    secret = bytes.fromhex(secret_hex)
    msg = bytes.fromhex(msg_hex)
    assert ed25519.public_key_from_secret(secret).hex() == public_hex
    assert ed25519.sign_deterministic(secret, msg).hex() == sig_hex
    assert ed25519.verify_pure(bytes.fromhex(public_hex), msg, bytes.fromhex(sig_hex))
    assert ed25519.verify(bytes.fromhex(public_hex), msg, bytes.fromhex(sig_hex))


def test_backends_agree_on_valid_and_invalid_inputs() -> None:
    """The accelerated backend must accept/reject exactly what the reference path does."""
    secret = bytes([7]) * 32
    pub = ed25519.public_key_from_secret(secret)
    msg = b"causal-rewards evidence batch"
    sig = ed25519.sign_deterministic(secret, msg)
    cases = [
        (pub, msg, sig, True),
        (pub, msg + b"!", sig, False),
        (pub, msg, bytes(64), False),
        (bytes(32), msg, sig, False),
        (pub, msg, sig[:63], False),
        (pub[:31], msg, sig, False),
    ]
    for k, m, s, expected in cases:
        assert ed25519.verify_pure(k, m, s) is expected
        assert ed25519.verify(k, m, s) is expected


def test_verify_never_raises_on_garbage() -> None:
    assert ed25519.verify(b"", b"", b"") is False
    assert ed25519.verify(b"\xff" * 32, b"x", b"\x00" * 64) is False


def test_signing_is_deterministic() -> None:
    secret = bytes([9]) * 32
    a = ed25519.sign_deterministic(secret, b"m")
    b = ed25519.sign_deterministic(secret, b"m")
    assert a == b
