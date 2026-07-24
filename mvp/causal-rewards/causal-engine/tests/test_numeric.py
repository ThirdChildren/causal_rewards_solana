"""Known-answer tests for the bit-reproducible numeric primitives."""

from __future__ import annotations

import math
import random
from fractions import Fraction

import numpy as np
import pytest

from crp_engine import numeric as nm


# ---------------------------------------------------------------- rounding / quantization

@pytest.mark.parametrize(
    "value,scale,expected",
    [
        (0.0, -6, 0),
        (1.0, -6, 1_000_000),
        (-0.30, -6, -300_000),
        (0.0000005, -6, 0),      # exactly .5 at 1e-6 resolution -> ties to EVEN (0)
        (0.0000015, -6, 2),      # ties to even (2), not 1
        (-0.0000005, -6, 0),
        (-0.0000015, -6, -2),
        (0.123456789, -6, 123_457),
        (12.3, 0, 12),
        (12.5, 0, 12),           # banker's rounding
        (13.5, 0, 14),
        (-12.5, 0, -12),
        (-13.5, 0, -14),
    ],
)
def test_quantize_round_half_even(value: float, scale: int, expected: int) -> None:
    assert nm.quantize(value, scale) == expected


def test_quantize_is_exact_not_repr_based() -> None:
    """0.1+0.2 is 0.30000000000000004; quantizing at 1e-6 must use the EXACT binary value."""
    assert nm.quantize(0.1 + 0.2, -6) == 300_000
    assert nm.quantize(0.1 + 0.2, -17) == 30000000000000004


def test_quantize_rejects_non_finite() -> None:
    for bad in (math.inf, -math.inf, math.nan):
        with pytest.raises(ValueError):
            nm.quantize(bad, -6)


def test_round_half_even_div_known_answers() -> None:
    assert nm.round_half_even_div(1_645_000 * 80_000, 1_000_000) == 131_600
    assert nm.round_half_even_div(5, 2) == 2       # 2.5 -> 2
    assert nm.round_half_even_div(7, 2) == 4       # 3.5 -> 4
    assert nm.round_half_even_div(4, 2) == 2


# ---------------------------------------------------------------- reductions

def test_fsum_is_order_independent() -> None:
    rng = random.Random(20260723)
    vals = [rng.uniform(-1e8, 1e8) for _ in range(5000)]
    shuffled = vals[:]
    rng.shuffle(shuffled)
    assert nm.fsum(vals) == nm.fsum(shuffled)


def test_fsum_beats_naive_accumulation_on_a_catastrophic_case() -> None:
    """The classic case where naive summation loses the answer entirely."""
    vals = [1.0, 1e100, 1.0, -1e100]
    assert nm.fsum(vals) == 2.0
    naive = 0.0
    for v in vals:  # explicit left-to-right accumulation, as a BLAS kernel would do
        naive += v
    assert naive == 0.0


def test_dot_matches_exact_rational_arithmetic() -> None:
    rng = random.Random(7)
    a = np.array([rng.uniform(-3, 3) for _ in range(500)])
    b = np.array([rng.uniform(-3, 3) for _ in range(500)])
    exact = sum((Fraction(x) * Fraction(y) for x, y in zip(a.tolist(), b.tolist())), Fraction(0))
    # fsum of the (already-rounded) products is the exactly-rounded sum of those products.
    prods = [Fraction(float(x * y)) for x, y in zip(a.tolist(), b.tolist())]
    assert nm.dot(a, b) == float(sum(prods, Fraction(0)))
    assert abs(nm.dot(a, b) - float(exact)) < 1e-9


# ---------------------------------------------------------------- linear algebra

def test_solve_known_answer() -> None:
    A = [[2.0, 1.0], [1.0, 3.0]]
    b = [5.0, 10.0]
    x = nm.solve(A, b)
    assert x == pytest.approx([1.0, 3.0], abs=1e-12)


def test_solve_matches_numpy_within_tolerance() -> None:
    rng = np.random.default_rng(11)
    A = rng.normal(size=(6, 6))
    A = (A @ A.T + 6 * np.eye(6)).tolist()
    b = rng.normal(size=6).tolist()
    assert nm.solve(A, b) == pytest.approx(np.linalg.solve(np.array(A), np.array(b)).tolist(), rel=1e-9)


def test_solve_rejects_singular() -> None:
    with pytest.raises(nm.SingularMatrixError):
        nm.solve([[1.0, 2.0], [2.0, 4.0]], [1.0, 2.0])


def test_inverse_round_trips() -> None:
    A = [[4.0, 1.0, 0.0], [1.0, 3.0, 1.0], [0.0, 1.0, 2.0]]
    Ainv = nm.inverse(A)
    prod = nm.matmul(A, Ainv)
    for i in range(3):
        for j in range(3):
            assert prod[i][j] == pytest.approx(1.0 if i == j else 0.0, abs=1e-12)


def test_gram_is_symmetric_and_blas_free() -> None:
    rng = np.random.default_rng(3)
    X = rng.normal(size=(200, 4))
    G = nm.gram(X)
    for i in range(4):
        for j in range(4):
            assert G[i][j] == G[j][i]
    assert np.allclose(np.array(G), X.T @ X)


def test_sample_variance_known_answer() -> None:
    assert nm.sample_variance([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == pytest.approx(4.571428571428571)
    assert nm.sample_variance([1.0]) == 0.0


# ---------------------------------------------------------------- reward curve

CURVE = ((0, 0), (100_000, 20_000_000_000), (500_000, 80_000_000_000), (1_000_000, 120_000_000_000))


def test_curve_worked_example_from_reward_policy() -> None:
    """reward-policy.md worked example, cohort A: conservative 168400 -> 30_260_000_000."""
    assert nm.piecewise_linear(168_400, CURVE) == 30_260_000_000


def test_curve_endpoints_and_clamping() -> None:
    assert nm.piecewise_linear(0, CURVE) == 0
    assert nm.piecewise_linear(-5, CURVE) == 0          # clamped below
    assert nm.piecewise_linear(100_000, CURVE) == 20_000_000_000
    assert nm.piecewise_linear(1_000_000, CURVE) == 120_000_000_000
    assert nm.piecewise_linear(9_999_999, CURVE) == 120_000_000_000  # clamped above


def test_curve_is_monotonic_non_decreasing() -> None:
    prev = -1
    for x in range(0, 1_100_000, 977):
        v = nm.piecewise_linear(x, CURVE)
        assert v >= prev
        prev = v


def test_curve_is_pure_integer_arithmetic() -> None:
    for x in (1, 7, 99_999, 100_001, 499_999, 999_999):
        assert isinstance(nm.piecewise_linear(x, CURVE), int)
