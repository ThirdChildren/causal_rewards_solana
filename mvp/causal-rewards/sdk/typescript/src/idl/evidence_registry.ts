/**
 * Program IDL in camelCase format in order to be used in JS/TS.
 *
 * Note that this is only a type helper and is not the actual IDL. The original
 * IDL can be found at `target/idl/evidence_registry.json`.
 */
export type EvidenceRegistry = {
  "address": "Ex82ncHsgc4ZFWDYQQzwR96GNNnKd3YmoULnjWgb1neP",
  "metadata": {
    "name": "evidenceRegistry",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol — evidence registry (per-epoch batch roots, time ranges, signer commitments, aggregate counts)."
  },
  "instructions": [
    {
      "name": "postEvidenceEpoch",
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
          "name": "evidenceEpoch",
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
                "path": "epochIndex"
              }
            ]
          }
        },
        {
          "name": "prevEpoch"
        },
        {
          "name": "coordinator",
          "writable": true,
          "signer": true
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "epochIndex",
          "type": "u64"
        },
        {
          "name": "args",
          "type": {
            "defined": {
              "name": "evidenceEpochArgs"
            }
          }
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "evidenceEpoch",
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
      "name": "evidenceEpochPosted",
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
      "name": "wrongStatus",
      "msg": "Experiment is not Active"
    },
    {
      "code": 6001,
      "name": "unauthorized",
      "msg": "Signer is not the coordinator"
    },
    {
      "code": 6002,
      "name": "invalidCohortId",
      "msg": "cohort_id empty or too long"
    },
    {
      "code": 6003,
      "name": "invalidTimeRange",
      "msg": "time_range invalid: require start < end"
    },
    {
      "code": 6004,
      "name": "timeRangeOutsideActiveWindow",
      "msg": "time_range outside the active window"
    },
    {
      "code": 6005,
      "name": "inconsistentCounts",
      "msg": "distinct_signers exceeds total observation count"
    },
    {
      "code": 6006,
      "name": "prevEpochMissing",
      "msg": "previous epoch does not exist (epochs must be monotonic, no gaps)"
    },
    {
      "code": 6007,
      "name": "mathOverflow",
      "msg": "Checked arithmetic overflow"
    }
  ],
  "types": [
    {
      "name": "evidenceEpoch",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "epochIndex",
            "type": "u64"
          },
          {
            "name": "cohortId",
            "type": "string"
          },
          {
            "name": "timeStart",
            "type": "i64"
          },
          {
            "name": "timeEnd",
            "type": "i64"
          },
          {
            "name": "signerSetRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observationsRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "acceptedCount",
            "type": "u64"
          },
          {
            "name": "rejectedCount",
            "type": "u64"
          },
          {
            "name": "distinctSigners",
            "type": "u64"
          },
          {
            "name": "contentHash",
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
      "name": "evidenceEpochArgs",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "cohortId",
            "type": "string"
          },
          {
            "name": "timeStart",
            "type": "i64"
          },
          {
            "name": "timeEnd",
            "type": "i64"
          },
          {
            "name": "signerSetRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observationsRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "acceptedCount",
            "type": "u64"
          },
          {
            "name": "rejectedCount",
            "type": "u64"
          },
          {
            "name": "distinctSigners",
            "type": "u64"
          },
          {
            "name": "contentHash",
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
      "name": "evidenceEpochPosted",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "epochIndex",
            "type": "u64"
          },
          {
            "name": "cohortId",
            "type": "string"
          },
          {
            "name": "timeStart",
            "type": "i64"
          },
          {
            "name": "timeEnd",
            "type": "i64"
          },
          {
            "name": "signerSetRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "observationsRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "acceptedCount",
            "type": "u64"
          }
        ]
      }
    },
    {
      "name": "experiment",
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
                "name": "experimentStatus"
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
            "name": "authorityThreshold",
            "docs": [
              "m-of-n multisig."
            ],
            "type": "u8"
          },
          {
            "name": "authoritySigners",
            "type": {
              "vec": "pubkey"
            }
          },
          {
            "name": "experimentId",
            "type": "string"
          },
          {
            "name": "manifestHash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "analysisContainerDigest",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "rewardCurveHash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "seedCommitment",
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
            "name": "budgetBaseUnits",
            "type": "u64"
          },
          {
            "name": "challengeBondBaseUnits",
            "type": "u64"
          },
          {
            "name": "freezeBy",
            "type": "i64"
          },
          {
            "name": "activeStart",
            "type": "i64"
          },
          {
            "name": "activeEnd",
            "type": "i64"
          },
          {
            "name": "evaluationDeadline",
            "type": "i64"
          },
          {
            "name": "challengeWindowSeconds",
            "type": "i64"
          },
          {
            "name": "claimWindowSeconds",
            "type": "i64"
          },
          {
            "name": "cohortPublished",
            "type": "bool"
          },
          {
            "name": "revealedSeed",
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
            "name": "evaluationPresent",
            "type": "bool"
          },
          {
            "name": "evaluationInvalidated",
            "type": "bool"
          },
          {
            "name": "everChallenged",
            "type": "bool"
          },
          {
            "name": "openChallenges",
            "type": "u32"
          },
          {
            "name": "challengeWindowEnd",
            "type": "i64"
          },
          {
            "name": "claimWindowEnd",
            "type": "i64"
          },
          {
            "name": "createdAt",
            "type": "i64"
          },
          {
            "name": "bump",
            "type": "u8"
          },
          {
            "name": "vaultBump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "experimentStatus",
      "type": {
        "kind": "enum",
        "variants": [
          {
            "name": "draft"
          },
          {
            "name": "frozen"
          },
          {
            "name": "active"
          },
          {
            "name": "evaluating"
          },
          {
            "name": "challenged"
          },
          {
            "name": "final"
          },
          {
            "name": "closed"
          }
        ]
      }
    }
  ]
};
