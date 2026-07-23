"""Deterministic test fixtures — no RNG, no clock, fixed keys.

Secrets are fixed 32-byte patterns and signatures are RFC-8032 deterministic, so every
fixture batch is byte-stable and so are the roots derived from it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from crp_evidence import _ref, ed25519
from crp_evidence.ingest import recompute_header_hash

REPO_ROOT = Path(__file__).resolve().parents[2]
SPECS = REPO_ROOT / "specs"
TEST_VECTORS = REPO_ROOT / "test-vectors"

EXPERIMENT_ID = "env-sensors-pilot-001"

#: Fixed producer secrets (never used outside tests).
PRODUCER_A_SECRET = bytes([0x11]) * 32
PRODUCER_B_SECRET = bytes([0x22]) * 32


def b58(raw: bytes) -> str:
    return _ref.evidence.b58encode(raw)


def producer_pubkey(secret: bytes) -> str:
    return b58(ed25519.public_key_from_secret(secret))


def device_pubkeys(n: int) -> list[str]:
    """n distinct 32-byte device pubkeys as base58 (structural fixtures, not real keys)."""
    return [b58(bytes([0xA0 + i]) + bytes(31)) for i in range(n)]


def commitments(n: int, tag: int) -> list[str]:
    return [(bytes([tag, i]) + bytes(30)).hex() for i in range(n)]


def sign_batch(unsigned: Mapping[str, Any], secret: bytes) -> dict[str, Any]:
    """Attach a valid ``batch_signature`` computed over the recomputed header hash."""
    body = {k: v for k, v in unsigned.items() if k != "batch_signature"}
    header_hash = _ref.sha256(_ref.canonical_json_bytes(body))
    pub = ed25519.public_key_from_secret(secret)
    sig = ed25519.sign_deterministic(secret, header_hash)
    out = dict(body)
    out["batch_signature"] = {
        "algo": "ed25519",
        "header_hash_hex": header_hash.hex(),
        "signature_hex": sig.hex(),
        "signer_pubkey": b58(pub),
    }
    assert recompute_header_hash(out) == header_hash
    return out


def make_batch(
    *,
    epoch_index: str,
    cohort_id: str,
    secret: bytes = PRODUCER_A_SECRET,
    signers: Sequence[str] | None = None,
    obs: Sequence[str] | None = None,
    experiment_id: str = EXPERIMENT_ID,
    start: int = 1721001600,
    block_seconds: int = 3600,
) -> dict[str, Any]:
    from crp_evidence.roots import observations_root, signer_set_root

    signers = list(signers if signers is not None else device_pubkeys(3))
    obs = list(obs if obs is not None else commitments(4, 0x40))
    signer_root, _ = signer_set_root(signers)
    obs_root, _ = observations_root(obs)
    e = int(epoch_index)
    unsigned = {
        "aggregate_summary": {
            "accepted_count": str(len(obs)),
            "distinct_signers": str(len(signers)),
            "quality_score_micro_sum": str(len(obs) * 900_000),
            "rejected_count": "0",
        },
        "cohort_id": cohort_id,
        "epoch_index": str(e),
        "experiment_id": experiment_id,
        "observations_commitment": {
            "algo": "sha256",
            "leaf_count": str(len(obs)),
            "leaf_scheme": "sha256(0x00||'obs'||observation_commitment_be32)",
            "merkle_root_hex": obs_root,
        },
        "signer_set_commitment": {
            "algo": "sha256",
            "leaf_scheme": "sha256(0x00||'signer'||signer_pubkey_be32)",
            "merkle_root_hex": signer_root,
            "signer_count": str(len(signers)),
        },
        "spec_version": "1.1.0",
        "time_range": {
            "end": str(start + (e + 1) * block_seconds),
            "start": str(start + e * block_seconds),
        },
    }
    return sign_batch(unsigned, secret)


def example_manifest() -> dict[str, Any]:
    return json.loads((SPECS / "examples" / "manifest.example.json").read_bytes().decode("utf-8"))


def small_manifest(epoch_count: int = 2, cohort_count: int = 2) -> dict[str, Any]:
    """The example manifest narrowed to a tiny schedule so coverage tests stay readable."""
    m = example_manifest()
    m["estimand"]["time_block"]["block_count"] = str(epoch_count)
    m["estimand"]["cohort_definition"]["cohort_count"] = str(cohort_count)
    return m


COHORT_IDS = ("cohort-a", "cohort-b")


def participants(n_per_cohort: int = 2) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for ci, cohort in enumerate(COHORT_IDS):
        for i in range(n_per_cohort):
            out.append(
                {
                    "participant_id": b58(bytes([0xC0 + ci, i]) + bytes(30)),
                    "cohort_id": cohort,
                }
            )
    return out


def assignments() -> list[Any]:
    seed = bytes(32)
    return _ref.assignment.derive_assignment(
        seed, EXPERIMENT_ID, list(COHORT_IDS), "bernoulli", {"treat_fraction_ppm": "500000"}
    )


def full_batch_set() -> list[dict[str, Any]]:
    """2 epochs x 2 cohorts, plus a second producer corroborating one cell."""
    out: list[dict[str, Any]] = []
    for epoch in ("0", "1"):
        for ci, cohort in enumerate(COHORT_IDS):
            out.append(
                make_batch(
                    epoch_index=epoch,
                    cohort_id=cohort,
                    obs=commitments(4, 0x40 + ci + 2 * int(epoch)),
                )
            )
    # Independent corroboration of (epoch 0, cohort-a) by a DIFFERENT producer: admitted.
    out.append(
        make_batch(
            epoch_index="0",
            cohort_id=COHORT_IDS[0],
            secret=PRODUCER_B_SECRET,
            obs=commitments(4, 0x70),
            signers=device_pubkeys(2),
        )
    )
    return out
