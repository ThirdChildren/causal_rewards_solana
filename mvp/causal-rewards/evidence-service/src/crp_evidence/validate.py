"""Structural validation of a signed evidence batch against ``specs/evidence.schema.json``.

Implemented as an explicit, dependency-free validator rather than a generic JSON-Schema
engine because:

1. The schema is ``additionalProperties: false`` everywhere and frozen — an explicit walk is
   auditable line-by-line against the spec, which a generic engine's error strings are not.
2. Rejections must carry the STABLE codes in ``errors.RejectionCode`` (the wire contract);
   generic validators emit their own message shapes.
3. The service must run in a container with no extra deps on the artifact-producing path.

The validator is nevertheless kept honest by ``tests/test_schema_parity.py``, which loads
``specs/evidence.schema.json`` and asserts that the property names / required lists / const
values / regexes this module enforces are exactly the ones in the frozen schema. If the spec
changes, that test fails before any behavior silently diverges.

Data minimization (invariant 5) is enforced structurally: ``additionalProperties: false``
means a producer cannot smuggle raw telemetry or coordinates into an anchored artifact — an
unknown key is a hard rejection, not a warning.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from .errors import EvidenceRejected, RejectionCode

__all__ = [
    "SUPPORTED_SPEC_VERSIONS",
    "RE_UINT",
    "RE_UINT_POS",
    "RE_HEX64",
    "RE_HEX128",
    "RE_BASE58",
    "RE_EXPERIMENT_ID",
    "RE_COHORT_ID",
    "SIGNER_LEAF_SCHEME",
    "OBS_LEAF_SCHEME",
    "validate_batch",
    "validate_observation_leaf",
]

# Wire/hash contract versions this service accepts. v1.1.0 is additive and hash-compatible
# with 1.0.0 (no §6.5 byte changes), so both are admitted and both hash identically.
SUPPORTED_SPEC_VERSIONS = frozenset({"1.0.0", "1.1.0"})

RE_UINT = re.compile(r"^(0|[1-9][0-9]*)$")
RE_UINT_POS = re.compile(r"^[1-9][0-9]*$")
RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")
RE_HEX128 = re.compile(r"^[0-9a-f]{128}$")
RE_BASE58 = re.compile(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$")
RE_EXPERIMENT_ID = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
RE_COHORT_ID = re.compile(r"^[a-z0-9_-]{1,64}$")
RE_SPEC_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

SIGNER_LEAF_SCHEME = "sha256(0x00||'signer'||signer_pubkey_be32)"
OBS_LEAF_SCHEME = "sha256(0x00||'obs'||observation_commitment_be32)"

_BATCH_REQUIRED = (
    "spec_version",
    "experiment_id",
    "epoch_index",
    "cohort_id",
    "time_range",
    "signer_set_commitment",
    "observations_commitment",
    "aggregate_summary",
    "batch_signature",
)
_BATCH_OPTIONAL: tuple[str, ...] = ()

_TIME_RANGE_REQUIRED = ("start", "end")
_SIGNER_COMMIT_REQUIRED = ("algo", "merkle_root_hex", "signer_count", "leaf_scheme")
_OBS_COMMIT_REQUIRED = ("algo", "merkle_root_hex", "leaf_count", "leaf_scheme")
_AGG_REQUIRED = ("accepted_count", "rejected_count", "distinct_signers")
_AGG_OPTIONAL = ("quality_score_micro_sum",)
_SIG_REQUIRED = ("algo", "signer_pubkey", "header_hash_hex", "signature_hex")

_OBS_LEAF_REQUIRED = (
    "signer_pubkey",
    "cohort_id",
    "time_block_index",
    "payload_commitment_hex",
    "signature_hex",
)


def _reject(code: str, msg: str, **detail: Any) -> None:
    raise EvidenceRejected(code, msg, **detail)


def _obj(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _reject(RejectionCode.SCHEMA_INVALID, "%s must be an object" % path, path=path)
    return value


def _keys(
    value: Mapping[str, Any], path: str, required: tuple[str, ...], optional: tuple[str, ...] = ()
) -> None:
    allowed = set(required) | set(optional)
    missing = [k for k in required if k not in value]
    if missing:
        _reject(
            RejectionCode.SCHEMA_INVALID,
            "%s missing required propert%s: %s"
            % (path, "y" if len(missing) == 1 else "ies", ", ".join(missing)),
            path=path,
            missing=missing,
        )
    extra = sorted(set(value) - allowed)
    if extra:
        # additionalProperties:false — also the data-minimization guard (invariant 5).
        _reject(
            RejectionCode.DATA_MINIMIZATION_VIOLATION,
            "%s has forbidden additional propert%s: %s (the anchored batch schema is closed; "
            "raw telemetry/coordinates have no property to hold them)"
            % (path, "y" if len(extra) == 1 else "ies", ", ".join(extra)),
            path=path,
            extra=extra,
        )


def _str(value: Mapping[str, Any], key: str, path: str, pattern: re.Pattern[str], code: str) -> str:
    v = value[key]
    if not isinstance(v, str):
        _reject(RejectionCode.SCHEMA_INVALID, "%s.%s must be a string" % (path, key), path=path)
    if not pattern.match(v):
        _reject(code, "%s.%s does not match %s: %r" % (path, key, pattern.pattern, v), path=path)
    return v  # type: ignore[return-value]


def _const(value: Mapping[str, Any], key: str, path: str, expected: str, code: str) -> None:
    if value[key] != expected:
        _reject(
            code,
            "%s.%s must be %r, got %r" % (path, key, expected, value[key]),
            path=path,
            expected=expected,
            actual=value[key],
        )


def validate_batch(batch: Any, *, expected_experiment_id: str | None = None) -> Mapping[str, Any]:
    """Validate a signed evidence batch header. Raises ``EvidenceRejected`` on any violation.

    Structural + semantic checks only. Header-hash recomputation and signature verification
    live in ``ingest.py`` (they need the canonical encoder and a key); the §6.5 32-byte
    base58 length pin lives in ``roots.py`` / ``ingest.py`` via the reference decoder.
    """
    b = _obj(batch, "batch")
    _keys(b, "batch", _BATCH_REQUIRED, _BATCH_OPTIONAL)

    spec_version = _str(b, "spec_version", "batch", RE_SPEC_VERSION, RejectionCode.SCHEMA_INVALID)
    if spec_version not in SUPPORTED_SPEC_VERSIONS:
        _reject(
            RejectionCode.UNSUPPORTED_SPEC_VERSION,
            "spec_version %r is not supported (accepted: %s)"
            % (spec_version, ", ".join(sorted(SUPPORTED_SPEC_VERSIONS))),
            spec_version=spec_version,
        )

    experiment_id = _str(
        b, "experiment_id", "batch", RE_EXPERIMENT_ID, RejectionCode.SCHEMA_INVALID
    )
    if expected_experiment_id is not None and experiment_id != expected_experiment_id:
        _reject(
            RejectionCode.EXPERIMENT_ID_MISMATCH,
            "batch.experiment_id %r != frozen manifest experiment_id %r"
            % (experiment_id, expected_experiment_id),
            actual=experiment_id,
            expected=expected_experiment_id,
        )

    _str(b, "epoch_index", "batch", RE_UINT, RejectionCode.NON_CANONICAL_INTEGER_STRING)
    _str(b, "cohort_id", "batch", RE_COHORT_ID, RejectionCode.SCHEMA_INVALID)

    tr = _obj(b["time_range"], "batch.time_range")
    _keys(tr, "batch.time_range", _TIME_RANGE_REQUIRED)
    start = _str(
        tr, "start", "batch.time_range", RE_UINT, RejectionCode.NON_CANONICAL_INTEGER_STRING
    )
    end = _str(
        tr, "end", "batch.time_range", RE_UINT_POS, RejectionCode.NON_CANONICAL_INTEGER_STRING
    )
    if int(start) >= int(end):
        _reject(
            RejectionCode.TIME_RANGE_INVALID,
            "time_range must be half-open with start < end; got [%s, %s)" % (start, end),
            start=start,
            end=end,
        )

    ssc = _obj(b["signer_set_commitment"], "batch.signer_set_commitment")
    _keys(ssc, "batch.signer_set_commitment", _SIGNER_COMMIT_REQUIRED)
    _const(ssc, "algo", "batch.signer_set_commitment", "sha256", RejectionCode.SCHEMA_INVALID)
    _str(ssc, "merkle_root_hex", "batch.signer_set_commitment", RE_HEX64, RejectionCode.SCHEMA_INVALID)
    signer_count = _str(
        ssc,
        "signer_count",
        "batch.signer_set_commitment",
        RE_UINT_POS,
        RejectionCode.NON_CANONICAL_INTEGER_STRING,
    )
    _const(
        ssc,
        "leaf_scheme",
        "batch.signer_set_commitment",
        SIGNER_LEAF_SCHEME,
        RejectionCode.SCHEMA_INVALID,
    )

    oc = _obj(b["observations_commitment"], "batch.observations_commitment")
    _keys(oc, "batch.observations_commitment", _OBS_COMMIT_REQUIRED)
    _const(oc, "algo", "batch.observations_commitment", "sha256", RejectionCode.SCHEMA_INVALID)
    _str(
        oc, "merkle_root_hex", "batch.observations_commitment", RE_HEX64, RejectionCode.SCHEMA_INVALID
    )
    _str(
        oc,
        "leaf_count",
        "batch.observations_commitment",
        RE_UINT_POS,
        RejectionCode.NON_CANONICAL_INTEGER_STRING,
    )
    _const(
        oc,
        "leaf_scheme",
        "batch.observations_commitment",
        OBS_LEAF_SCHEME,
        RejectionCode.SCHEMA_INVALID,
    )

    agg = _obj(b["aggregate_summary"], "batch.aggregate_summary")
    _keys(agg, "batch.aggregate_summary", _AGG_REQUIRED, _AGG_OPTIONAL)
    for k in _AGG_REQUIRED:
        _str(agg, k, "batch.aggregate_summary", RE_UINT, RejectionCode.NON_CANONICAL_INTEGER_STRING)
    if "quality_score_micro_sum" in agg:
        _str(
            agg,
            "quality_score_micro_sum",
            "batch.aggregate_summary",
            RE_UINT,
            RejectionCode.NON_CANONICAL_INTEGER_STRING,
        )
    # Schema-documented semantic bound: distinct_signers <= signer_count.
    if int(agg["distinct_signers"]) > int(signer_count):
        _reject(
            RejectionCode.AGGREGATE_SUMMARY_INCONSISTENT,
            "aggregate_summary.distinct_signers (%s) > signer_set_commitment.signer_count (%s)"
            % (agg["distinct_signers"], signer_count),
            distinct_signers=agg["distinct_signers"],
            signer_count=signer_count,
        )

    sig = _obj(b["batch_signature"], "batch.batch_signature")
    _keys(sig, "batch.batch_signature", _SIG_REQUIRED)
    _const(
        sig, "algo", "batch.batch_signature", "ed25519", RejectionCode.UNSUPPORTED_SIGNATURE_ALGO
    )
    _str(sig, "signer_pubkey", "batch.batch_signature", RE_BASE58, RejectionCode.SIGNER_PUBKEY_INVALID_BASE58)
    _str(sig, "header_hash_hex", "batch.batch_signature", RE_HEX64, RejectionCode.SCHEMA_INVALID)
    _str(sig, "signature_hex", "batch.batch_signature", RE_HEX128, RejectionCode.SCHEMA_INVALID)

    return b


def validate_observation_leaf(leaf: Any) -> Mapping[str, Any]:
    """Validate an OFF-CHAIN ``$defs.observation_leaf`` record (never anchored on-chain)."""
    o = _obj(leaf, "observation_leaf")
    _keys(o, "observation_leaf", _OBS_LEAF_REQUIRED)
    _str(
        o,
        "signer_pubkey",
        "observation_leaf",
        RE_BASE58,
        RejectionCode.SIGNER_PUBKEY_INVALID_BASE58,
    )
    _str(o, "cohort_id", "observation_leaf", RE_COHORT_ID, RejectionCode.SCHEMA_INVALID)
    _str(
        o,
        "time_block_index",
        "observation_leaf",
        RE_UINT,
        RejectionCode.NON_CANONICAL_INTEGER_STRING,
    )
    _str(o, "payload_commitment_hex", "observation_leaf", RE_HEX64, RejectionCode.SCHEMA_INVALID)
    _str(o, "signature_hex", "observation_leaf", RE_HEX128, RejectionCode.SCHEMA_INVALID)
    return o
