"""Anti-drift: the hand-written validator must match ``specs/evidence.schema.json`` exactly.

``specs/`` wins over any implementation (CLAUDE.md). This test reads the frozen schema and
asserts that every property name, required list, ``const`` and ``pattern`` the validator
enforces is the one in the spec. If protocol-architect edits the schema, this fails BEFORE
any behavior silently diverges — which is the whole reason a hand-written validator is
acceptable here.

It also pins the parity between this service and the reference encoder / reference evidence
module (no second implementation of any byte rule).
"""

from __future__ import annotations

import json

from fixtures import SPECS

from crp_evidence import _ref, validate


def _schema() -> dict:
    return json.loads((SPECS / "evidence.schema.json").read_bytes().decode("utf-8"))


def test_batch_required_and_property_names_match_spec() -> None:
    s = _schema()
    assert tuple(s["required"]) == validate._BATCH_REQUIRED
    assert set(s["properties"]) == set(validate._BATCH_REQUIRED) | set(validate._BATCH_OPTIONAL)
    assert s["additionalProperties"] is False


def test_nested_object_required_lists_match_spec() -> None:
    p = _schema()["properties"]
    assert tuple(p["time_range"]["required"]) == validate._TIME_RANGE_REQUIRED
    assert tuple(p["signer_set_commitment"]["required"]) == validate._SIGNER_COMMIT_REQUIRED
    assert tuple(p["observations_commitment"]["required"]) == validate._OBS_COMMIT_REQUIRED
    assert tuple(p["aggregate_summary"]["required"]) == validate._AGG_REQUIRED
    assert tuple(p["batch_signature"]["required"]) == validate._SIG_REQUIRED
    assert set(p["aggregate_summary"]["properties"]) == set(validate._AGG_REQUIRED) | set(
        validate._AGG_OPTIONAL
    )


def test_patterns_match_spec() -> None:
    p = _schema()["properties"]
    assert p["experiment_id"]["pattern"] == validate.RE_EXPERIMENT_ID.pattern
    assert p["cohort_id"]["pattern"] == validate.RE_COHORT_ID.pattern
    assert p["epoch_index"]["pattern"] == validate.RE_UINT.pattern
    assert p["time_range"]["properties"]["start"]["pattern"] == validate.RE_UINT.pattern
    assert p["time_range"]["properties"]["end"]["pattern"] == validate.RE_UINT_POS.pattern
    assert (
        p["signer_set_commitment"]["properties"]["merkle_root_hex"]["pattern"]
        == validate.RE_HEX64.pattern
    )
    assert (
        p["signer_set_commitment"]["properties"]["signer_count"]["pattern"]
        == validate.RE_UINT_POS.pattern
    )
    assert (
        p["observations_commitment"]["properties"]["leaf_count"]["pattern"]
        == validate.RE_UINT_POS.pattern
    )
    sig = p["batch_signature"]["properties"]
    assert sig["signer_pubkey"]["pattern"] == validate.RE_BASE58.pattern
    assert sig["header_hash_hex"]["pattern"] == validate.RE_HEX64.pattern
    assert sig["signature_hex"]["pattern"] == validate.RE_HEX128.pattern


def test_leaf_scheme_consts_match_spec() -> None:
    p = _schema()["properties"]
    assert (
        p["signer_set_commitment"]["properties"]["leaf_scheme"]["const"]
        == validate.SIGNER_LEAF_SCHEME
    )
    assert (
        p["observations_commitment"]["properties"]["leaf_scheme"]["const"]
        == validate.OBS_LEAF_SCHEME
    )
    assert p["batch_signature"]["properties"]["algo"]["const"] == "ed25519"


def test_observation_leaf_defs_match_spec() -> None:
    d = _schema()["$defs"]["observation_leaf"]
    assert tuple(d["required"]) == validate._OBS_LEAF_REQUIRED
    assert set(d["properties"]) == set(validate._OBS_LEAF_REQUIRED)


def test_spec_example_batch_validates() -> None:
    example = json.loads(
        (SPECS / "examples" / "evidence.example.json").read_bytes().decode("utf-8")
    )
    validate.validate_batch(example)


def test_service_uses_the_single_ratified_encoder() -> None:
    """No second encoder: our CJSON path IS verifier-cli/reference/canonical.py."""
    assert _ref.canonical_json_bytes is _ref.canonical.canonical_json_bytes
    assert _ref.reference_dir.name == "reference"
    assert (_ref.reference_dir / "canonical.py").is_file()
    fp = _ref.module_fingerprint()
    assert set(fp) == {"canonical.py", "merkle.py", "evidence.py", "assignment.py", "reward.py"}
    assert all(len(v) == 64 for v in fp.values())


def test_merkle_domain_tags_match_spec_table() -> None:
    assert _ref.merkle.DOMAIN_PARTICIPANT == b"CRP:participant:v1"
    assert _ref.merkle.DOMAIN_ASSIGNMENT == b"CRP:assignment:v1"
    assert _ref.merkle.DOMAIN_EVIDENCE == b"CRP:evidence:v1"
    assert _ref.merkle.DOMAIN_REWARD == b"CRP:reward:v1"
    assert _ref.evidence.DOMAIN_OBS == b"obs"
    assert _ref.evidence.DOMAIN_SIGNER == b"signer"
