"""Expected epoch schedule + missingness policy (selective-reporting defense).

Threat: a coordinator who anchors evidence only for epochs/cohorts where the numbers look
good. If the expected schedule is implicit, "absent" and "never expected" are
indistinguishable and the omission is invisible in the audit bundle.

Where the schedule comes from
-----------------------------
The frozen manifest does NOT (as of manifest.schema.json v1.1) carry an explicit
``evidence_schedule`` / missingness-policy object. The schedule is therefore DERIVED from
frozen manifest fields, which is sound because every input is itself frozen:

    epoch_count   = estimand.time_block.block_count
    block_seconds = estimand.time_block.block_seconds
    epoch e       covers [ active_start + e*block_seconds , active_start + (e+1)*block_seconds )
    expected cells = epoch_count x <the frozen cohort set>

The derivation is stated explicitly in ``ScheduleSpec`` so an independent verifier reproduces
it from the manifest alone. A cohort set must be supplied by the caller (from the published
CohortSet / participants table) because the manifest freezes only ``cohort_count``, not the
ids. If ``cohort_count`` and the supplied set disagree, that is itself reported.

**Open spec item (proposal, not decided here):** an explicit
``manifest.evidence_schedule { epoch_count, epoch_seconds, expected_cohort_coverage,
missingness_action }`` would remove this derivation. Filed to protocol-architect; see README.

Policy
------
Missingness produces FINDINGS, never rejections or silent imputation. An empty epoch is a
LEGAL state (§6.4 gives it a root of 32 zero bytes) that must be anchored and visible, not an
error. The causal engine consumes ``missingness.json`` and decides what a missing cell does to
the estimate — that decision belongs to the frozen analysis plan, not to this service.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .anomalies import Finding, FindingCode

__all__ = ["ScheduleSpec", "MissingnessReport", "schedule_from_manifest", "evaluate_coverage"]


@dataclass(frozen=True)
class ScheduleSpec:
    """The expected evidence schedule, derived from frozen manifest fields."""

    experiment_id: str
    epoch_count: int
    block_seconds: int
    active_start: int
    active_end: int
    cohort_ids: tuple[str, ...]
    declared_cohort_count: int

    def epoch_time_range(self, epoch_index: int) -> tuple[int, int]:
        start = self.active_start + epoch_index * self.block_seconds
        return start, start + self.block_seconds

    def expected_epochs(self) -> tuple[str, ...]:
        return tuple(str(e) for e in range(self.epoch_count))

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "epoch_count": str(self.epoch_count),
            "block_seconds": str(self.block_seconds),
            "active_start": str(self.active_start),
            "active_end": str(self.active_end),
            "declared_cohort_count": str(self.declared_cohort_count),
            "cohort_ids": list(self.cohort_ids),
            "derivation": (
                "epoch_count=estimand.time_block.block_count; "
                "block_seconds=estimand.time_block.block_seconds; "
                "epoch e covers [windows.active_start+e*block_seconds, +block_seconds); "
                "expected cells = epoch_count x cohort_ids"
            ),
        }


def schedule_from_manifest(
    manifest: Mapping[str, Any], cohort_ids: Sequence[str]
) -> ScheduleSpec:
    """Derive the expected schedule from a frozen manifest plus the published cohort set."""
    tb = manifest["estimand"]["time_block"]
    w = manifest["windows"]
    return ScheduleSpec(
        experiment_id=str(manifest["experiment_id"]),
        epoch_count=int(tb["block_count"]),
        block_seconds=int(tb["block_seconds"]),
        active_start=int(w["active_start"]),
        active_end=int(w["active_end"]),
        cohort_ids=tuple(sorted(str(c) for c in cohort_ids)),
        declared_cohort_count=int(manifest["estimand"]["cohort_definition"]["cohort_count"]),
    )


@dataclass(frozen=True)
class MissingnessReport:
    spec: ScheduleSpec
    observed_cells: tuple[tuple[str, str], ...]
    missing_cells: tuple[tuple[str, str], ...]
    empty_epochs: tuple[str, ...]
    unscheduled_epochs: tuple[str, ...]
    unscheduled_cohorts: tuple[str, ...]
    findings: tuple[Finding, ...]

    @property
    def coverage_micro(self) -> int:
        """Observed / expected cells, micro-scaled (integer; §2.2 micro class). No float."""
        expected = self.spec.epoch_count * len(self.spec.cohort_ids)
        if expected == 0:
            return 0
        return (len(self.observed_cells) * 1_000_000) // expected

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule": self.spec.to_dict(),
            "expected_cell_count": str(self.spec.epoch_count * len(self.spec.cohort_ids)),
            "observed_cell_count": str(len(self.observed_cells)),
            "missing_cell_count": str(len(self.missing_cells)),
            "coverage_micro": str(self.coverage_micro),
            "missing_cells": [
                {"epoch_index": e, "cohort_id": c} for e, c in self.missing_cells
            ],
            "empty_epochs": list(self.empty_epochs),
            "unscheduled_epochs": list(self.unscheduled_epochs),
            "unscheduled_cohorts": list(self.unscheduled_cohorts),
            "findings": [f.to_dict() for f in self.findings],
            "policy": (
                "Missingness is REPORTED, never imputed and never a rejection. An epoch with "
                "no batches is a legal state with root=32 zero bytes (serialization.md §6.4) "
                "and MUST still be anchored so absence is committed, not merely unrecorded. "
                "The frozen analysis plan decides the estimator consequence of a missing cell."
            ),
        }


def evaluate_coverage(
    spec: ScheduleSpec, batches: Sequence[Mapping[str, Any]]
) -> MissingnessReport:
    """Compare anchored batches against the expected schedule. Pure function, sorted output."""
    observed: set[tuple[str, str]] = set()
    seen_epochs: set[str] = set()
    seen_cohorts: set[str] = set()
    for b in batches:
        e = str(int(b["epoch_index"]))
        c = str(b["cohort_id"])
        observed.add((e, c))
        seen_epochs.add(e)
        seen_cohorts.add(c)

    expected_epochs = set(spec.expected_epochs())
    expected_cells = {(e, c) for e in expected_epochs for c in spec.cohort_ids}
    missing = sorted(expected_cells - observed, key=lambda ec: (int(ec[0]), ec[1]))
    empty_epochs = sorted(expected_epochs - seen_epochs, key=int)
    unscheduled_epochs = sorted(seen_epochs - expected_epochs, key=int)
    unscheduled_cohorts = sorted(seen_cohorts - set(spec.cohort_ids))

    findings: list[Finding] = []
    for e, c in missing:
        findings.append(
            Finding(
                FindingCode.MISSING_SCHEDULED_CELL,
                "epoch=%s/cohort=%s" % (e, c),
                "the frozen schedule expects a batch for this cell; none was anchored",
            )
        )
    for e in empty_epochs:
        findings.append(
            Finding(
                FindingCode.EMPTY_SCHEDULED_EPOCH,
                "epoch=%s" % e,
                "scheduled epoch has zero anchored batches (evidence root = 32 zero bytes)",
            )
        )
    for e in unscheduled_epochs:
        findings.append(
            Finding(
                FindingCode.UNSCHEDULED_EPOCH_PRESENT,
                "epoch=%s" % e,
                "batch anchored for an epoch index outside the frozen schedule (0..%d)"
                % (spec.epoch_count - 1),
            )
        )
    for c in unscheduled_cohorts:
        findings.append(
            Finding(
                FindingCode.UNSCHEDULED_EPOCH_PRESENT,
                "cohort=%s" % c,
                "batch anchored for a cohort id outside the frozen cohort set",
            )
        )

    return MissingnessReport(
        spec=spec,
        observed_cells=tuple(sorted(observed, key=lambda ec: (int(ec[0]), ec[1]))),
        missing_cells=tuple(missing),
        empty_epochs=tuple(empty_epochs),
        unscheduled_epochs=tuple(unscheduled_epochs),
        unscheduled_cohorts=tuple(unscheduled_cohorts),
        findings=tuple(sorted(findings)),
    )
