"""Selective-reporting defense: expected schedule vs anchored coverage."""

from __future__ import annotations

import fixtures as fx

from crp_evidence.anomalies import FindingCode
from crp_evidence.ingest import EvidenceLedger
from crp_evidence.schedule import evaluate_coverage, schedule_from_manifest


def _spec(epochs: int = 2, cohorts=fx.COHORT_IDS):
    return schedule_from_manifest(fx.small_manifest(epoch_count=epochs), cohorts)


def test_schedule_is_derived_from_frozen_manifest_fields() -> None:
    s = _spec(epochs=3)
    assert s.epoch_count == 3
    assert s.block_seconds == 3600
    assert s.expected_epochs() == ("0", "1", "2")
    assert s.epoch_time_range(0) == (s.active_start, s.active_start + 3600)
    assert s.epoch_time_range(2)[0] == s.active_start + 7200


def test_full_coverage_yields_no_missingness_findings() -> None:
    batches = [
        fx.make_batch(epoch_index=e, cohort_id=c)
        for e in ("0", "1")
        for c in fx.COHORT_IDS
    ]
    rep = evaluate_coverage(_spec(), batches)
    assert rep.missing_cells == ()
    assert rep.findings == ()
    assert rep.coverage_micro == 1_000_000


def test_a_withheld_cell_is_flagged() -> None:
    """The core selective-reporting case: a cohort's bad epoch quietly not anchored."""
    batches = [
        fx.make_batch(epoch_index=e, cohort_id=c)
        for e in ("0", "1")
        for c in fx.COHORT_IDS
        if not (e == "1" and c == "cohort-b")
    ]
    rep = evaluate_coverage(_spec(), batches)
    assert rep.missing_cells == (("1", "cohort-b"),)
    assert [f.code for f in rep.findings] == [FindingCode.MISSING_SCHEDULED_CELL]
    assert rep.coverage_micro == 750_000


def test_a_wholly_empty_scheduled_epoch_is_flagged_as_well() -> None:
    batches = [fx.make_batch(epoch_index="0", cohort_id=c) for c in fx.COHORT_IDS]
    rep = evaluate_coverage(_spec(), batches)
    codes = {f.code for f in rep.findings}
    assert FindingCode.EMPTY_SCHEDULED_EPOCH in codes
    assert rep.empty_epochs == ("1",)


def test_an_out_of_schedule_epoch_is_flagged() -> None:
    batches = [fx.make_batch(epoch_index="7", cohort_id=c) for c in fx.COHORT_IDS]
    rep = evaluate_coverage(_spec(), batches)
    assert rep.unscheduled_epochs == ("7",)
    assert FindingCode.UNSCHEDULED_EPOCH_PRESENT in {f.code for f in rep.findings}


def test_report_is_deterministic_and_order_independent() -> None:
    batches = [
        fx.make_batch(epoch_index=e, cohort_id=c)
        for e in ("0", "1")
        for c in fx.COHORT_IDS
        if not (e == "0" and c == "cohort-a")
    ]
    a = evaluate_coverage(_spec(), batches).to_dict()
    b = evaluate_coverage(_spec(), list(reversed(batches))).to_dict()
    assert a == b


def test_missingness_is_never_a_rejection() -> None:
    """An incomplete epoch still ingests and still produces a root."""
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest_many([fx.make_batch(epoch_index="0", cohort_id="cohort-a")], strict=True)
    rep = evaluate_coverage(_spec(), [a.batch for a in led.accepted])
    assert len(led.accepted) == 1
    assert len(rep.missing_cells) == 3


# --------------------------------------------------------------- correlation findings


def test_identical_observations_root_across_producers_is_flagged() -> None:
    obs = fx.commitments(4, 0x40)
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest(fx.make_batch(epoch_index="0", cohort_id="cohort-a", obs=obs))
    led.ingest(
        fx.make_batch(
            epoch_index="0", cohort_id="cohort-a", obs=obs, secret=fx.PRODUCER_B_SECRET
        )
    )
    codes = {f.code for f in led.findings()}
    assert FindingCode.DUPLICATE_OBSERVATIONS_ROOT_ACROSS_PRODUCERS in codes
    assert FindingCode.SHARED_SIGNER_SET_ACROSS_PRODUCERS in codes
    assert len(led.accepted) == 2, "flagged, not rejected"


def test_same_observations_root_reused_across_cells_is_flagged() -> None:
    obs = fx.commitments(4, 0x40)
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest(fx.make_batch(epoch_index="0", cohort_id="cohort-a", obs=obs))
    led.ingest(fx.make_batch(epoch_index="1", cohort_id="cohort-a", obs=obs))
    assert FindingCode.OBSERVATIONS_ROOT_REUSED_ACROSS_CELLS in {
        f.code for f in led.findings()
    }


def test_accepted_count_vs_leaf_count_divergence_is_flagged() -> None:
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    b = dict(b)
    b["aggregate_summary"] = dict(b["aggregate_summary"], accepted_count="3")
    b = fx.sign_batch(b, fx.PRODUCER_A_SECRET)
    led = EvidenceLedger(experiment_id=fx.EXPERIMENT_ID)
    led.ingest(b)
    assert FindingCode.ACCEPTED_COUNT_LEAF_COUNT_DIVERGENCE in {f.code for f in led.findings()}
