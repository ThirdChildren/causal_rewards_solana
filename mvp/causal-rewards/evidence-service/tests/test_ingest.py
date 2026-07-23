"""Ingestion trust boundary: never trust a producer hash; dedup the right things only."""

from __future__ import annotations

import copy

import fixtures as fx
import pytest

from crp_evidence import ed25519
from crp_evidence.errors import EvidenceRejected
from crp_evidence.ingest import EvidenceLedger, recompute_header_hash, verify_batch_signature
from crp_evidence.roots import evidence_epoch_root


def _ledger() -> EvidenceLedger:
    return EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)


def test_valid_batch_is_accepted_and_hash_is_recomputed_not_trusted() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    acc = _ledger().ingest(b)
    assert acc.header_hash_hex == recompute_header_hash(b).hex()
    assert acc.header_hash_hex == b["batch_signature"]["header_hash_hex"]


def test_forged_header_hash_is_rejected_before_signature_check() -> None:
    """A producer claiming a different header hash is rejected even if the sig is valid for it."""
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    forged = copy.deepcopy(b)
    fake = "cc" * 32
    forged["batch_signature"]["header_hash_hex"] = fake
    forged["batch_signature"]["signature_hex"] = ed25519.sign_deterministic(
        fx.PRODUCER_A_SECRET, bytes.fromhex(fake)
    ).hex()
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(forged)
    assert ei.value.code == "BATCH_HEADER_HASH_MISMATCH"
    assert ei.value.detail["recomputed"] == recompute_header_hash(b).hex()


def test_mutated_body_is_rejected_because_the_hash_is_recomputed() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    tampered = copy.deepcopy(b)
    tampered["aggregate_summary"]["accepted_count"] = "999999"
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(tampered)
    assert ei.value.code == "BATCH_HEADER_HASH_MISMATCH"


def test_signature_by_the_wrong_key_is_rejected() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    other = copy.deepcopy(b)
    other["batch_signature"]["signature_hex"] = ed25519.sign_deterministic(
        fx.PRODUCER_B_SECRET, recompute_header_hash(b)
    ).hex()
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(other)
    assert ei.value.code == "BATCH_SIGNATURE_INVALID"


def test_signer_pubkey_must_decode_to_32_bytes() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    bad = copy.deepcopy(b)
    # 33-byte decode, still 32..44 base58 CHARACTERS (evidence-05 shape).
    bad["batch_signature"]["signer_pubkey"] = "JEKNVnkbo3jma5nREBBJCDoXFVeKkD56V3xKrvRmWxFH"
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(bad)
    assert ei.value.code == "SIGNER_PUBKEY_NOT_32_BYTES"


def test_byte_identical_replay_is_rejected_at_ingestion() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    led = _ledger()
    led.ingest(b)
    with pytest.raises(EvidenceRejected) as ei:
        led.ingest(copy.deepcopy(b))
    assert ei.value.code == "REPLAYED_BATCH"
    assert len(led.accepted) == 1


def test_same_producer_double_reporting_one_cell_is_a_nonce_violation() -> None:
    """Different content, same (experiment, epoch, cohort, producer) -> DUPLICATE_EVENT_NONCE."""
    a = fx.make_batch(epoch_index="0", cohort_id="cohort-a", obs=fx.commitments(4, 0x40))
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a", obs=fx.commitments(4, 0x50))
    assert a != b
    led = _ledger()
    led.ingest(a)
    with pytest.raises(EvidenceRejected) as ei:
        led.ingest(b)
    assert ei.value.code == "DUPLICATE_EVENT_NONCE"


def test_two_producers_same_cell_are_two_distinct_admitted_leaves() -> None:
    """NORMATIVE (roots.py): corroboration is evidence, not duplication. Both admitted."""
    a = fx.make_batch(epoch_index="0", cohort_id="cohort-a", secret=fx.PRODUCER_A_SECRET)
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a", secret=fx.PRODUCER_B_SECRET)
    led = _ledger()
    led.ingest(a)
    led.ingest(b)
    assert len(led.accepted) == 2
    root, records = evidence_epoch_root(led.batches_for_epoch("0"))
    assert len(records) == 2
    assert records[0]["leaf_hash_hex"] < records[1]["leaf_hash_hex"], "leaf order must be strict"
    assert root != "00" * 32


def test_wrong_experiment_id_is_rejected() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a", experiment_id="some-other-exp")
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(b)
    assert ei.value.code == "EXPERIMENT_ID_MISMATCH"


def test_additional_property_is_a_data_minimization_rejection() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    leaky = copy.deepcopy(b)
    leaky["gps_lat_micro"] = "45123456"
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(leaky)
    assert ei.value.code == "DATA_MINIMIZATION_VIOLATION"
    assert "gps_lat_micro" in ei.value.detail["extra"]


def test_non_strict_ingest_records_rejections_and_continues() -> None:
    good = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    bad = copy.deepcopy(good)
    bad["aggregate_summary"]["accepted_count"] = "007"  # non-canonical integer string
    led = _ledger()
    led.ingest_many([bad, good], strict=False)
    assert len(led.accepted) == 1
    assert led.rejection_records()[0]["code"] == "NON_CANONICAL_INTEGER_STRING"


def test_time_range_must_be_half_open_and_increasing() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    bad = copy.deepcopy(b)
    bad["time_range"]["end"] = bad["time_range"]["start"]
    with pytest.raises(EvidenceRejected) as ei:
        _ledger().ingest(bad)
    assert ei.value.code == "TIME_RANGE_INVALID"


def test_verify_batch_signature_returns_the_recomputed_hash() -> None:
    b = fx.make_batch(epoch_index="3", cohort_id="cohort-b")
    assert verify_batch_signature(b) == recompute_header_hash(b)


def test_epochs_are_ordered_numerically_not_lexically() -> None:
    led = _ledger()
    for e in ("9", "10", "2"):
        led.ingest(fx.make_batch(epoch_index=e, cohort_id="cohort-a"))
    assert led.epochs() == ["2", "9", "10"]
