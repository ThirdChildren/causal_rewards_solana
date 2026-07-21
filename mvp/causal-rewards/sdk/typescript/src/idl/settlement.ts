/**
 * Program IDL in camelCase format in order to be used in JS/TS.
 *
 * Note that this is only a type helper and is not the actual IDL. The original
 * IDL can be found at `target/idl/settlement.json`.
 */
export type Settlement = {
  "address": "4YGzmSUZYxYQMJ4E9YiM7h8dv4KChVEKHuN5T2W5qn86",
  "metadata": {
    "name": "settlement",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol — settlement (evaluation, finalized reward root, single-use Merkle claims, unused-budget recovery). Fees hard-zero."
  },
  "instructions": [
    {
      "name": "claimReward",
      "discriminator": [
        149,
        95,
        181,
        242,
        94,
        90,
        158,
        162
      ],
      "accounts": [
        {
          "name": "experiment",
          "relations": [
            "distribution"
          ]
        },
        {
          "name": "distribution",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  100,
                  105,
                  115,
                  116,
                  114,
                  105,
                  98,
                  117,
                  116,
                  105,
                  111,
                  110
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "claimReceipt",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  108,
                  97,
                  105,
                  109
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              },
              {
                "kind": "arg",
                "path": "leafIndex"
              }
            ]
          }
        },
        {
          "name": "vault",
          "writable": true
        },
        {
          "name": "vaultAuthority",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  118,
                  97,
                  117,
                  108,
                  116,
                  95,
                  97,
                  117,
                  116,
                  104,
                  111,
                  114,
                  105,
                  116,
                  121
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "recipientToken",
          "writable": true
        },
        {
          "name": "recipient",
          "writable": true,
          "signer": true
        },
        {
          "name": "tokenProgram",
          "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "leafIndex",
          "type": "u64"
        },
        {
          "name": "amountBaseUnits",
          "type": "u64"
        },
        {
          "name": "proof",
          "type": {
            "vec": {
              "defined": {
                "name": "claimProofStep"
              }
            }
          }
        }
      ]
    },
    {
      "name": "closeExperiment",
      "discriminator": [
        147,
        221,
        173,
        207,
        48,
        170,
        121,
        8
      ],
      "accounts": [
        {
          "name": "protocolConfig",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  112,
                  114,
                  111,
                  116,
                  111,
                  99,
                  111,
                  108,
                  95,
                  99,
                  111,
                  110,
                  102,
                  105,
                  103
                ]
              }
            ],
            "program": {
              "kind": "account",
              "path": "experimentRegistryProgram"
            }
          }
        },
        {
          "name": "experiment",
          "writable": true,
          "relations": [
            "distribution"
          ]
        },
        {
          "name": "distribution",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  100,
                  105,
                  115,
                  116,
                  114,
                  105,
                  98,
                  117,
                  116,
                  105,
                  111,
                  110
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "vault",
          "writable": true
        },
        {
          "name": "vaultAuthority",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  118,
                  97,
                  117,
                  108,
                  116,
                  95,
                  97,
                  117,
                  116,
                  104,
                  111,
                  114,
                  105,
                  116,
                  121
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "recoveryToken",
          "writable": true
        },
        {
          "name": "cpiAuthority",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  112,
                  105,
                  95,
                  97,
                  117,
                  116,
                  104,
                  111,
                  114,
                  105,
                  116,
                  121
                ]
              }
            ]
          }
        },
        {
          "name": "cranker",
          "writable": true,
          "signer": true
        },
        {
          "name": "experimentRegistryProgram",
          "address": "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj"
        },
        {
          "name": "tokenProgram",
          "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        }
      ],
      "args": []
    },
    {
      "name": "finalizeDistribution",
      "discriminator": [
        12,
        246,
        59,
        197,
        66,
        128,
        169,
        197
      ],
      "accounts": [
        {
          "name": "protocolConfig",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  112,
                  114,
                  111,
                  116,
                  111,
                  99,
                  111,
                  108,
                  95,
                  99,
                  111,
                  110,
                  102,
                  105,
                  103
                ]
              }
            ],
            "program": {
              "kind": "account",
              "path": "experimentRegistryProgram"
            }
          }
        },
        {
          "name": "experiment",
          "writable": true,
          "relations": [
            "evaluation"
          ]
        },
        {
          "name": "evaluation",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  118,
                  97,
                  108,
                  117,
                  97,
                  116,
                  105,
                  111,
                  110
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "distribution",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  100,
                  105,
                  115,
                  116,
                  114,
                  105,
                  98,
                  117,
                  116,
                  105,
                  111,
                  110
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "cpiAuthority",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  112,
                  105,
                  95,
                  97,
                  117,
                  116,
                  104,
                  111,
                  114,
                  105,
                  116,
                  121
                ]
              }
            ]
          }
        },
        {
          "name": "finalizer",
          "writable": true,
          "signer": true
        },
        {
          "name": "experimentRegistryProgram",
          "address": "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj"
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "totalAllocatedBaseUnits",
          "type": "u64"
        }
      ]
    },
    {
      "name": "submitEvaluation",
      "discriminator": [
        216,
        88,
        152,
        86,
        73,
        107,
        153,
        93
      ],
      "accounts": [
        {
          "name": "protocolConfig",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  112,
                  114,
                  111,
                  116,
                  111,
                  99,
                  111,
                  108,
                  95,
                  99,
                  111,
                  110,
                  102,
                  105,
                  103
                ]
              }
            ],
            "program": {
              "kind": "account",
              "path": "experimentRegistryProgram"
            }
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "evaluation",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  118,
                  97,
                  108,
                  117,
                  97,
                  116,
                  105,
                  111,
                  110
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              }
            ]
          }
        },
        {
          "name": "epochZero"
        },
        {
          "name": "cpiAuthority",
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  112,
                  105,
                  95,
                  97,
                  117,
                  116,
                  104,
                  111,
                  114,
                  105,
                  116,
                  121
                ]
              }
            ]
          }
        },
        {
          "name": "evaluator",
          "writable": true,
          "signer": true
        },
        {
          "name": "experimentRegistryProgram",
          "address": "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj"
        },
        {
          "name": "systemProgram",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "resultArtifactHash",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        },
        {
          "name": "rewardRoot",
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
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "claimReceipt",
      "discriminator": [
        223,
        233,
        11,
        229,
        124,
        165,
        207,
        28
      ]
    },
    {
      "name": "distribution",
      "discriminator": [
        176,
        85,
        17,
        11,
        13,
        194,
        18,
        1
      ]
    },
    {
      "name": "evaluation",
      "discriminator": [
        212,
        70,
        25,
        106,
        239,
        24,
        93,
        220
      ]
    }
  ],
  "events": [
    {
      "name": "distributionFinalized",
      "discriminator": [
        232,
        198,
        127,
        113,
        61,
        16,
        158,
        22
      ]
    },
    {
      "name": "evaluationSubmitted",
      "discriminator": [
        255,
        99,
        101,
        136,
        239,
        201,
        85,
        182
      ]
    },
    {
      "name": "experimentClosed",
      "discriminator": [
        39,
        4,
        20,
        205,
        110,
        68,
        248,
        245
      ]
    },
    {
      "name": "rewardClaimed",
      "discriminator": [
        49,
        28,
        87,
        84,
        158,
        48,
        229,
        175
      ]
    }
  ],
  "errors": [
    {
      "code": 6000,
      "name": "wrongStatus",
      "msg": "Experiment is not in the required status"
    },
    {
      "code": 6001,
      "name": "unauthorized",
      "msg": "Signer not authorized"
    },
    {
      "code": 6002,
      "name": "seedNotRevealed",
      "msg": "Seed has not been revealed"
    },
    {
      "code": 6003,
      "name": "activeWindowNotEnded",
      "msg": "Active window has not ended"
    },
    {
      "code": 6004,
      "name": "evaluationDeadlinePassed",
      "msg": "Evaluation deadline has passed"
    },
    {
      "code": 6005,
      "name": "containerDigestMismatch",
      "msg": "Echoed analysis_container_digest does not match the frozen one"
    },
    {
      "code": 6006,
      "name": "noEvidence",
      "msg": "No evidence epoch exists"
    },
    {
      "code": 6007,
      "name": "multisigThresholdNotMet",
      "msg": "Multisig threshold not met"
    },
    {
      "code": 6008,
      "name": "allocationExceedsBudget",
      "msg": "Allocation exceeds budget"
    },
    {
      "code": 6009,
      "name": "invalidMerkleProof",
      "msg": "Merkle proof of the reward leaf is invalid"
    },
    {
      "code": 6010,
      "name": "claimWindowClosed",
      "msg": "Claim window is closed"
    },
    {
      "code": 6011,
      "name": "claimWindowNotElapsed",
      "msg": "Claim window has not elapsed"
    },
    {
      "code": 6012,
      "name": "wrongVault",
      "msg": "Vault does not match experiment"
    },
    {
      "code": 6013,
      "name": "wrongExperiment",
      "msg": "Evaluation/Distribution does not belong to this experiment"
    },
    {
      "code": 6014,
      "name": "mintMismatch",
      "msg": "Token mint mismatch"
    },
    {
      "code": 6015,
      "name": "mathOverflow",
      "msg": "Checked arithmetic overflow"
    }
  ],
  "types": [
    {
      "name": "claimProofStep",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "sibling",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "siblingIsLeft",
            "docs": [
              "true => sibling is the LEFT node (self is the right child)."
            ],
            "type": "bool"
          }
        ]
      }
    },
    {
      "name": "claimReceipt",
      "docs": [
        "Single-use nullifier for one reward leaf."
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "leafIndex",
            "type": "u64"
          },
          {
            "name": "recipient",
            "type": "pubkey"
          },
          {
            "name": "amountBaseUnits",
            "type": "u64"
          },
          {
            "name": "bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "distribution",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "rewardRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "totalAllocatedBaseUnits",
            "type": "u64"
          },
          {
            "name": "unallocatedBaseUnits",
            "type": "u64"
          },
          {
            "name": "claimWindowEnd",
            "type": "i64"
          },
          {
            "name": "bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "distributionFinalized",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "rewardRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "totalAllocatedBaseUnits",
            "type": "u64"
          },
          {
            "name": "unallocatedBaseUnits",
            "type": "u64"
          },
          {
            "name": "claimWindowEnd",
            "type": "i64"
          }
        ]
      }
    },
    {
      "name": "evaluation",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "resultArtifactHash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "rewardRoot",
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
            "name": "evaluator",
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
      "name": "evaluationSubmitted",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "resultArtifactHash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "rewardRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "challengeWindowEnd",
            "type": "i64"
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
      "name": "experimentClosed",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "recoveredBaseUnits",
            "type": "u64"
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
    },
    {
      "name": "protocolConfig",
      "docs": [
        "Global config. Created once at program init."
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "admin",
            "type": "pubkey"
          },
          {
            "name": "feeBps",
            "docs": [
              "Hard-zero fee (Invariant 7). Asserted == 0 at init."
            ],
            "type": "u16"
          },
          {
            "name": "paused",
            "docs": [
              "Emergency pause: blocks state-advancing instructions. Cannot rewrite frozen records."
            ],
            "type": "bool"
          },
          {
            "name": "cluster",
            "docs": [
              "Devnet guard (Invariant 7). Must equal CLUSTER_DEVNET."
            ],
            "type": "u8"
          },
          {
            "name": "schemaVersion",
            "type": "u16"
          },
          {
            "name": "evidenceProgram",
            "docs": [
              "Registered satellite program ids authorized to advance Experiment.status via CPI."
            ],
            "type": "pubkey"
          },
          {
            "name": "settlementProgram",
            "type": "pubkey"
          },
          {
            "name": "challengeProgram",
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
      "name": "rewardClaimed",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "leafIndex",
            "type": "u64"
          },
          {
            "name": "recipient",
            "type": "pubkey"
          },
          {
            "name": "amountBaseUnits",
            "type": "u64"
          }
        ]
      }
    }
  ]
};
