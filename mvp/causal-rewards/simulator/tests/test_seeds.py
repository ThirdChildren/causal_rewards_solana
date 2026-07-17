"""Seed derivation: reproducible, isolated streams, and stable assignment interface."""

from __future__ import annotations

import numpy as np

from depin_sim.seeds import build_rng_bundle, normalize_seed


def test_normalize_seed_hex_and_prefixes():
    assert normalize_seed("0x0f") == 15
    assert normalize_seed("sha256:0f") == 15
    assert normalize_seed("0F") == 15


def test_normalize_seed_non_hex_is_hashed_deterministically():
    a = normalize_seed("not-hex-seed")
    b = normalize_seed("not-hex-seed")
    assert a == b
    assert normalize_seed("not-hex-seed") != normalize_seed("other-seed")


def test_streams_are_reproducible():
    b1 = build_rng_bundle("0xabc123")
    b2 = build_rng_bundle("0xabc123")
    for name in ("network", "faults", "observations", "outcome", "assignment"):
        x1 = b1.stream(name).random(5)
        x2 = b2.stream(name).random(5)
        np.testing.assert_array_equal(x1, x2)


def test_streams_are_independent():
    b = build_rng_bundle("0xabc123")
    net = b.stream("network").random(10)
    obs = b.stream("observations").random(10)
    # Independent streams should not be identical.
    assert not np.array_equal(net, obs)


def test_unknown_stream_raises():
    b = build_rng_bundle("0x1")
    try:
        b.stream("does_not_exist")
    except KeyError:
        return
    raise AssertionError("expected KeyError for unknown stream")
