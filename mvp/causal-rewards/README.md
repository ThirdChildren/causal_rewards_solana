# Causal Rewards Protocol

Open-source **measurement and settlement layer for Solana DePIN networks**. Beyond proof of
contribution and quality/scarcity scoring, this protocol asks one more question before
settlement: **did a contribution cause measurable additional value versus a credible
counterfactual?** ("Proof of Additionality" — a product concept, not a cryptographic claim.)

## MVP workflow

freeze experiment → assign cohorts from committed seed → anchor evidence batches →
estimate causal effect with uncertainty → compile conservative reward distribution →
settle claims on Solana.

Raw telemetry stays off-chain. Solana stores only manifest hash, commitments, result
hashes, reward root, and dispute state.

## Non-negotiable invariants

1. **Freeze before reveal** — manifest frozen + hashed before seed reveal and before any outcome analysis.
2. **Determinism / reproducibility** — same inputs reproduce exact roots. Primary acceptance criterion.
3. **Conservative payouts** — reward uses lower confidence bound; `max(0, effect - crit*se)`.
4. **Cohort-level estimand** — unit is geographic cohort within time block, never a device.
5. **Data minimization** — on-chain = hashes/roots/summaries/claim state only.
6. **Chain verifies process, not truth** — code enforces commitments; causal claim validity rests on design/data/assumptions.
7. **Devnet only** — no mainnet, no token, no fee, no production budget custody.
8. **Null results are valid** — publish scenarios where causal allocation does not beat baseline.

## Repository layout

| Path | Purpose | License |
|------|---------|---------|
| `programs/` | Solana (Anchor/Rust) on-chain programs | Apache-2.0 |
| `sdk/` | TypeScript + Python client SDKs | MIT |
| `causal-engine/` | Estimators, uncertainty, reward compiler | MIT |
| `simulator/` | Configurable DePIN simulator | MIT |
| `verifier-cli/` | Independent root-reproduction oracle | Apache-2.0 |
| `dashboard/` | Public web app + audit export | Apache-2.0 |
| `examples/` | Reference pilot wiring | Apache-2.0 |
| `specs/` | Spec, schemas, state machine, threat model, reward policy | Apache-2.0 |
| `test-vectors/` | Deterministic golden vectors | Apache-2.0 |
| `docs/` | Integration guide, benchmark report, dev docs | Apache-2.0 |

## Milestones (acceptance-gated)

- **M1 (wk 1–4)** Spec & benchmark — frozen public spec + reproducible baseline run.
- **M2 (wk 5–9)** Programs & SDK — devnet deploy + integration tests + assignment vectors.
- **M3 (wk 10–14)** Evidence & causal engine — independent reproduction of result + reward roots.
- **M4 (wk 15–20)** Pilot, hardening, release — tagged release + dashboard + benchmark report.

No milestone starts until the prior milestone's acceptance test passes. Frozen M1 spec is a
hard dependency for M2/M3. `specs/` wins over any individual implementation.

## Licensing

Apache-2.0 for protocol code; MIT for SDKs and analysis libraries. See each directory's
README and per-directory `LICENSE` notes.
