/**
 * Program IDL in camelCase format in order to be used in JS/TS.
 *
 * Note that this is only a type helper and is not the actual IDL. The original
 * IDL can be found at `target/idl/experiment_registry.json`.
 */
export type ExperimentRegistry = {
  "address": "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj",
  "metadata": {
    "name": "experimentRegistry",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol — experiment registry (frozen manifest hash, funding, status, windows, authorities, seed commitment/reveal)."
  },
  "instructions": [
    {
      "name": "createExperiment",
      "discriminator": [
        13,
        224,
        230,
        252,
        170,
        107,
        114,
        62
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  101,
                  120,
                  112,
                  101,
                  114,
                  105,
                  109,
                  101,
                  110,
                  116
                ]
              },
              {
                "kind": "arg",
                "path": "experimentIdHash"
              }
            ]
          }
        },
        {
          "name": "vault",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  118,
                  97,
                  117,
                  108,
                  116
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
          "name": "vaultAuthority"
        },
        {
          "name": "mint"
        },
        {
          "name": "coordinatorFunding",
          "writable": true
        },
        {
          "name": "coordinator",
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
        },
        {
          "name": "rent",
          "address": "SysvarRent111111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "experimentIdHash",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        },
        {
          "name": "args",
          "type": {
            "defined": {
              "name": "createExperimentArgs"
            }
          }
        }
      ]
    },
    {
      "name": "freezeExperiment",
      "docs": [
        "Freeze: record the manifest hash and lock the immutability set. Multisig only."
      ],
      "discriminator": [
        4,
        37,
        6,
        21,
        71,
        129,
        51,
        26
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        }
      ],
      "args": [
        {
          "name": "manifestHash",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        }
      ]
    },
    {
      "name": "initProtocolConfig",
      "discriminator": [
        91,
        97,
        211,
        137,
        96,
        222,
        139,
        40
      ],
      "accounts": [
        {
          "name": "protocolConfig",
          "writable": true,
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
            ]
          }
        },
        {
          "name": "admin",
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
          "name": "schemaVersion",
          "type": "u16"
        },
        {
          "name": "evidenceProgram",
          "type": "pubkey"
        },
        {
          "name": "settlementProgram",
          "type": "pubkey"
        },
        {
          "name": "challengeProgram",
          "type": "pubkey"
        }
      ]
    },
    {
      "name": "markChallenged",
      "docs": [
        "Evaluating|Challenged -> Challenged; increments open_challenges. Challenge program only."
      ],
      "discriminator": [
        88,
        18,
        123,
        227,
        101,
        198,
        104,
        240
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "markClosed",
      "docs": [
        "Final -> Closed. Settlement only."
      ],
      "discriminator": [
        45,
        161,
        251,
        138,
        89,
        105,
        161,
        213
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "markEvaluating",
      "docs": [
        "Active -> Evaluating (or re-Evaluating after an upheld challenge). Settlement only."
      ],
      "discriminator": [
        123,
        80,
        48,
        35,
        45,
        46,
        101,
        41
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": [
        {
          "name": "challengeWindowEnd",
          "type": "i64"
        }
      ]
    },
    {
      "name": "markFinal",
      "docs": [
        "Evaluating|Challenged -> Final. Settlement only."
      ],
      "discriminator": [
        76,
        133,
        127,
        13,
        232,
        42,
        56,
        110
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": [
        {
          "name": "claimWindowEnd",
          "type": "i64"
        }
      ]
    },
    {
      "name": "publishCohortRoot",
      "docs": [
        "Publish the assignment/cohort Merkle root. Coordinator only. Frozen -> Active.",
        "Commits the assignment BEFORE the seed can be revealed (freeze-before-reveal)."
      ],
      "discriminator": [
        118,
        32,
        113,
        158,
        76,
        119,
        184,
        92
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "cohortSet",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  111,
                  104,
                  111,
                  114,
                  116,
                  95,
                  115,
                  101,
                  116
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
          "name": "cohortRoot",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        },
        {
          "name": "cohortCount",
          "type": "u32"
        }
      ]
    },
    {
      "name": "resolveDismissed",
      "docs": [
        "Resolve a challenge as DISMISSED: decrement open_challenges; stay Challenged. Challenge only."
      ],
      "discriminator": [
        124,
        35,
        220,
        214,
        9,
        19,
        156,
        78
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "resolveUpheld",
      "docs": [
        "Resolve a challenge as UPHELD: evaluation invalidated, back to Evaluating. Challenge only."
      ],
      "discriminator": [
        206,
        246,
        46,
        106,
        59,
        37,
        207,
        142
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "callerAuthority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "revealSeed",
      "docs": [
        "Reveal the seed. Coordinator only. Verifies the commitment on-chain (Invariant 1)."
      ],
      "discriminator": [
        196,
        119,
        194,
        112,
        156,
        211,
        239,
        105
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
            ]
          }
        },
        {
          "name": "experiment",
          "writable": true
        },
        {
          "name": "coordinator",
          "signer": true
        }
      ],
      "args": [
        {
          "name": "seed",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        }
      ]
    },
    {
      "name": "setPaused",
      "docs": [
        "Emergency pause / unpause. Admin only. Cannot rewrite any frozen record — it",
        "merely blocks advancing instructions (Invariant: constrained authority)."
      ],
      "discriminator": [
        91,
        60,
        125,
        192,
        176,
        225,
        166,
        218
      ],
      "accounts": [
        {
          "name": "protocolConfig",
          "writable": true,
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
            ]
          }
        },
        {
          "name": "admin",
          "signer": true,
          "relations": [
            "protocolConfig"
          ]
        }
      ],
      "args": [
        {
          "name": "paused",
          "type": "bool"
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "cohortSet",
      "discriminator": [
        64,
        195,
        102,
        70,
        12,
        143,
        224,
        5
      ]
    },
    {
      "name": "experiment",
      "discriminator": [
        93,
        88,
        219,
        4,
        130,
        32,
        125,
        30
      ]
    },
    {
      "name": "protocolConfig",
      "discriminator": [
        207,
        91,
        250,
        28,
        152,
        179,
        215,
        209
      ]
    }
  ],
  "events": [
    {
      "name": "cohortRootPublished",
      "discriminator": [
        40,
        59,
        233,
        244,
        46,
        71,
        12,
        234
      ]
    },
    {
      "name": "experimentCreated",
      "discriminator": [
        161,
        226,
        80,
        112,
        20,
        207,
        145,
        214
      ]
    },
    {
      "name": "experimentFrozen",
      "discriminator": [
        161,
        60,
        140,
        4,
        107,
        48,
        7,
        184
      ]
    },
    {
      "name": "protocolInitialized",
      "discriminator": [
        173,
        122,
        168,
        254,
        9,
        118,
        76,
        132
      ]
    },
    {
      "name": "seedRevealed",
      "discriminator": [
        28,
        28,
        203,
        69,
        255,
        141,
        240,
        236
      ]
    },
    {
      "name": "statusTransitioned",
      "discriminator": [
        75,
        47,
        160,
        112,
        65,
        59,
        42,
        22
      ]
    }
  ],
  "errors": [
    {
      "code": 6000,
      "name": "notDevnet",
      "msg": "Protocol config cluster is not devnet (Invariant 7)"
    },
    {
      "code": 6001,
      "name": "feeNotZero",
      "msg": "Fee must be hard-zero (Invariant 7)"
    },
    {
      "code": 6002,
      "name": "paused",
      "msg": "Protocol is paused (emergency)"
    },
    {
      "code": 6003,
      "name": "wrongStatus",
      "msg": "Experiment is not in the required status for this transition"
    },
    {
      "code": 6004,
      "name": "unauthorized",
      "msg": "Signer is not authorized for this action"
    },
    {
      "code": 6005,
      "name": "multisigThresholdNotMet",
      "msg": "Multisig threshold not met"
    },
    {
      "code": 6006,
      "name": "invalidMultisig",
      "msg": "Invalid multisig configuration"
    },
    {
      "code": 6007,
      "name": "invalidExperimentId",
      "msg": "experiment_id is empty or too long"
    },
    {
      "code": 6008,
      "name": "invalidWindowOrdering",
      "msg": "Window ordering invalid: require active_start <= active_end <= evaluation_deadline"
    },
    {
      "code": 6009,
      "name": "freezeDeadlinePassed",
      "msg": "freeze_by is in the past"
    },
    {
      "code": 6010,
      "name": "freezeWindowClosed",
      "msg": "Freeze deadline has passed; cannot freeze"
    },
    {
      "code": 6011,
      "name": "seedCommitmentMismatch",
      "msg": "Revealed seed does not open the frozen seed commitment (Invariant 1)"
    },
    {
      "code": 6012,
      "name": "seedAlreadyRevealed",
      "msg": "Seed already revealed; assignment cannot be re-chosen"
    },
    {
      "code": 6013,
      "name": "cohortAlreadyPublished",
      "msg": "Cohort root already published"
    },
    {
      "code": 6014,
      "name": "cohortNotPublished",
      "msg": "Seed must be revealed only after the cohort root is published"
    },
    {
      "code": 6015,
      "name": "unauthorizedCaller",
      "msg": "Caller program is not the registered authority for this transition"
    },
    {
      "code": 6016,
      "name": "evaluationInvalidated",
      "msg": "Evaluation was invalidated by an upheld challenge; resubmit required"
    },
    {
      "code": 6017,
      "name": "challengeWindowNotElapsed",
      "msg": "Challenge window has not elapsed and challenges remain unresolved"
    },
    {
      "code": 6018,
      "name": "openChallengesRemain",
      "msg": "Open challenges remain unresolved"
    },
    {
      "code": 6019,
      "name": "claimWindowNotElapsed",
      "msg": "Claim window has not elapsed"
    },
    {
      "code": 6020,
      "name": "mathOverflow",
      "msg": "Checked arithmetic overflow"
    },
    {
      "code": 6021,
      "name": "invalidThreshold",
      "msg": "Threshold must be >= 1 and <= number of signers"
    },
    {
      "code": 6022,
      "name": "mintMismatch",
      "msg": "Vault mint does not match experiment mint"
    }
  ],
  "types": [
    {
      "name": "cohortRootPublished",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "cohortRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "cohortCount",
            "type": "u32"
          }
        ]
      }
    },
    {
      "name": "cohortSet",
      "docs": [
        "Assignment/cohort commitment. Published BEFORE the seed is revealed."
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "cohortRoot",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "cohortCount",
            "type": "u32"
          },
          {
            "name": "bump",
            "type": "u8"
          }
        ]
      }
    },
    {
      "name": "createExperimentArgs",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experimentId",
            "type": "string"
          },
          {
            "name": "evaluator",
            "type": "pubkey"
          },
          {
            "name": "authorityThreshold",
            "type": "u8"
          },
          {
            "name": "authoritySigners",
            "type": {
              "vec": "pubkey"
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
      "name": "experimentCreated",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "experimentId",
            "type": "string"
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
            "name": "seedCommitment",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "budgetBaseUnits",
            "type": "u64"
          }
        ]
      }
    },
    {
      "name": "experimentFrozen",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "manifestHash",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
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
      "name": "protocolInitialized",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "admin",
            "type": "pubkey"
          },
          {
            "name": "schemaVersion",
            "type": "u16"
          }
        ]
      }
    },
    {
      "name": "seedRevealed",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
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
            "name": "revealedSeed",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          }
        ]
      }
    },
    {
      "name": "statusTransitioned",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "from",
            "type": "u8"
          },
          {
            "name": "to",
            "type": "u8"
          },
          {
            "name": "callerProgram",
            "type": "pubkey"
          }
        ]
      }
    }
  ]
};
