"""Canonical serialization: the single enforcement point for byte-stable, float-free hashing.

Conforms to specs/serialization.md (no floats in hashed bytes; integer-scaled decimals with
round-half-to-even; sorted keys; SHA-256 hex).
"""

from __future__ import annotations

import json
import math

import numpy as np
import pytest

from depin_sim.canonical import FLOAT_SCALE, canonical_bytes, content_hash, scale_decimal


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
    """The hashed bytes must contain no float literals (serialization.md §1.2)."""
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
