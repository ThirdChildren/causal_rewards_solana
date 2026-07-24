# Engine artifact schemas

The engine emits **standalone** artifacts with the schemas below.
`backend-data-engineer` owns the audit-bundle layout (file names, directory structure,
`roots.json`, bundle-level `provenance.json`); this document is the engine-side contract the
orchestrator reconciles against it. The engine does not write into the bundle assembler.

| File | Schema id | Committed? | Notes |
| --- | --- | --- | --- |
| `analysis.json` | `crp.analysis/v1` | **yes** — SHA-256 over its canonical bytes | the evaluation artifact `submit_evaluation` anchors; carries top-level `evidence_epoch_roots` (echoed from the assembler) |
| `rewards.parquet` | `crp.reward_leaves/v1` | no (mirror is) | the RATIFIED aggregate on-chain **leaf set** = settlement source (bundle-seam §1.2) |
| `rewards.canonical.json` | `crp.reward_leaves/v1` | **yes** | byte-stable mirror of the leaf set; carries `reward_root_hex` |
| `rewards_detail.parquet` | `crp.rewards_detail/v1` | no (mirror is) | per-(cohort, recipient) Stage-2 detail — supplementary auditability, NOT settlement |
| `rewards_detail.canonical.json` | `crp.rewards_detail/v1` | **yes** | byte-stable mirror of `rewards_detail.parquet` |
| `provenance.json` | `crp.engine_provenance/v1` | **no, by design** | environment only; excluded from every hash |
| `engine_hashes.json` | `crp.engine_hashes/v1` | no | convenience index of the above hashes |

**Why parquet is not the commitment target.** Parquet bytes leak the writer version, statistics
and row-group layout. Following the same pattern the simulator uses for its content hash, every
parquet table has a canonical-JSON mirror and the SHA-256 of *that* is the committed number.
Under the pinned writer settings (`compression="none"`, `version="2.6"`,
`write_statistics=False`) the parquet bytes happen to be reproducible too, and the determinism
test asserts it — but the guarantee does not rest on it.

---

## `analysis.json` (`crp.analysis/v1`)

Canonical JSON per `specs/serialization.md` §2/§3: **no JSON number tokens** — every numeric value
is a canonical decimal string; object keys are NFC-normalized and sorted by UTF-16 code unit;
arrays keep declared order. The encoder is `verifier-cli/reference/canonical.py`, which rejects
Python `int`/`float`, so the rule is mechanically enforced.

Scale suffixes: `_s` = the manifest's `positive_improvement_transform.effect_scale` (e.g. 1e-6);
`_micro` = 1e-6 fixed; `_base_units` and plain counts = scale 1.

```
{
  "schema":        "crp.analysis/v1",
  "spec_version":  "<manifest spec_version>",
  "experiment_id": "<string>",
  "manifest_hash": "sha256:<64hex>",         # over the canonical bytes of the frozen manifest
  "evidence_epoch_roots": [ "<hex>", ... ],  # echoed INPUT from the assembler, ascending epoch order

  "engine": { "name", "version",
              "analysis_container_digest",    # echoed from the frozen analysis_plan
              "reference_source_digest" },    # sha256 over verifier-cli/reference/*.py

  "estimand": { "unit_type",                  # const geo_cohort_time_block (Invariant 4)
                "primary_outcome_metric_id", "improvement_direction",
                "effect_scale", "statement" },

  "design":  { "template", "assignment_method", "treated_fraction_micro",
               "interference_assumption", "carryover_blocks", "washout_blocks",
               "eligible_for_strong_causal_claim", "missingness_policy" },

  "analysis_plan": { "estimator", "standard_error_method", "test_sidedness",
                     "confidence_level_micro", "critical_value_micro",
                     "critical_value_reference", "df_frozen",
                     "minimum_sample": { 4 frozen thresholds } },

  "identification": { "per_cohort_mode",              # see docs/modeling-notes.md §3
                      "supports_strong_causal_claim",
                      "assumptions": [ ... ],          # untestable assumptions, stated plainly
                      "caveat" },                      # "the chain verifies process, not truth"

  "primary_estimate": {                                 # EXACTLY ONE primary number
      "term": "treated",
      "effect_s", "standard_error_s",
      "improvement_s", "margin_s", "conservative_improvement_s",
      "n_units", "n_clusters", "n_parameters", "n_absorbed_fe_groups",
      "cluster_robust_df",                              # G-1
      "finite_sample_correction_micro", "residual_sd_s",
      "se_method" },                                    # prose: CR1 + the within-vs-LSDV note

  "balance": { "threshold_micro", "passed", "max_abs_smd_micro", "treated_share_micro",
               "gates_payout": "false",                 # ALWAYS false: balance is diagnostic
               "covariates": [ { "name", "mean_treated_micro", "mean_control_micro",
                                 "smd_micro", "n_treated", "n_control", "passed" } ] },

  "sensitivity": [ { "name", "kind": "descriptive", "status", "note", "values": {...} } ],

  "cohorts": [ {                                        # one row per geo-cohort, sorted by id
      "cohort_id",
      "effect_s", "standard_error_s",                   # on the RAW outcome metric
      "improvement_s", "margin_s", "conservative_effect_s",
      "allocation_base_units", "budget_base_units",     # before / after the budget cap
      "identified", "identification_mode",
      "meets_minimum_sample", "exclusion_reasons": [ ... ],
      "n_time_blocks", "n_treated_blocks", "n_control_blocks",
      "n_observations", "min_units_in_any_block", "n_clusters", "note" } ],

  "excluded_records": { "total", "by_reason": [ { "reason", "count" } ] },

  "reward_summary": { "budget_base_units",
                      "total_allocation_before_cap_base_units",
                      "total_cohort_budget_base_units", "total_leaf_base_units",
                      "recoverable_base_units", "scaled_to_budget",
                      "leaf_count", "dropped_zero_sum_recipients",
                      "reward_root_hex", "null_distribution", "null_reasons": [ ... ],
                      "n_eligible_cohorts",
                      "leaf_set_shape": "aggregate_one_leaf_per_recipient" }
}
```

