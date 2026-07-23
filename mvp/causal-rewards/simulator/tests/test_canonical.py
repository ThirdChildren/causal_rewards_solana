"""Canonical serialization: the single enforcement point for byte-stable, float-free hashing.

Conforms to specs/serialization.md (no floats in hashed bytes; integer-scaled decimals with
round-half-to-even; NFC-normalized keys/values sorted by UTF-16 code unit; minimal escaping;
raw UTF-8; SHA-256 hex). The parity tests below prove the simulator's encoder is byte-for-byte
identical to the ratified reference (verifier-cli/reference/canonical.py) on the shared,
number-free value domain — including NON-ASCII values and keys. Closes carried discrepancy #2.

Non-ASCII literals here are written with explicit ``\\u`` escapes so the test source is
encoding-agnostic and unambiguous about decomposed vs precomposed forms.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pytest

from depin_sim.canonical import FLOAT_SCALE, canonical_bytes, content_hash, scale_decimal

# --- Load the RATIFIED reference serializer (verifier-cli/reference/canonical.py) as the
# --- byte-level authority (serialization.md §2/§3/§4). The simulator's encoder MUST agree with
# --- it byte-for-byte on the shared value domain (str/dict/list/bool/None). This is the
# --- committed anti-drift oracle for the cross-checked golden hash.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_REF_PATH = _REPO_ROOT / "verifier-cli" / "reference" / "canonical.py"
_VECTORS_DIR = _REPO_ROOT / "test-vectors" / "serialization"


def _load_reference():
    spec = importlib.util.spec_from_file_location("_crp_reference_canonical", _REF_PATH)
    assert spec and spec.loader, f"cannot load reference serializer at {_REF_PATH}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_REF = _load_reference()


# ------------------------------- existing float-free / scaling contract -------------------------

def test_negative_zero_normalized():
    assert scale_decimal(-0.0) == scale_decimal(0.0) == 0


def test_scale_is_integer_micro():
    assert scale_decimal(0.5) == 500_000
    assert scale_decimal(1.0) == FLOAT_SCALE
    assert isinstance(scale_decimal(0.123456), int)


def test_round_half_to_even():
    # 0.0000005 * 1e6 = 0.5 -> rounds to even (0); 0.0000015 -> 1.5 -> 2.
    assert scale_decimal(0.0000005) == 0
    assert scale_decimal(0.0000015) == 2


def test_non_finite_rejected():
    with pytest.raises(ValueError):
        scale_decimal(math.inf)
    with pytest.raises(ValueError):
        scale_decimal(math.nan)


def test_no_float_tokens_in_bytes():
    """The hashed bytes must contain no float literals (serialization.md §2)."""
    b = canonical_bytes({"x": 0.25, "y": [1.5, 2.5], "z": {"w": np.float64(3.14159)}})
    text = b.decode("utf-8")
    # Every number token must be an integer: no '.' outside of strings.
    parsed = json.loads(text)
    assert parsed["x"] == 250_000
    assert "." not in text


def test_numpy_and_python_equal_hash():
    py = {"a": [1, 2, 3], "b": 0.5, "c": True}
    npy = {"a": np.array([1, 2, 3]), "b": np.float64(0.5), "c": np.bool_(True)}
    assert content_hash(py) == content_hash(npy)


def test_key_order_independent():
    assert canonical_bytes({"a": 1, "b": 2}) == canonical_bytes({"b": 2, "a": 1})


def test_int_vs_scaled_float_collision_is_explicit():
    # 1 (int) and 0.000001 (-> scaled 1) both serialize to integer 1; callers must not mix
    # semantic types in one field. Documents the integer-scaling contract.
    assert content_hash({"x": 1}) == content_hash({"x": 0.000001})


# --------------------------------------------------------------------------------------------
# Parity with the ratified reference serializer (verifier-cli/reference/canonical.py).
#
# The reference is a hashed-PROTOCOL-ARTIFACT serializer and forbids all JSON number tokens
# (serialization.md §2 — numbers are carried as decimal STRINGS), so the parity fixtures are
# number-free (the shared value domain). On that domain the simulator's canonical_bytes MUST
# equal the reference byte-for-byte, incl. NON-ASCII values/keys, NFC normalization, UTF-16
# key ordering, and minimal escaping.
# --------------------------------------------------------------------------------------------

_ACUTE = "́"          # COMBINING ACUTE ACCENT (decomposed accent)
_E_ACUTE = "é"        # é  (precomposed)
_A_UML = "ä"          # ä
_O_UML = "ö"          # ö
_N_TILDE = "ñ"        # ñ
_A_GRAVE = "à"        # à
_SS = "ß"            # ß
_GRIN = "\U0001f600"      # 😀 (astral / non-BMP)
_FW_A = "Ａ"          # Ａ  (fullwidth A, BMP > U+E000)
_CJK = ("名前", "太郎", "都市", "東京")  # 名前 太郎 都市 東京

# café / resumé / näme / straße / thé / clé built explicitly.
_CAFE = "caf" + _E_ACUTE
_CAFE_DECOMP = "cafe" + _ACUTE
_RESUME = "resum" + _E_ACUTE
_RESUME_DECOMP = "resume" + _ACUTE
_NAME = "n" + _A_UML + "me"
_STRASSE = "stra" + _SS + "e"
_THE = "th" + _E_ACUTE
_CLE_DECOMP = "cle" + _ACUTE

# Number-free payloads exercising the non-ASCII paths the old `ensure_ascii=True` serializer
# got wrong. Each is (label, payload).
_NON_ASCII_FIXTURES = [
    ("accented-value", {"city": _CAFE}),
    ("accented-key", {_CAFE: "value"}),
    # DECOMPOSED input (base char + U+0301) must serialize to PRECOMPOSED bytes in keys & values.
    ("nfc-decomposed-key", {_CAFE_DECOMP: "value"}),
    ("nfc-decomposed-value", {"k": _RESUME_DECOMP}),
    ("nfc-mixed", {_NAME: _STRASSE, _CAFE: _RESUME}),
    ("non-ascii-emoji-value", {"status": "ok " + _GRIN + " done"}),
    ("non-ascii-cjk", {_CJK[0]: _CJK[1], _CJK[2]: _CJK[3]}),
    ("forward-slash-raw", {"path": "a/b/c"}),
    ("mixed-ascii-nonascii-keys", {"z": "1", _A_GRAVE: "2", "a": "3", _E_ACUTE: "4"}),
    ("nested-non-ascii", {"outer": [{_CLE_DECOMP: "valeur"}, {_CAFE: _THE}]}),
    ("bool-null-nonascii", {_CAFE: True, _THE: None, "e" + _N_TILDE + "e": [False, "x"]}),
]


@pytest.mark.parametrize("label,payload", _NON_ASCII_FIXTURES, ids=[f[0] for f in _NON_ASCII_FIXTURES])
def test_parity_with_reference_on_non_ascii(label, payload):
    """Simulator canonical bytes == ratified reference bytes on non-ASCII, number-free payloads."""
    sim = canonical_bytes(payload)
    ref = _REF.canonical_json_bytes(payload)
    assert sim == ref, f"{label}: sim {sim!r} != reference {ref!r}"
    # And therefore identical SHA-256 (the cross-checked golden hash property).
    assert hashlib.sha256(sim).hexdigest() == _REF.sha256_hex(ref)


def test_parity_raw_utf8_not_escaped():
    """Old bug (a): ensure_ascii=True emitted \\uXXXX; spec §4 demands raw UTF-8."""
    b = canonical_bytes({"city": _CAFE})
    assert b"\\u" not in b  # no unicode escapes
    assert _CAFE.encode("utf-8") in b  # raw UTF-8 bytes (…c3 a9) present
    assert b"\xc3\xa9" in b  # é precomposed UTF-8
    assert b == _REF.canonical_json_bytes({"city": _CAFE})


def test_parity_nfc_decomposed_equals_precomposed():
    """Old bug (b): no NFC normalization. Decomposed and precomposed must hash identically."""
    decomposed = {_CAFE_DECOMP: _RESUME_DECOMP}  # base letters + U+0301
    precomposed = {_CAFE: _RESUME}               # single code points U+00E9
    assert decomposed != precomposed             # genuinely distinct Python strings
    assert canonical_bytes(decomposed) == canonical_bytes(precomposed)
    assert content_hash(decomposed) == content_hash(precomposed)
    # Precomposed UTF-8 bytes (c3 a9) appear; the decomposed combining mark (cc 81) does not.
    assert b"\xc3\xa9" in canonical_bytes(decomposed)
    assert b"\xcc\x81" not in canonical_bytes(decomposed)
    assert canonical_bytes(decomposed) == _REF.canonical_json_bytes(decomposed)


def test_parity_key_order_is_utf16_not_codepoint():
    """Old bug (c): align key ordering to UTF-16 code units, not Unicode code points.

    An astral key (U+1F600, encoded as a surrogate pair whose first unit is 0xD83D) sorts
    BEFORE a BMP key in 0xE000..0xFFFF (U+FF21) under UTF-16, but AFTER it under code-point
    order. The simulator must match the reference (UTF-16), i.e. differ from a naive sort.
    """
    payload = {_GRIN: "astral", _FW_A: "bmp", "a": "ascii"}
    sim = canonical_bytes(payload)
    assert sim == _REF.canonical_json_bytes(payload)
    # UTF-16 order places the astral key before the BMP key; a code-point sort would not.
    astral_pos = sim.index(b'"' + _GRIN.encode("utf-8") + b'"')
    bmp_pos = sim.index(b'"' + _FW_A.encode("utf-8") + b'"')
    assert astral_pos < bmp_pos
    # Confirm this is genuinely the UTF-16 discriminator (differs from code-point order).
    assert ord(_GRIN) > ord(_FW_A)


def test_parity_duplicate_key_after_nfc_is_hard_error():
    """§3.3: duplicate keys after NFC normalization are a hard error (never last-wins)."""
    # Distinct Python keys (decomposed vs precomposed) that collide only after NFC.
    dup = {_CAFE_DECOMP: "1", _CAFE: "2"}
    assert len(dup) == 2  # distinct before normalization
    with pytest.raises(ValueError):
        canonical_bytes(dup)
    with pytest.raises(ValueError):
        _REF.canonical_json_bytes(dup)


def _load_ser_vector(name):
    return json.loads((_VECTORS_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "vector_name",
    [
        "ser-01-key-ordering.json",
        "ser-02-unicode-nfc.json",
        "ser-04-control-and-escapes.json",
        "ser-05-nested-mixed.json",
    ],
)
def test_matches_committed_ser_golden_vectors(vector_name):
    """Simulator reproduces the committed ser-* golden bytes/hash (number-free vectors).

    These vectors are the spec's conformance oracles; the simulator, the reference, and the
    on-chain crp-crypto all target the same bytes.
    """
    vec = _load_ser_vector(vector_name)
    payload = vec["input"]
    expected_bytes = vec["canonical_bytes_utf8"].encode("utf-8")
    sim = canonical_bytes(payload)
    assert sim == expected_bytes, f"{vector_name}: {sim!r} != golden {expected_bytes!r}"
    assert content_hash(payload) == vec["sha256_hex"]
    # Belt-and-suspenders: also equals the live reference output.
    assert sim == _REF.canonical_json_bytes(payload)
