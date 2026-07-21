/**
 * Program IDL in Anchor 0.30.1 native format (snake_case), regenerated from
 * the CURRENT published idl/experiment_registry.json. Pairs with new Program(<json>) at runtime.
 *
 * Auto-generated: do not edit by hand. Re-copy from idl/ when the program changes.
 */
export type ExperimentRegistry = {
  "address": "8DotPgXajgeHt68htC7vbuvScUDkQa9ZPi3a5Sk1mioj",
  "metadata": {
    "name": "experiment_registry",
    "version": "0.1.0",
    "spec": "0.1.0",
    "description": "Causal Rewards Protocol \u2014 experiment registry (frozen manifest hash, funding, status, windows, authorities, seed commitment/reveal)."
  },
  "instructions": [
    {
      "name": "create_experiment",
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
          "name": "protocol_config",
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
                "path": "experiment_id_hash"
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
          "name": "vault_authority"
        },
        {
          "name": "mint"
        },
        {
          "name": "coordinator_funding",
          "writable": true
        },
        {
          "name": "coordinator",
          "writable": true,
          "signer": true
        },
        {
          "name": "token_program",
          "address": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
        },
        {
          "name": "system_program",
          "address": "11111111111111111111111111111111"
        },
        {
          "name": "rent",
          "address": "SysvarRent111111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "experiment_id_hash",
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
              "name": "CreateExperimentArgs"
            }
          }
        }
      ]
    },
    {
      "name": "freeze_experiment",
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
          "name": "protocol_config",
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
          "name": "manifest_hash",
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
      "name": "init_protocol_config",
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
          "name": "protocol_config",
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
          "name": "system_program",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "schema_version",
          "type": "u16"
        },
        {
          "name": "evidence_program",
          "type": "pubkey"
        },
        {
          "name": "settlement_program",
          "type": "pubkey"
        },
        {
          "name": "challenge_program",
          "type": "pubkey"
        },
        {
          "name": "abort_grace_seconds",
          "type": "i64"
        }
      ]
    },
    {
      "name": "mark_aborted",
      "docs": [
        "tx12: {Frozen,Active,Evaluating,Challenged} -> Closed (`aborted = true`). Settlement only.",
        "",
        "The authorization gate (multisig OR permissionless timeout) and the vault return +",
        "still-open-bond refunds live in the settlement/challenge programs; this transition",
        "enforces only the legal status set and stamps the `aborted` marker. NOT gated on",
        "`paused` \u2014 abort is the bounded escape from the pre-`Final` fund trap (H1) and must",
        "remain reachable so funds can never be trapped by pausing."
      ],
      "discriminator": [
        169,
        22,
        33,
        5,
        212,
        202,
        207,
        169
      ],
      "accounts": [
        {
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "mark_challenged",
      "docs": [
        "tx7: Evaluating|Challenged -> Challenged; increments open_challenges. Challenge only."
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "mark_closed",
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "mark_evaluating",
      "docs": [
        "tx6: Active -> Evaluating (first submission) or Evaluating -> Evaluating",
        "(corrected re-submission after an upheld challenge). Settlement only.",
        "",
        "Writes the ABSOLUTE `challenge_window_end` once here (never derived elsewhere,",
        "so no earlier event can shorten it \u2014 security finding M1), sets",
        "`evaluation_valid = true`, and re-initializes `open_challenges = 0`."
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": [
        {
          "name": "challenge_window_end",
          "type": "i64"
        }
      ]
    },
    {
      "name": "mark_final",
      "docs": [
        "tx9: Evaluating -> Final. Settlement only.",
        "",
        "Guard (security finding M1): finalize is taken ONLY from `Evaluating` and requires",
        "the conjunction `now >= challenge_window_end AND open_challenges == 0 AND",
        "evaluation_valid`. There is no `ever_challenged` short-circuit."
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the SETTLEMENT program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": [
        {
          "name": "claim_window_end",
          "type": "i64"
        }
      ]
    },
    {
      "name": "publish_cohort_root",
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
          "name": "protocol_config",
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
          "name": "cohort_set",
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
          "name": "system_program",
          "address": "11111111111111111111111111111111"
        }
      ],
      "args": [
        {
          "name": "cohort_root",
          "type": {
            "array": [
              "u8",
              32
            ]
          }
        },
        {
          "name": "cohort_count",
          "type": "u32"
        }
      ]
    },
    {
      "name": "resolve_dismissed",
      "docs": [
        "tx8: resolve exactly ONE challenge as DISMISSED. Challenge only.",
        "",
        "Decrements `open_challenges` by 1 and leaves `evaluation_valid` untouched. State",
        "returns to `Evaluating` only when `open_challenges` reaches 0 (security finding H2);",
        "a dismissed challenge NEVER shortcuts the finalize window for a not-yet-opened",
        "honest challenge (security finding M1 \u2014 there is no `ever_challenged` flag)."
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "resolve_upheld",
      "docs": [
        "tx8: resolve exactly ONE challenge as UPHELD. Challenge only.",
        "",
        "`open_challenges` is the SOLE gate for leaving `Challenged` (security finding H2):",
        "this decrements the counter by 1 and sets `evaluation_valid = false` (an upheld",
        "resolution invalidates the evaluation regardless of order). State returns to",
        "`Evaluating` only when `open_challenges` reaches 0; otherwise it stays `Challenged`",
        "and every remaining challenge is still independently resolvable."
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
          "name": "protocol_config",
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
          "name": "caller_authority",
          "docs": [
            "Authorizes the caller: PDA of the CHALLENGE program signs this CPI."
          ],
          "signer": true
        }
      ],
      "args": []
    },
    {
      "name": "reveal_seed",
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
          "name": "protocol_config",
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
      "name": "set_paused",
      "docs": [
        "Emergency pause / unpause. Admin only. Cannot rewrite any frozen record \u2014 it",
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
          "name": "protocol_config",
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
            "protocol_config"
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
      "name": "CohortSet",
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
      "name": "Experiment",
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
      "name": "ProtocolConfig",
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
      "name": "CohortRootPublished",
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
      "name": "ExperimentAborted",
      "discriminator": [
        191,
        142,
        47,
        239,
        108,
        171,
        159,
        5
      ]
    },
    {
      "name": "ExperimentCreated",
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
      "name": "ExperimentFrozen",
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
      "name": "ProtocolInitialized",
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
      "name": "SeedRevealed",
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
      "name": "StatusTransitioned",
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
      "name": "NotDevnet",
      "msg": "Protocol config cluster is not devnet (Invariant 7)"
    },
    {
      "code": 6001,
      "name": "FeeNotZero",
      "msg": "Fee must be hard-zero (Invariant 7)"
    },
    {
      "code": 6002,
      "name": "Paused",
      "msg": "Protocol is paused (emergency)"
    },
    {
      "code": 6003,
      "name": "WrongStatus",
      "msg": "Experiment is not in the required status for this transition"
    },
    {
      "code": 6004,
      "name": "Unauthorized",
      "msg": "Signer is not authorized for this action"
    },
    {
      "code": 6005,
      "name": "MultisigThresholdNotMet",
      "msg": "Multisig threshold not met"
    },
    {
      "code": 6006,
      "name": "InvalidMultisig",
      "msg": "Invalid multisig configuration"
    },
    {
      "code": 6007,
      "name": "InvalidExperimentId",
      "msg": "experiment_id is empty or too long"
    },
    {
      "code": 6008,
      "name": "InvalidWindowOrdering",
      "msg": "Window ordering invalid: require active_start <= active_end <= evaluation_deadline"
    },
    {
      "code": 6009,
      "name": "FreezeDeadlinePassed",
      "msg": "freeze_by is in the past"
    },
    {
      "code": 6010,
      "name": "FreezeWindowClosed",
      "msg": "Freeze deadline has passed; cannot freeze"
    },
    {
      "code": 6011,
      "name": "SeedCommitmentMismatch",
      "msg": "Revealed seed does not open the frozen seed commitment (Invariant 1)"
    },
    {
      "code": 6012,
      "name": "SeedAlreadyRevealed",
      "msg": "Seed already revealed; assignment cannot be re-chosen"
    },
    {
      "code": 6013,
      "name": "CohortAlreadyPublished",
      "msg": "Cohort root already published"
    },
    {
      "code": 6014,
      "name": "CohortNotPublished",
      "msg": "Seed must be revealed only after the cohort root is published"
    },
    {
      "code": 6015,
      "name": "UnauthorizedCaller",
      "msg": "Caller program is not the registered authority for this transition"
    },
    {
      "code": 6016,
      "name": "EvaluationNotValid",
      "msg": "Evaluation is not valid (never submitted, or invalidated by an upheld challenge; resubmit required)"
    },
    {
      "code": 6017,
      "name": "ChallengeWindowNotElapsed",
      "msg": "Challenge window has not elapsed"
    },
    {
      "code": 6018,
      "name": "OpenChallengesRemain",
      "msg": "Open challenges remain unresolved"
    },
    {
      "code": 6019,
      "name": "ClaimWindowNotElapsed",
      "msg": "Claim window has not elapsed"
    },
    {
      "code": 6020,
      "name": "MathOverflow",
      "msg": "Checked arithmetic overflow"
    },
    {
      "code": 6021,
      "name": "InvalidThreshold",
      "msg": "Threshold must be >= 1 and <= number of signers"
    },
    {
      "code": 6022,
      "name": "MintMismatch",
      "msg": "Vault mint does not match experiment mint"
    },
    {
      "code": 6023,
      "name": "AbortNotAllowed",
      "msg": "abort_experiment is only reachable from a pre-Final state (Frozen/Active/Evaluating/Challenged)"
    },
    {
      "code": 6024,
      "name": "AlreadyAborted",
      "msg": "Experiment already aborted"
    }
  ],
  "types": [
    {
      "name": "CohortRootPublished",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "cohort_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "cohort_count",
            "type": "u32"
          }
        ]
      }
    },
    {
      "name": "CohortSet",
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
            "name": "cohort_root",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "cohort_count",
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
      "name": "CreateExperimentArgs",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment_id",
            "type": "string"
          },
          {
            "name": "evaluator",
            "type": "pubkey"
          },
          {
            "name": "authority_threshold",
            "type": "u8"
          },
          {
            "name": "authority_signers",
            "type": {
              "vec": "pubkey"
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
      "name": "ExperimentAborted",
      "docs": [
        "Emitted when `abort_experiment` (tx12) drives a pre-`Final` experiment to",
        "`Closed` with `aborted = true` (security finding H1)."
      ],
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "from",
            "docs": [
              "Status the experiment was in immediately before abort."
            ],
            "type": "u8"
          },
          {
            "name": "open_challenges",
            "docs": [
              "Open challenges recorded at abort time (their bonds are refundable via the",
              "challenge program's `refund_bond` crank)."
            ],
            "type": "u32"
          }
        ]
      }
    },
    {
      "name": "ExperimentCreated",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "experiment_id",
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
            "name": "seed_commitment",
            "type": {
              "array": [
                "u8",
                32
              ]
            }
          },
          {
            "name": "budget_base_units",
            "type": "u64"
          }
        ]
      }
    },
    {
      "name": "ExperimentFrozen",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
          },
          {
            "name": "manifest_hash",
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
    },
    {
      "name": "ProtocolConfig",
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
            "name": "fee_bps",
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
            "name": "schema_version",
            "type": "u16"
          },
          {
            "name": "evidence_program",
            "docs": [
              "Registered satellite program ids authorized to advance Experiment.status via CPI."
            ],
            "type": "pubkey"
          },
          {
            "name": "settlement_program",
            "type": "pubkey"
          },
          {
            "name": "challenge_program",
            "type": "pubkey"
          },
          {
            "name": "abort_grace_seconds",
            "docs": [
              "Timeout offset (seconds) for the permissionless `abort_experiment` path",
              "(state-machine v1.1 tx12): abort is permissionlessly reachable once",
              "`now > evaluation_deadline + abort_grace_seconds`."
            ],
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
      "name": "ProtocolInitialized",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "admin",
            "type": "pubkey"
          },
          {
            "name": "schema_version",
            "type": "u16"
          }
        ]
      }
    },
    {
      "name": "SeedRevealed",
      "type": {
        "kind": "struct",
        "fields": [
          {
            "name": "experiment",
            "type": "pubkey"
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
            "name": "revealed_seed",
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
      "name": "StatusTransitioned",
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
            "name": "caller_program",
            "type": "pubkey"
          }
        ]
      }
    }
  ]
};
