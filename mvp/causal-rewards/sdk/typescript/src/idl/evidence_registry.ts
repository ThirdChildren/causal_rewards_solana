/**
 * Program IDL in Anchor 0.30.1 native format (snake_case), regenerated from
 * the CURRENT published idl/evidence_registry.json. Pairs with new Program(<json>) at runtime.
 *
 * Auto-generated: do not edit by hand. Re-copy from idl/ when the program changes.
 */
export type EvidenceRegistry = {
  "address": "Ex82ncHsgc4ZFWDYQQzwR96GNNnKd3YmoULnjWgb1neP",
  "metadata": {
    "name": "evidence_registry",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol \u2014 evidence registry (per-epoch batch roots, time ranges, signer commitments, aggregate counts)."
  },
  "instructions": [
    {
      "name": "post_evidence_epoch",
      "discriminator": [
        113,
        175,
        40,
        159,
        192,
        165,
        189,
        218
      ],
      "accounts": [
        {
          "name": "experiment"
        },
        {
          "name": "evidence_epoch",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  112,
                  111,
                  99,
                  104
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              },
              {
                "kind": "arg",
                "path": "epoch_index"
              }
            ]
          }
        },
        {
          "name": "prev_epoch"
        },
        {
          "name": "coordinator",
          "writable": true,
          "signer": true
        },
        {
          "name": "system_program",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "epoch_index",
          "type": "u64"
        },
        {
          "name": "args",
          "type": {
            "defined": {
              "name": "EvidenceEpochArgs"
            }
          }
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "EvidenceEpoch",
      "discriminator": [
        136,
        24,
        176,
        142,
        197,
        53,
        144,
        64
      ]
    }
  ],
  "events": [
    {
      "name": "EvidenceEpochPosted",
      "discriminator": [
        137,
        87,
        220,
        145,
        42,
        27,
        148,
        153
      ]
    }
  ],
  "errors": [
    {
      "code": 6000,
      "name": "WrongStatus",
      "msg": "Experiment is not Active"
    },
    {
      "code": 6001,
      "name": "Unauthorized",
      "msg": "Signer is not the coordinator"
    },
    {
      "code": 6002,
      "name": "InvalidCohortId",
      "msg": "cohort_id empty or too long"
    },
    {
      "code": 6003,
      "name": "InvalidTimeRange",
      "msg": "time_range invalid: require start < end"
    },
    {
      "code": 6004,
      "name": "TimeRangeOutsideActiveWindow",
      "msg": "time_range outside the active window"
    },
    {
      "code": 6005,
      "name": "InconsistentCounts",
      "msg": "distinct_signers exceeds total observation count"
    },
    {
      "code": 6006,
      "name": "PrevEpochMissing",
      "msg": "previous epoch does not exist (epochs must be monotonic, no gaps)"
    },
    {
      "code": 6007,
      "name": "MathOverflow",
      "msg": "Checked arithmetic overflow"
    }
  ],
  "types": [
    {
      "name": "EvidenceEpoch",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "epoch_index",
            "type": "u64"
          },
          {
            "name": "cohort_id",
            "type": "string"
          },
          {
            "name": "time_start",
            "type": "i64"
          },
          {
            "name": "time_end",
            "type": "i64"
          },
          {
            "name": "signer_set_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observations_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "accepted_count",
            "type": "u64"
          },
          {
            "name": "rejected_count",
            "type": "u64"
          },
          {
            "name": "distinct_signers",
            "type": "u64"
          },
          {
            "name": "content_hash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "producer",
            "type": "pubkey"
          },
          {
            "name": "bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "EvidenceEpochArgs",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "cohort_id",
            "type": "string"
          },
          {
            "name": "time_start",
            "type": "i64"
          },
          {
            "name": "time_end",
            "type": "i64"
          },
          {
            "name": "signer_set_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observations_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "accepted_count",
            "type": "u64"
          },
          {
            "name": "rejected_count",
            "type": "u64"
          },
          {
            "name": "distinct_signers",
            "type": "u64"
          },
          {
            "name": "content_hash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "producer",
            "type": "pubkey"
          }
        ]
      }
    },
    {
      "name": "EvidenceEpochPosted",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "epoch_index",
            "type": "u64"
          },
          {
            "name": "cohort_id",
            "type": "string"
          },
          {
            "name": "time_start",
            "type": "i64"
          },
          {
            "name": "time_end",
            "type": "i64"
          },
          {
            "name": "signer_set_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observations_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "accepted_count",
            "type": "u64"
          }
        ]
      }
    },
    {
      "name": "Experiment",
      "docs": [
        "Per-experiment record. Holds only hashes / roots / status / windows (Invariant 5)."
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "status",
            "type": {
              "defined": {
                "name": "ExperimentStatus"
              }
            }
          },
          {
            "name": "coordinator",
            "type": "pubkey"
          },
          {
            "name": "evaluator",
            "type": "pubkey"
          },
          {
            "name": "authority_threshold",
            "docs": [
              "m-of-n multisig."
            ],
            "type": "u8"
          },
          {
            "name": "authority_signers",
            "type": {
              "vec": "pubkey"
            }
          },
          {
            "name": "experiment_id",
            "type": "string"
          },
          {
            "name": "manifest_hash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "analysis_container_digest",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "reward_curve_hash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "seed_commitment",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "mint",
            "type": "pubkey"
          },
          {
            "name": "vault",
            "type": "pubkey"
          },
          {
            "name": "budget_base_units",
            "type": "u64"
          },
          {
            "name": "challenge_bond_base_units",
            "type": "u64"
          },
          {
            "name": "freeze_by",
            "type": "i64"
          },
          {
            "name": "active_start",
            "type": "i64"
          },
          {
            "name": "active_end",
            "type": "i64"
          },
          {
            "name": "evaluation_deadline",
            "type": "i64"
          },
          {
            "name": "challenge_window_seconds",
            "type": "i64"
          },
          {
            "name": "claim_window_seconds",
            "type": "i64"
          },
          {
            "name": "cohort_published",
            "type": "bool"
          },
          {
            "name": "revealed_seed",
            "docs": [
              "Revealed once, after publish_cohort_root (freeze-before-reveal, Invariant 1)."
            ],
            "type": {
              "option": {
                "array": [
                  "u8",
                  32
                ]
              }
            }
          },
          {
            "name": "evaluation_valid",
            "docs": [
              "True iff a live, non-invalidated `Evaluation` is present (set at",
              "`submit_evaluation` / tx6, cleared to `false` by an upheld challenge / tx8).",
              "It is the sole `evaluation is finalizable` predicate (state-machine v1.1);",
              "starts `false` at create (no evaluation yet). Replaces the previous",
              "`evaluation_present`/`evaluation_invalidated` pair and the removed",
              "`ever_challenged` gate (security findings H2/M1)."
            ],
            "type": "bool"
          },
          {
            "name": "open_challenges",
            "docs": [
              "`open_challenges` is the SOLE gate for leaving `Challenged` (tx8). u32 count of",
              "unresolved `Challenge` accounts; checked_add/sub only."
            ],
            "type": "u32"
          },
          {
            "name": "challenge_window_end",
            "docs": [
              "Absolute unix ts written ONCE at `submit_evaluation` (tx6); the finalize window",
              "is defined only here so no earlier event can shorten it (security finding M1)."
            ],
            "type": "i64"
          },
          {
            "name": "claim_window_end",
            "type": "i64"
          },
          {
            "name": "aborted",
            "docs": [
              "Set only by `abort_experiment` (tx12). Marks a `Closed` experiment as aborted",
              "(pre-`Final` escape from the fund trap, security finding H1). No 8th status word."
            ],
            "type": "bool"
          },
          {
            "name": "created_at",
            "type": "i64"
          },
          {
            "name": "bump",
            "type": "u8"
          },
          {
            "name": "vault_bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "ExperimentStatus",
      "type": {
        "kind": "enum",
        "variants": [
          {
            "name": "Draft"
          },
          {
            "name": "Frozen"
          },
          {
            "name": "Active"
          },
          {
            "name": "Evaluating"
          },
          {
            "name": "Challenged"
          },
          {
            "name": "Final"
          },
          {
            "name": "Closed"
          }
        ]
      }
    }
  ]
};
