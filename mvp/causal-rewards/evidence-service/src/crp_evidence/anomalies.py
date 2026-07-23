"""Findings — admissible-but-suspicious signals recorded in the audit bundle.

A *finding* is not a rejection. Silently dropping data would itself be a selective-reporting
attack surface, so anything that is structurally valid and correctly signed is ADMITTED and
the suspicion is published alongside it. The challenge process (and a human reviewer) acts on
findings; the pipeline does not.

Findings are deterministic pure functions of the accepted batch set — same input set, same
findings, same order (sorted by ``(code, subject)``), so they do not perturb the bundle hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

__all__ = ["FindingCode", "Finding", "correlation_findings"]


class FindingCode:
    """Stable finding codes (published in the bundle; additive only)."""

    #: Two batches from DIFFERENT producers carry an identical observations root for the same
    #: (epoch, cohort). Identical content under two identities is replication, not independent
    #: corroboration — the classic Sybil-amplification shape.
    DUPLICATE_OBSERVATIONS_ROOT_ACROSS_PRODUCERS = (
        "DUPLICATE_OBSERVATIONS_ROOT_ACROSS_PRODUCERS"
    )
    #: The same observations root appears under two DIFFERENT (epoch, cohort) cells — the same
    #: measured content re-reported as if it were new evidence.
    OBSERVATIONS_ROOT_REUSED_ACROSS_CELLS = "OBSERVATIONS_ROOT_REUSED_ACROSS_CELLS"
    #: Identical signer set root across two different producers for one cell: the "independent"
    #: collectors are drawing on the same device population.
    SHARED_SIGNER_SET_ACROSS_PRODUCERS = "SHARED_SIGNER_SET_ACROSS_PRODUCERS"
    #: aggregate_summary.accepted_count disagrees with observations_commitment.leaf_count.
    ACCEPTED_COUNT_LEAF_COUNT_DIVERGENCE = "ACCEPTED_COUNT_LEAF_COUNT_DIVERGENCE"
    #: An epoch/cohort cell expected by the frozen schedule has no anchored batch.
    MISSING_SCHEDULED_CELL = "MISSING_SCHEDULED_CELL"
    #: A whole scheduled epoch has an empty evidence tree (32 zero bytes).
    EMPTY_SCHEDULED_EPOCH = "EMPTY_SCHEDULED_EPOCH"
    #: A batch was anchored for an epoch index outside the frozen schedule.
    UNSCHEDULED_EPOCH_PRESENT = "UNSCHEDULED_EPOCH_PRESENT"


@dataclass(frozen=True, order=True)
class Finding:
    code: str
    subject: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "subject": self.subject, "detail": self.detail}


def _cell(batch: Mapping[str, Any]) -> str:
    return "%s/epoch=%s/cohort=%s" % (
        batch["experiment_id"],
        batch["epoch_index"],
        batch["cohort_id"],
    )


def correlation_findings(batches: Sequence[Mapping[str, Any]]) -> list[Finding]:
    """Cross-batch correlation checks over the ACCEPTED batch set.

    Deliberately cheap and explainable: every check is a statement about equality of committed
    32-byte roots, which a verifier can re-derive from the bundle with no extra data. No
    statistical thresholds, no tunables — a tunable here would be an un-frozen analysis choice
    on the artifact path (invariant 1).
    """
    findings: list[Finding] = []

    obs_root_index: dict[str, list[Mapping[str, Any]]] = {}
    signer_root_index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}

    for b in batches:
        obs_root = b["observations_commitment"]["merkle_root_hex"]
        obs_root_index.setdefault(obs_root, []).append(b)
        signer_root_index.setdefault(
            (_cell(b), b["signer_set_commitment"]["merkle_root_hex"]), []
        ).append(b)

        accepted = int(b["aggregate_summary"]["accepted_count"])
        leaf_count = int(b["observations_commitment"]["leaf_count"])
        if accepted != leaf_count:
            findings.append(
                Finding(
                    FindingCode.ACCEPTED_COUNT_LEAF_COUNT_DIVERGENCE,
                    _cell(b),
                    "accepted_count=%d but observations leaf_count=%d; the committed "
                    "observation set does not match the reported accepted volume"
                    % (accepted, leaf_count),
                )
            )

    for obs_root, group in obs_root_index.items():
        if len(group) < 2:
            continue
        producers = {b["batch_signature"]["signer_pubkey"] for b in group}
        cells = {_cell(b) for b in group}
        if len(producers) > 1 and len(cells) == 1:
            findings.append(
                Finding(
                    FindingCode.DUPLICATE_OBSERVATIONS_ROOT_ACROSS_PRODUCERS,
                    obs_root,
                    "observations root reported by %d distinct producers for cell %s: %s"
                    % (len(producers), sorted(cells)[0], ", ".join(sorted(producers))),
                )
            )
        if len(cells) > 1:
            findings.append(
                Finding(
                    FindingCode.OBSERVATIONS_ROOT_REUSED_ACROSS_CELLS,
                    obs_root,
                    "identical observations root anchored for %d distinct cells: %s"
                    % (len(cells), ", ".join(sorted(cells))),
                )
            )

    for (cell, signer_root), group in signer_root_index.items():
        producers = {b["batch_signature"]["signer_pubkey"] for b in group}
        if len(producers) > 1:
            findings.append(
                Finding(
                    FindingCode.SHARED_SIGNER_SET_ACROSS_PRODUCERS,
                    "%s|%s" % (cell, signer_root),
                    "signer set root shared by %d producers in one cell: %s"
                    % (len(producers), ", ".join(sorted(producers))),
                )
            )

    return sorted(findings)