**Reproducibility property.** Every payout number is recomputable from the published fields alone:

```
margin_s           = round_half_even(critical_value_micro * standard_error_s / 1_000_000)
conservative_s     = max(0, improvement_s - margin_s)     # 0 if not eligible or not identified
allocation         = reward_curve(conservative_s)          # frozen piecewise-linear curve
```

`exclusion_reasons` on each cohort names exactly which frozen gate fired. Possible values:
`below_min_units_per_cohort`, `below_min_observations_per_cohort`, `below_min_time_blocks`,
`per_cohort_effect_not_identified`, `design_not_eligible_for_causal_reward`.

`excluded_records.by_reason` covers the row-level exclusions:
`missing_data_ineligible`, `missing_data_imputed`, `missing_data_unimputable`,
`switchback_washout`, `upstream_ineligible`.

---

## `rewards.parquet` (`crp.reward_leaves/v1`) — the on-chain leaf set (settlement source)

The RATIFIED aggregate leaf set — exactly what the reward Merkle tree commits and what settlement
claims against (bundle-seam §1.2). One row per leaf, ordered by `leaf_index` ascending, contiguous
from 0.

| column | arrow type | meaning |
| --- | --- | --- |
| `leaf_index` | `uint64` | 0-based rank; also the `ClaimReceipt` nullifier key |
| `recipient_hex` | `string` | unique primary key of the leaf set; 64 lowercase hex (presentation only) |
| `amount_base_units` | `uint64` | `Σ_c leaf_i(c)`, always > 0 |
| `leaf_hash_hex` | `string` | `SHA-256(0x00 ‖ "CRP:reward:v1" ‖ recipient ‖ amount_be ‖ index_be)` |

The canonical mirror (`rewards.canonical.json`) additionally carries `reward_root_hex` and
`leaf_set_shape`. An empty leaf set (fully-null distribution) has `reward_root_hex = "00"*32`
(§6.4). The `recipient_hex`/`recipient_pubkey` column dtype is presentation only — the §6.6 leaf
preimage consumes the 32 raw bytes, so it never enters any committed hash.

## `rewards_detail.parquet` (`crp.rewards_detail/v1`) — supplementary auditability (not settlement)

Per-(cohort, recipient) Stage-2 detail — the split table `reward-policy.md` refers to. Aggregates
to the leaf set above. Sorted by `(cohort_id, recipient)`.

| column | arrow type | meaning |
| --- | --- | --- |
| `cohort_id` | `string` | geo-cohort id |
| `recipient_hex` | `string` | 64 lowercase hex = the 32-byte ed25519 signer pubkey |
| `weight` | `uint64` | `w_i` from the frozen CRP-WS1 formula |
| `cohort_weight_total` | `uint64` | `W = Σ_i w_i` in this cohort |
| `cohort_budget_base_units` | `uint64` | `budget_c` after the budget cap |
| `amount_base_units` | `uint64` | `leaf_i(c) = floor(budget_c · w_i / W)` |
| `recipient_aggregate_base_units` | `uint64` | `Σ_c leaf_i(c)` for this recipient |
| `leaf_index` | `uint64` (nullable) | the recipient's on-chain leaf index; **null** if omitted |
| `included_in_leaf_set` | `bool` | false ⇒ zero aggregate, omitted per §6.6 |

## `provenance.json` (`crp.engine_provenance/v1`)

`engine_name`, `engine_version`, `source_commit`, `analysis_container_digest`,
`reference_source_digest`, `packages{}`.

**There is deliberately no execution timestamp.** A wall-clock field in an artifact that must be
byte-reproducible would defeat the purpose. If the bundle needs one, it belongs in the
bundle-level `provenance.json` owned by `backend-data-engineer`, outside every hashed artifact.
