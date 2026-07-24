"""Bit-reproducible numeric primitives (CLAUDE.md invariant 2).

Every artifact-producing arithmetic path in this engine goes through this module. The design
rule is simple:

    A committed number must be identical on every IEEE-754 machine, under any BLAS,
    at any thread count.

Elementwise IEEE-754 ``+ - * /`` are exactly specified and therefore already reproducible. What
is *not* reproducible is a **reduction**: ``numpy.sum`` / ``numpy.dot`` / ``@`` may pairwise-
chunk, vectorize or thread the accumulation, and the chunking depends on the BLAS build, the
CPU's SIMD width and the thread count. So:

* **No** ``np.sum``, ``np.dot``, ``np.mean``, ``@`` or ``np.linalg.*`` appears on any path that
  reaches a committed number.
* Every reduction uses :func:`fsum` (``math.fsum``), which is *exactly rounded*: it computes the
  infinitely-precise sum and rounds once. An exactly-rounded sum is by definition independent of
  summation order, so it is identical everywhere.
* The (tiny, K x K) linear solve is a hand-written Gaussian elimination with partial pivoting —
  only ``+ - * /`` in a fixed order, no LAPACK.
* The final float -> committed-integer step (:func:`quantize`) converts through
  :class:`fractions.Fraction`, which is *exact* for a binary float, and rounds half-to-even
  (``serialization.md`` §2.4, the single rounding rule). No ``round()``, no string formatting,
  no locale.

Elementwise numpy vector ops (``a * b``, ``a - b``) are kept — they are IEEE-deterministic and
BLAS-free — but the accumulation is always ours.
"""

from __future__ import annotations

import math
from fractions import Fraction
from typing import Iterable, Sequence

import numpy as np

from crp_engine.reference import round_half_even_div

__all__ = [
    "fsum",
    "vsum",
    "vmean",
    "dot",
    "matvec",
    "gram",
    "xty",
    "matmul",
    "solve",
    "inverse",
    "round_half_even_div",
    "quantize",
    "dequantize",
    "piecewise_linear",
    "sample_variance",
]


# --------------------------------------------------------------------------------------
# Exactly-rounded reductions
# --------------------------------------------------------------------------------------

def fsum(values: Iterable[float]) -> float:
    """Exactly-rounded sum. Order-independent, BLAS-independent, thread-independent."""
    return math.fsum(values)


def vsum(a: np.ndarray) -> float:
    """Exactly-rounded sum of a 1-D float array (replacement for ``np.sum``)."""
    return math.fsum(np.asarray(a, dtype=np.float64).ravel().tolist())


def vmean(a: np.ndarray) -> float:
    """Exactly-rounded mean (replacement for ``np.mean``). Empty input is an error."""
    arr = np.asarray(a, dtype=np.float64).ravel()
    n = arr.size
    if n == 0:
        raise ValueError("mean of an empty array")
    return math.fsum(arr.tolist()) / n


def dot(a: np.ndarray, b: np.ndarray) -> float:
    """Exactly-rounded inner product (replacement for ``np.dot`` on 1-D input).

    The elementwise product is IEEE-exact per element; only the accumulation needs care.
    """
    x = np.asarray(a, dtype=np.float64).ravel()
    y = np.asarray(b, dtype=np.float64).ravel()
    if x.size != y.size:
        raise ValueError("dot: length mismatch %d vs %d" % (x.size, y.size))
    return math.fsum((x * y).tolist())


def matvec(X: np.ndarray, beta: Sequence[float]) -> np.ndarray:
    """``X @ beta`` for an (n, k) design matrix, BLAS-free and order-fixed.

    Accumulates column by column in ascending column order using elementwise numpy adds. Every
    operation is a specified IEEE-754 op applied in a fixed sequence, so the result is
    bit-identical everywhere (it is not *exactly rounded*, but it is *reproducible*, which is
    what the invariant requires; residuals are then reduced with :func:`fsum`).
    """
    Xf = np.asarray(X, dtype=np.float64)
    n, k = Xf.shape
    if len(beta) != k:
        raise ValueError("matvec: beta length %d != k %d" % (len(beta), k))
    out = np.zeros(n, dtype=np.float64)
    for j in range(k):
        out = out + Xf[:, j] * float(beta[j])
    return out


def gram(X: np.ndarray) -> list[list[float]]:
    """``X.T @ X`` computed with exactly-rounded column inner products. Symmetric by construction."""
    Xf = np.asarray(X, dtype=np.float64)
    k = Xf.shape[1]
    G = [[0.0] * k for _ in range(k)]
    for i in range(k):
        for j in range(i, k):
            v = math.fsum((Xf[:, i] * Xf[:, j]).tolist())
            G[i][j] = v
            G[j][i] = v
    return G


def xty(X: np.ndarray, y: np.ndarray) -> list[float]:
    """``X.T @ y`` with exactly-rounded inner products."""
    Xf = np.asarray(X, dtype=np.float64)
    yf = np.asarray(y, dtype=np.float64).ravel()
    return [math.fsum((Xf[:, j] * yf).tolist()) for j in range(Xf.shape[1])]


