"""Deterministic seed -> cohort-assignment derivation (reference).

Freeze-before-reveal (invariant 1): the manifest freezes seed_commitment(seed).
The seed itself is revealed later. Verification is therefore two distinct steps:

  1. commitment check:  seed_commitment(revealed_seed) == frozen_commitment
  2. derivation:        derive_assignment(revealed_seed, experiment_id, cohorts,
                                          design) -> per-cohort arm

Both steps are pure functions of committed/revealed inputs. No wall-clock, no
unseeded RNG, no float.

Proposed constants (subject to protocol-architect ratification):

  SEED_LEN            = 32 bytes (the assignment seed is a 32-byte value)
  SEED_COMMIT_DOMAIN  = b"CRP-seed-commit-v1"
  ASSIGN_PRF_DOMAIN   = b"CRP-assign-v1"

PRF (pseudo-random function) for a cohort, unambiguously length-prefixed so no
two (experiment_id, cohort_id) pairs can collide by concatenation:

  msg = ASSIGN_PRF_DOMAIN
      || seed (32 bytes)
      || u32be(len(experiment_id_utf8)) || experiment_id_utf8
      || u32be(len(cohort_id_utf8))     || cohort_id_utf8
  prf_digest = SHA-256(msg)
  prf_u64    = int.from_bytes(prf_digest[:8], "big")   # first 8 bytes, big-endian

Designs:
  * bernoulli  : params {"treat_fraction_ppm": "<int string>"}; cohort is
                 treatment iff (prf_u64 % 1_000_000) < treat_fraction_ppm.
                 Independent per cohort; expected but not exact balance.
  * fixed_count: params {"treatment_count": "<int string>"}; cohorts are sorted
                 by (prf_u64, cohort_id) ascending and the first k are
                 treatment. Exact balance; tie-break by cohort_id.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from canonical import canonical_json_bytes, sha256

__all__ = [
    "SEED_LEN",
    "SEED_COMMIT_DOMAIN",
    "ASSIGN_PRF_DOMAIN",
    "ARM_TREATMENT",
    "ARM_CONTROL",
    "seed_commitment",
    "cohort_prf",
    "derive_assignment",
    "assignment_leaf_object",
    "assignment_leaf_bytes",
    "CohortAssignment",
    "parse_composite_cohort_id",
    "round_half_even_div",
    "switchback_phase",
]

SEED_LEN = 32
SEED_COMMIT_DOMAIN = b"CRP-seed-commit-v1"
ASSIGN_PRF_DOMAIN = b"CRP-assign-v1"

ARM_TREATMENT = "treatment"
ARM_CONTROL = "control"

_PPM = 1_000_000


def _u32be(n: int) -> bytes:
    if n < 0 or n > 0xFFFFFFFF:
        raise ValueError("length out of u32 range: %d" % n)
    return n.to_bytes(4, "big")


def seed_commitment(seed: bytes) -> bytes:
    if len(seed) != SEED_LEN:
        raise ValueError("seed must be exactly %d bytes, got %d" % (SEED_LEN, len(seed)))
    return sha256(SEED_COMMIT_DOMAIN + seed)


def cohort_prf(seed: bytes, experiment_id: str, cohort_id: str) -> int:
    if len(seed) != SEED_LEN:
        raise ValueError("seed must be exactly %d bytes, got %d" % (SEED_LEN, len(seed)))
    exp = experiment_id.encode("utf-8")
    coh = cohort_id.encode("utf-8")
    msg = (
        ASSIGN_PRF_DOMAIN
        + seed
        + _u32be(len(exp))
        + exp
        + _u32be(len(coh))
        + coh
    )
    digest = sha256(msg)
    return int.from_bytes(digest[:8], "big")


_INDEX_RE = re.compile(r"^(0|[1-9][0-9]*)$")


def parse_composite_cohort_id(cohort_id: str) -> Tuple[str, int]:
    """Parse a switchback/matched_cluster composite id ``group "|" index`` (§7.4 grammar).

    The single ``|`` (U+007C) MUST appear EXACTLY once; ``group`` is one or more
    non-``|`` characters; ``index`` is a canonical unsigned integer string
    (``^(0|[1-9][0-9]*)$`` — no leading zeros). Any violation is a hard error,
    rejected before derivation. The FULL composite id is still what the leaf
    carries and what leaves sort by (§6.2/§7.5); this parse only reads structure
    OUT of the id for the derivation.
    """
    parts = cohort_id.split("|")
    if len(parts) != 2:
        raise ValueError(
            "composite cohort_id must contain EXACTLY one '|': %r" % (cohort_id,)
        )
    group, index = parts
    if group == "":
        raise ValueError("composite cohort_id has empty group: %r" % (cohort_id,))
    if not _INDEX_RE.match(index):
        raise ValueError(
            "composite cohort_id index is not a canonical uint string: %r" % (cohort_id,)
        )
    return group, int(index)


def round_half_even_div(numerator: int, denominator: int) -> int:
    """Integer round-half-to-even of ``numerator / denominator`` (§2.4 sole rounding rule).

    ``q = N // D``, ``r = N mod D``: take ``q`` if ``2r < D``, ``q+1`` if
    ``2r > D``, and on the exact half ``2r == D`` take ``q`` when ``q`` is even
    else ``q+1``. Denominator MUST be positive.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    q, r = divmod(numerator, denominator)
    two_r = 2 * r
    if two_r < denominator:
        return q
    if two_r > denominator:
        return q + 1
    return q if (q % 2 == 0) else q + 1


