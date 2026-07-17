"""Scenario configuration.

Scenario files are JSON (content-addressed alongside the manifest). All knobs that steer
the data-generating process live here so a scenario is fully described by (config + seed).

Field-name alignment with the manifest (from the concept note / forthcoming
specs/manifest.schema.json, owned by protocol-architect):
  * ``design``          -> manifest ``design`` (cluster_randomized | cluster_switchback |
                           matched_cluster | observational_replay)
  * ``unit``            -> manifest ``unit`` == "geo_cell_time_block" (fixed here)
  * ``primary_outcome`` -> manifest ``primary_outcome`` == "held_out_rmse" (fixed here)
  * ``treatment``       -> manifest ``treatment`` == "cohort_data_included" (fixed here)
  * ``minimum_sample``  -> manifest ``minimum_sample``
  * ``confidence_level``-> manifest ``confidence_level``
MISMATCH NOTES (surface to protocol-architect): the manifest has no field for the
data-generating truth (true_effect, interference, confounding, sybil params). Those are
simulator-only ground truth and must NOT leak into a real frozen manifest.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

DESIGNS = (
    "cluster_randomized",
    "cluster_switchback",
    "matched_cluster",
    "observational_replay",
)

# Aligned to specs/manifest.schema.json: estimand.unit_type is a const "geo_cohort_time_block"
# (protocol-architect, ratified). We mirror that exact string so the simulator's unit label
# matches the manifest the causal engine will consume.
UNIT = "geo_cohort_time_block"
PRIMARY_OUTCOME = "held_out_rmse"
TREATMENT = "cohort_data_included"


@dataclass(frozen=True)
class CoverageConfig:
    """Sensor supply per geographic cell.

    Cells draw an expected sensor count from a gamma distribution; a fraction of cells are
    forced ``sparse`` (few sensors, high marginal value) to model under-supplied areas.
    """

    mean_sensors_per_cell: float = 8.0
    dispersion: float = 1.5          # gamma shape; lower => more over/under-supply spread
    sparse_cell_fraction: float = 0.25
    sparse_sensors_per_cell: float = 1.5


@dataclass(frozen=True)
class QualityConfig:
    """Per-sensor hardware quality in [0, 1] via a Beta draw."""

    alpha: float = 5.0
    beta: float = 2.0


@dataclass(frozen=True)
class FaultConfig:
    """Per-sensor per-time-block fault model.

    ``base_risk`` is the probability a healthy sensor faults in a block; lower-quality
    sensors fault more (risk scales by ``1 + quality_sensitivity * (1 - quality)``).
    A faulting sensor emits zero usable observations for that block.
    """

    base_risk: float = 0.03
    quality_sensitivity: float = 1.5


@dataclass(frozen=True)
class SybilConfig:
    """Sybil replication: a fraction of sensors are sybils that duplicate a group's data.

    Sybils inflate *activity* (observation counts) without adding information value, so
    activity/quality baselines overpay them while a causal estimand does not. ``group_size``
    sensors share one true underlying signal (near-duplicate observations).
    """

    sensor_fraction: float = 0.0
    group_size: int = 3
    replication_factor: float = 1.0  # multiplies observation counts for sybil sensors


@dataclass(frozen=True)
class DemandConfig:
    """Demand shift across time blocks.

    Demand scales observation volume and (in confounded designs) treatment propensity and
    outcome level. ``shift_amplitude`` is the relative swing; ``pattern`` selects the shape.
    """

    shift_amplitude: float = 0.0     # 0 => flat demand
    pattern: str = "ramp"            # ramp | seasonal | step


@dataclass(frozen=True)
class EffectConfig:
    """Ground-truth causal structure of the outcome (SIMULATOR TRUTH — never in a manifest).

    Outcome is out-of-sample prediction error (held-out RMSE); lower is better. Including a
    treated cohort's data reduces error by ``true_effect`` on average. Effects are
    heterogeneous across cohorts (scaled by cohort information value: sparse cells help more).
    """

    baseline_rmse: float = 1.0
    true_effect: float = 0.10        # mean RMSE reduction from inclusion; 0 => null scenario
    effect_heterogeneity: float = 0.30
    interference: float = 0.0        # fraction of a cohort's effect leaking to neighbor cells
    confounding: float = 0.0         # demand->(treatment,outcome) coupling for observational
    cluster_noise_sd: float = 0.08   # cohort-level shared noise (drives cluster-robust SEs)
    obs_noise_sd: float = 0.04       # residual noise per cohort x time-block


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    description: str = ""
    seed: str = "0x0000000000000000000000000000000000000000000000000000000000000001"

    # Topology / experimental frame.
    n_cells: int = 40                # number of geographic cohorts
    n_time_blocks: int = 12
    design: str = "cluster_randomized"
    treatment_fraction: float = 0.5  # share of cohorts (or cohort-blocks) treated
    guard_band_cells: int = 0        # neighbor cells held out around a treated cell (spillover control)
    carryover_blocks: int = 0        # switchback: blocks discarded after a treatment flip

    # Frozen-analysis-plan fields (mirror the manifest).
    minimum_sample: int = 40         # min signed observations for a cohort-block to be eligible
    confidence_level: float = 0.95

    # Data-generating sub-configs.
    coverage: CoverageConfig = field(default_factory=CoverageConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    faults: FaultConfig = field(default_factory=FaultConfig)
    sybil: SybilConfig = field(default_factory=SybilConfig)
    demand: DemandConfig = field(default_factory=DemandConfig)
    effect: EffectConfig = field(default_factory=EffectConfig)

    # Fixed frame identifiers (align with manifest).
    unit: str = UNIT
    primary_outcome: str = PRIMARY_OUTCOME
    treatment: str = TREATMENT

    def validate(self) -> None:
        if self.design not in DESIGNS:
            raise ValueError(f"design must be one of {DESIGNS}, got {self.design!r}")
        if self.unit != UNIT:
            raise ValueError(f"unit is fixed to {UNIT!r} for this simulator")
        if self.primary_outcome != PRIMARY_OUTCOME:
            raise ValueError(f"primary_outcome is fixed to {PRIMARY_OUTCOME!r}")
        if self.n_cells < 2:
            raise ValueError("n_cells must be >= 2")
        if self.n_time_blocks < 1:
            raise ValueError("n_time_blocks must be >= 1")
        if not 0.0 < self.treatment_fraction < 1.0:
            raise ValueError("treatment_fraction must be in (0, 1)")
        if not 0.0 < self.confidence_level < 1.0:
            raise ValueError("confidence_level must be in (0, 1)")

    def to_dict(self) -> dict:
        return asdict(self)


def _build_sub(cls, data: dict | None):
    return cls(**data) if data else cls()


def scenario_from_dict(data: dict) -> ScenarioConfig:
    data = dict(data)
    sub_specs = {
        "coverage": CoverageConfig,
        "quality": QualityConfig,
        "faults": FaultConfig,
        "sybil": SybilConfig,
        "demand": DemandConfig,
        "effect": EffectConfig,
    }
    kwargs = {k: _build_sub(cls, data.pop(k, None)) for k, cls in sub_specs.items()}
    cfg = ScenarioConfig(**data, **kwargs)
    cfg.validate()
    return cfg


def load_scenario(path: str | Path) -> ScenarioConfig:
    with open(path, "r", encoding="utf-8") as fh:
        return scenario_from_dict(json.load(fh))
