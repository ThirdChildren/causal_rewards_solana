"""depin_sim — configurable, deterministic DePIN environmental-sensor simulator.

Alpha (M1). Generates a virtual environmental-sensor network with tunable coverage,
redundancy, hardware quality, fault risk, Sybil replication, and demand shifts, then
produces a deterministic artifact (sensor set, cohort assignment, signed-observation
counts, cohort x time-block outcomes) plus a canonical content hash.

Invariants honored here:
  * Determinism (CLAUDE.md #2): all randomness is seeded ONLY from the committed seed.
    No wall-clock, no unseeded RNG, no unordered iteration in artifact-producing paths.
  * Cohort-level estimand (CLAUDE.md #4): the experimental unit is a geographic cohort
    (cell) within a time block. We never model an individual device's counterfactual.
  * Null results are valid (CLAUDE.md #8): scenarios with true_effect == 0 or tiny
    effects are first-class and supported directly by the data-generating process.
"""

__version__ = "0.1.0-alpha"

from depin_sim.config import ScenarioConfig, load_scenario
from depin_sim.run import RunResult, run_scenario

__all__ = [
    "ScenarioConfig",
    "load_scenario",
    "RunResult",
    "run_scenario",
    "__version__",
]