def switchback_phase(seed: bytes, experiment_id: str, group: str) -> int:
    """Per-geo-cohort switchback phase bit = low bit of the §7.3 PRF keyed on ``group``."""
    return cohort_prf(seed, experiment_id, group) & 1


@dataclass(frozen=True)
class CohortAssignment:
    cohort_id: str
    arm: str
    prf_u64: int


def derive_assignment(
    seed: bytes,
    experiment_id: str,
    cohort_ids: List[str],
    design: str,
    params: Dict[str, str],
) -> List[CohortAssignment]:
    """Return assignments in canonical (cohort_id-ascending) order.

    cohort_ids may be supplied in any order; the result is deterministic and
    independent of input order.
    """
    if len(set(cohort_ids)) != len(cohort_ids):
        raise ValueError("duplicate cohort_id in cohort set")

    # Full-composite-id PRF for every cohort (used by fixed_count and
    # matched_cluster ranking, and by bernoulli). `prf_used` is what each
    # cohort's arm decision actually consumed and what the leaf table reports.
    prf = {cid: cohort_prf(seed, experiment_id, cid) for cid in cohort_ids}
    prf_used = dict(prf)

    if design == "bernoulli":
        ppm = int(params["treat_fraction_ppm"])
        if not (0 <= ppm <= _PPM):
            raise ValueError("treat_fraction_ppm out of range: %d" % ppm)
        arm = {cid: (ARM_TREATMENT if (prf[cid] % _PPM) < ppm else ARM_CONTROL) for cid in cohort_ids}
    elif design == "fixed_count":
        k = int(params["treatment_count"])
        if not (0 <= k <= len(cohort_ids)):
            raise ValueError("treatment_count out of range: %d" % k)
        ranked = sorted(cohort_ids, key=lambda cid: (prf[cid], cid))
        treated = set(ranked[:k])
        arm = {cid: (ARM_TREATMENT if cid in treated else ARM_CONTROL) for cid in cohort_ids}
    elif design == "switchback":
        # §7.4 switchback: per-geo phase bit + parity alternation across periods.
        # `treated_fraction_micro` MUST be "500000" (structurally 50/50); the
        # derivation itself does NOT read it — it only asserts the manifest value.
        tf = params["treated_fraction_micro"]
        if tf != "500000":
            raise ValueError(
                "switchback requires treated_fraction_micro == '500000', got %r" % (tf,)
            )
        phase: Dict[str, int] = {}
        arm = {}
        for cid in cohort_ids:
            group, index = parse_composite_cohort_id(cid)
            if group not in phase:
                phase[group] = switchback_phase(seed, experiment_id, group)
            prf_used[cid] = cohort_prf(seed, experiment_id, group)  # the group PRF
            arm[cid] = (
                ARM_TREATMENT if ((index + phase[group]) % 2 == 1) else ARM_CONTROL
            )
    elif design == "matched_cluster":
        # §7.4 matched_cluster: within each frozen stratum, k_s = round_he(
        # treated_fraction_micro * m_s / 1e6) treated, ranked by (full-id PRF,
        # member_index). Reuses the §7.3 PRF keyed on the FULL composite id.
        frac = int(params["treated_fraction_micro"])
        if not (0 <= frac <= _PPM):
            raise ValueError("treated_fraction_micro out of range: %d" % frac)
        strata: Dict[str, List[Tuple[int, int, str]]] = {}
        for cid in cohort_ids:
            group, index = parse_composite_cohort_id(cid)
            # rank tuple: (prf_u64 of FULL id, member_index) — index breaks prf ties
            strata.setdefault(group, []).append((prf[cid], index, cid))
        arm = {}
        for group, members in strata.items():
            m_s = len(members)
            k_s = round_half_even_div(frac * m_s, _PPM)
            k_s = max(0, min(k_s, m_s))  # clamp to [0, m_s]
            ranked = sorted(members, key=lambda t: (t[0], t[1]))
            for pos, (_prf, _idx, cid) in enumerate(ranked):
                arm[cid] = ARM_TREATMENT if pos < k_s else ARM_CONTROL
    else:
        raise ValueError("unknown design: %r" % (design,))

    # Canonical leaf order: FULL composite cohort_id ascending by UTF-16 code
    # unit (matches canonical JSON key ordering; the grammar never changes the
    # leaf form or leaf ordering — §7.4).
    ordered = sorted(cohort_ids, key=lambda cid: cid.encode("utf-16-be"))
    return [CohortAssignment(cid, arm[cid], prf_used[cid]) for cid in ordered]


def assignment_leaf_object(a: CohortAssignment) -> dict:
    """Canonical leaf object for the assignment Merkle tree.

    Only the committed decision is in the leaf: cohort_id + arm. The prf value
    is an auditable intermediate, published in the assignment table, but is a
    deterministic function of (seed, experiment_id, cohort_id) so it is not part
    of the leaf preimage.
    """
    return {"arm": a.arm, "cohort_id": a.cohort_id}


def assignment_leaf_bytes(a: CohortAssignment) -> bytes:
    return canonical_json_bytes(assignment_leaf_object(a))
