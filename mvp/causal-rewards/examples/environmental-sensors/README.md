# examples/environmental-sensors/ — Reference pilot wiring

Simulated environmental sensor network in **shadow mode**: the live prediction service is
never degraded; a *separate* evaluation pipeline randomly includes/holds out geographic
cohorts across time blocks.

Treatment effect = change in out-of-sample prediction error (e.g. held-out RMSE) caused by
including a cohort's data. Design templates: cluster-randomized, switchback, matched-cluster,
observational-replay (replay is **not** eligible for the strongest causal claim).

**Status:** stub. Wired up alongside M3/M4.

## License

Apache-2.0.
