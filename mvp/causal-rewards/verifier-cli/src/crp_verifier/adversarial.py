"""Independent rejection of the shared adversarial fixtures (``test-vectors/adversarial/``).

Each fixture describes a bad state a good verifier MUST reject. This module RE-DERIVES the
reject condition of every fixture from its raw inputs using the same ratified reference
encoder the bundle checks use — it never trusts the fixture's own ``expected`` block. It
returns a verdict so the CLI/tests can prove the verifier rejects each one.

Two enforcement scopes are distinguished, because they are genuinely different:

* ``BUNDLE``   — the offline bundle-recompute enforces this directly; a tampered *bundle*
                 makes ``crp-verify`` exit non-zero (seed reveal, evidence leaf/epoch order,
                 container digest, evidence↔result seam, substituted roots).
* ``ONCHAIN``  — a settlement / state-machine guard the *chain* enforces (evaluation binds
                 the current committed state; a claim nullifier is single-use). The bundle
                 carries no claims/chain-state, so the verifier confirms the reject condition
                 by recomputing it from the fixture inputs rather than from a bundle.

Either way, ``evaluate_fixture`` returns ``rejected=True`` for every adversarial fixture.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from . import _ref

BUNDLE = "BUNDLE"
ONCHAIN = "ONCHAIN"


@dataclass(frozen=True)
class Verdict:
    rejected: bool
    code: str
    scope: str
    detail: str


def _evidence_leaf_hash(batch: Mapping[str, Any]) -> str:
    cb = _ref.canonical_json_bytes(batch)
    return _ref.merkle.leaf_hash(_ref.merkle.DOMAIN_EVIDENCE, cb).hex()


def evaluate_fixture(fx: Mapping[str, Any]) -> Verdict:
    """Recompute a fixture's reject condition from first principles; return the verdict."""
    kind = str((fx.get("check") or {}).get("kind"))
    code = str(fx.get("rejection_code") or "REJECTED")
    inp = fx.get("inputs") or {}

    if kind == "seed_commitment_mismatch":
        revealed = bytes.fromhex(str(inp["revealed_seed_hex"]))
        frozen = str(inp["frozen_seed_commitment_hex"])
        recomputed = _ref.assignment.seed_commitment(revealed).hex()
        rejected = recomputed != frozen
        return Verdict(rejected, code, BUNDLE,
                       "seed_commitment(revealed)=%s %s frozen=%s"
                       % (recomputed, "!=" if rejected else "==", frozen))

    if kind == "duplicate_evidence_leaf":
        a = _evidence_leaf_hash(inp["batch_a"])
        b = _evidence_leaf_hash(inp["batch_b"])
        rejected = a == b  # identical batch collides on leaf_hash -> replay
        return Verdict(rejected, code, BUNDLE,
                       "leaf_hash(batch_a)=%s %s leaf_hash(batch_b)=%s"
                       % (a, "==" if rejected else "!=", b))

    if kind == "epoch_index_not_monotonic":
        prev = int(str(inp["previous_epoch_index"]))
        attempted = int(str(inp["attempted_epoch_index"]))
        rejected = attempted <= prev  # must extend the chain by exactly one
        return Verdict(rejected, code, BUNDLE,
                       "attempted_epoch_index=%d %s previous=%d"
                       % (attempted, "<=" if rejected else ">", prev))

    if kind == "container_digest_mismatch":
        frozen = str(inp["frozen_analysis_container_digest"])
        echoed = str(inp["echoed_analysis_container_digest"])
        rejected = frozen != echoed
        return Verdict(rejected, code, BUNDLE,
                       "frozen=%s %s echoed=%s" % (frozen, "!=" if rejected else "==", echoed))

    if kind == "stale_evaluation_state_mismatch":
        committed = str(inp["committed_cohort_root_hex"])
        referenced = str(inp["evaluation_referenced_cohort_root_hex"])
        rejected = referenced != committed
        return Verdict(rejected, code, ONCHAIN,
                       "evaluation referenced=%s %s committed=%s"
                       % (referenced, "!=" if rejected else "==", committed))

    if kind == "double_claim_nullifier_reuse":
        n1 = str(inp["first_claim"]["nullifier_hex"])
        n2 = str(inp["second_claim"]["nullifier_hex"])
        rejected = n1 == n2  # a re-used nullifier is a replayed claim
        return Verdict(rejected, code, ONCHAIN,
                       "first.nullifier=%s %s second.nullifier=%s"
                       % (n1, "==" if rejected else "!=", n2))

    raise ValueError("unknown adversarial fixture kind: %r" % kind)
