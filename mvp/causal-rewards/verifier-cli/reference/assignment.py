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

from dataclasses import dataclass
from typing import Dict, List

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

    prf = {cid: cohort_prf(seed, experiment_id, cid) for cid in cohort_ids}

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
    else:
        raise ValueError("unknown design: %r" % (design,))

    # Canonical leaf order: cohort_id ascending by UTF-16 code unit (matches
    # canonical JSON key ordering used everywhere else).
    ordered = sorted(cohort_ids, key=lambda cid: cid.encode("utf-16-be"))
    return [CohortAssignment(cid, arm[cid], prf[cid]) for cid in ordered]


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
