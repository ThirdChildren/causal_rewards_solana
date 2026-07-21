/**
 * Program IDL in camelCase format in order to be used in JS/TS.
 *
 * Note that this is only a type helper and is not the actual IDL. The original
 * IDL can be found at `target/idl/challenge.json`.
 */
export type Challenge = {
  "address": "J9MfPYVhveHLLRnGBUiMxJqCLJP6s5ZUn7e5h3mnsG4z",
  "metadata": {
    "name": "challenge",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol — challenge (bond escrow, finality pause, resolution per frozen policy)."
  },
  "instructions": [
    {
      "name": "openChallenge",
      "discriminator": [
        56,
        176,
        3,
        12,
        28,
        205,
        10,
        5
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
          "name": "challenge",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  104,
                  97,
                  108,
                  108,
                  101,
                  110,
                  103,
                  101
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              },
              {
                "kind": "account",
                "path": "challenger"
              }
            ]
          }
        },
        {
          "name": "bondVault",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  98,
                  111,
                  110,
                  100,
                  95,
                  118,
                  97,
                  117,
                  108,
                  116
                ]
              },
              {
                "kind": "account",
                "path": "challenge"
              }
            ]
          }
        },
        {
          "name": "mint"
        },
        {
          "name": "challengerToken",
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
          "name": "challenger",
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
          "name": "reasonCode",
          "type": "u16"
        },
        {
          "name": "bondAmount",
          "type": "u64"
        }
      ]
    },
    {
      "name": "resolveChallenge",
      "docs": [
        "Resolve a challenge. Multisig-gated. `upheld = true` invalidates the evaluation",
        "and returns the bond; `upheld = false` dismisses and forfeits the bond."
      ],
      "discriminator": [
        81,
        191,
        124,
        119,
        131,
        248,
        157,
        109
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
            "challenge"
          ]
        },
        {
          "name": "challenge",
          "writable": true,
          "pda": {
            "seeds": [
              {
                "kind": "const",
                "value": [
                  99,
                  104,
                  97,
                  108,
                  108,
                  101,
                  110,
                  103,
                  101
                ]
              },
              {
                "kind": "account",
                "path": "experiment"
              },
              {
                "kind": "account",
                "path": "challenge.challenger",
                "account": "challenge"
              }
            ]
          }
        },
        {
          "name": "bondVault",
          "writable": true
        },
        {
          "name": "bondDestination",
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
          "name": "resolver",
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
      "args": [
        {
          "name": "upheld",
          "type": "bool"
        }
      ]
    }
  ],
  "accounts": [
    {
      "name": "challenge",
      "discriminator": [
        119,
        250,
        161,
        121,
        119,
        81,
        22,
        208
      ]
    }
  ],
  "events": [
    {
      "name": "challengeOpened",
      "discriminator": [
        42,
        83,
        165,
        62,
        80,
        17,
        63,
        181
      ]
    },
    {
      "name": "challengeResolved",
      "discriminator": [
        100,
        153,
        38,
        123,
        172,
        250,
        166,
        105
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
      "name": "noLiveEvaluation",
      "msg": "No live evaluation to challenge"
    },
    {
      "code": 6002,
      "name": "challengeWindowClosed",
      "msg": "Challenge window is closed"
    },
    {
      "code": 6003,
      "name": "bondTooLow",
      "msg": "Bond is below the required minimum"
    },
    {
      "code": 6004,
      "name": "alreadyResolved",
      "msg": "Challenge already resolved"
    },
    {
      "code": 6005,
      "name": "multisigThresholdNotMet",
      "msg": "Multisig threshold not met"
    },
    {
      "code": 6006,
      "name": "wrongBondDestination",
      "msg": "Bond destination owner is wrong for this resolution"
    },
    {
      "code": 6007,
      "name": "wrongBondVault",
      "msg": "Bond vault does not match challenge"
    },
    {
      "code": 6008,
      "name": "wrongExperiment",
      "msg": "Challenge does not belong to this experiment"
    },
    {
      "code": 6009,
      "name": "unauthorized",
      "msg": "Signer not authorized"
    },
    {
      "code": 6010,
      "name": "mintMismatch",
      "msg": "Token mint mismatch"
    }
  ],
  "types": [
    {
      "name": "challenge",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "challenger",
            "type": "pubkey"
          },
          {
            "name": "bondAmount",
            "type": "u64"
          },
          {
            "name": "reasonCode",
            "type": "u16"
          },
          {
            "name": "resolution",
            "type": "u8"
          },
          {
            "name": "bondVault",
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
      "name": "challengeOpened",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "challenger",
            "type": "pubkey"
          },
          {
            "name": "reasonCode",
            "type": "u16"
          },
          {
            "name": "bondAmount",
            "type": "u64"
          }
        ]
      }
    },
    {
      "name": "challengeResolved",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "challenger",
            "type": "pubkey"
          },
          {
            "name": "upheld",
            "type": "bool"
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
    }
  ]
};