def matmul(A: Sequence[Sequence[float]], B: Sequence[Sequence[float]]) -> list[list[float]]:
    """Small dense matrix product with exactly-rounded accumulation (k is tiny: <= ~64)."""
    n = len(A)
    m = len(B[0]) if B else 0
    inner = len(B)
    if any(len(row) != inner for row in A):
        raise ValueError("matmul: shape mismatch")
    return [
        [math.fsum(A[i][t] * B[t][j] for t in range(inner)) for j in range(m)]
        for i in range(n)
    ]


# --------------------------------------------------------------------------------------
# Tiny dense linear algebra (no LAPACK)
# --------------------------------------------------------------------------------------

class SingularMatrixError(ValueError):
    """Raised when the design matrix is rank-deficient (collinear regressors)."""


def solve(A: Sequence[Sequence[float]], b: Sequence[float]) -> list[float]:
    """Solve ``A x = b`` by Gaussian elimination with partial pivoting.

    Only ``+ - * /`` in a fixed order — no LAPACK, no BLAS, hence bit-identical on any
    IEEE-754 platform. ``A`` is K x K with K small (the design matrix rank).
    """
    n = len(A)
    M = [[float(A[i][j]) for j in range(n)] + [float(b[i])] for i in range(n)]
    for col in range(n):
        # Partial pivoting: largest |value| in the column, lowest row index breaking ties.
        piv = col
        best = abs(M[col][col])
        for r in range(col + 1, n):
            v = abs(M[r][col])
            if v > best:
                best = v
                piv = r
        if best == 0.0:
            raise SingularMatrixError(
                "singular design matrix at column %d (collinear regressors)" % col
            )
        if piv != col:
            M[col], M[piv] = M[piv], M[col]
        pivot = M[col][col]
        for r in range(col + 1, n):
            f = M[r][col] / pivot
            if f == 0.0:
                continue
            for c in range(col, n + 1):
                M[r][c] = M[r][c] - f * M[col][c]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        acc = M[i][n] - math.fsum(M[i][j] * x[j] for j in range(i + 1, n))
        x[i] = acc / M[i][i]
    return x


def inverse(A: Sequence[Sequence[float]]) -> list[list[float]]:
    """Inverse of a small dense matrix via :func:`solve` against unit vectors (column-wise)."""
    n = len(A)
    cols = []
    for j in range(n):
        e = [1.0 if i == j else 0.0 for i in range(n)]
        cols.append(solve(A, e))
    return [[cols[j][i] for j in range(n)] for i in range(n)]


def sample_variance(values: Sequence[float]) -> float:
    """Unbiased (n-1) sample variance with exactly-rounded reductions. n<2 -> 0.0."""
    v = [float(x) for x in values]
    n = len(v)
    if n < 2:
        return 0.0
    mean = math.fsum(v) / n
    return math.fsum((x - mean) * (x - mean) for x in v) / (n - 1)


# --------------------------------------------------------------------------------------
# Float -> committed integer (the quantization boundary)
# --------------------------------------------------------------------------------------

def quantize(value: float, scale_exp: int) -> int:
    """Convert a float to the committed integer at ``10**scale_exp`` resolution.

    ``scale_exp`` is the ``positive_improvement_transform.effect_scale`` exponent
    (``"-6"`` -> 1e-6 resolution -> integer = value * 1e6). Conversion goes through an EXACT
    rational (``Fraction`` of a binary float is exact) and rounds half-to-even
    (``serialization.md`` §2.4). Deterministic, locale-free, and independent of ``repr``.

    Round-half-to-even is sign-symmetric, so we round the magnitude and reapply the sign:
    -2.5 -> -2, -3.5 -> -4 (matching banker's rounding).
    """
    if not math.isfinite(value):
        raise ValueError("cannot quantize a non-finite value: %r" % (value,))
    f = Fraction(value) * (Fraction(10) ** (-scale_exp))
    neg = f < 0
    if neg:
        f = -f
    q = round_half_even_div(f.numerator, f.denominator)
    return -q if neg else q


def dequantize(value_s: int, scale_exp: int) -> float:
    """Inverse of :func:`quantize`, for human-readable / diagnostic use only (never committed)."""
    return float(Fraction(value_s) * (Fraction(10) ** scale_exp))


# --------------------------------------------------------------------------------------
# Reward curve (reward-policy.md Stage 1 step 5) — pure integer arithmetic
# --------------------------------------------------------------------------------------

def piecewise_linear(x: int, breakpoints: Sequence[tuple[int, int]]) -> int:
    """Evaluate the frozen monotonic piecewise-linear reward curve at integer ``x``.

    ``alloc = y0 + round_he((y1 - y0) * (x - x0) / (x1 - x0))`` inside a segment; clamped to
    ``y_first`` / ``y_last`` outside the breakpoint range. Integer arithmetic only — the curve
    never touches a float (``reward-policy.md`` Stage 1 step 5).
    """
    if len(breakpoints) < 2:
        raise ValueError("reward curve needs at least 2 breakpoints")
    if x <= breakpoints[0][0]:
        return breakpoints[0][1]
    if x >= breakpoints[-1][0]:
        return breakpoints[-1][1]
    for (x0, y0), (x1, y1) in zip(breakpoints, breakpoints[1:]):
        if x0 <= x <= x1:
            if x1 == x0:
                return y0
            dy = y1 - y0
            num = dy * (x - x0)
            den = x1 - x0
            neg = num < 0
            step = round_half_even_div(-num if neg else num, den)
            return y0 + (-step if neg else step)
    raise AssertionError("unreachable: x within breakpoint range but no segment matched")
