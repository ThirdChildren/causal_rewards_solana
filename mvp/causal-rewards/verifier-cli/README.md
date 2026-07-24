# verifier-cli/ — Independent reproducibility oracle (`crp-verify`)

Recomputes **every root** (manifest / assignment / evidence epoch / result-artifact / reward)
from an audit-bundle directory with **zero network access** and **no trust** in the coordinator
or evaluator. `roots.json` is treated as an *untrusted claim* to be reproduced, never as a
source of truth. This is the M3 acceptance oracle.

## Install

```
pip install -e .          # provides the `crp-verify` console command
```

The only runtime dependency is `pyarrow==18.1.0` (to read the Parquet transport); everything
hashed or root-derived flows through the single ratified encoder in `verifier-cli/reference/`
(the same bytes the on-chain programs, causal engine, backend and SDKs are checked against).
When running from an installed wheel outside the repo tree, point the verifier at the reference
encoder with `CRP_REFERENCE_DIR=/path/to/verifier-cli/reference`.

## Run

```
crp-verify <bundle-dir> [--seed <64-hex>] [--onchain <commitments.json>]
                        [--golden-manifest-hash <64-hex>] [--json]
```

* `--seed` — the on-chain revealed assignment seed. With it, the verifier re-derives **every
  arm** from the committed seed and confirms the seed opens the frozen commitment (invariant 1,
  freeze-before-reveal). Without it, the assignment root is still reproduced from the published
  leaves (structural leg).
* `--onchain` — a JSON map of on-chain anchored commitments (`manifest_hash`, `cohort_root` /
  `assignment_root`, `reward_root`, `result_artifact_hash`). The reproduced roots must equal the
  anchors — this catches a self-consistent but **substituted** bundle.

Exit code is `0` only if no check FAILED (`SKIP` is not a failure); any divergence exits
non-zero and the report localizes the **first point of divergence** (field, expected, got).
Output reads no wall-clock and no RNG, so two runs on the same bundle emit byte-identical bytes.

## Audit bundle inputs

`manifest.json`, `participants.parquet`, `assignment.parquet`, `evidence/*.parquet`,
`analysis.json`, `rewards.parquet`, `roots.json`, `provenance.json` (excluded from hashes).

## What it checks (in order)

| Check | Reproduces | Rejects |
|---|---|---|
| `manifest_hash` | `SHA-256(CJSON(manifest.json))` | tampered manifest; non-canonical storage |
| `assignment_root` | leaf `CJSON({arm,cohort_id})` → Merkle root; arms from `--seed` | invalid seed reveal; non-canonical row order; hand-picked arms |
| `evidence_epoch_roots` | each epoch from published leaf hashes | duplicate/replayed leaf; non-ascending leaves; non-monotonic epoch index |
| `result_artifact_hash` | `SHA-256(CJSON(analysis.json))` + evidence↔result seam | cooked result; seam break; stale container digest |
| `reward_root` | every §6.6 reward leaf + the root | substituted reward set; duplicate recipient; leaf-index gap |
| `onchain_commitments` | reproduced roots vs on-chain anchors | substituted (but self-consistent) bundle |

## Fixtures & tests

* `fixtures/build_golden_bundle.py` assembles a **real** bundle from the ratified
  `test-vectors/` (manifest `74e0bb82…`, assignment `c229b5cc…`, evidence-01 `a13e1cdc…`,
  reward-01 `a9c35cf4…`); `crp-verify fixtures/bundles/golden-happy` passes every check.
* `tests/` covers the happy path, the full golden-root set (evidence-01/02/03, reward-01/02/03,
  reproduced via the reference oracle), determinism (byte-identical verdicts), and adversarial
  rejection (tampered/substituted/seam-broken bundles + the shared `adv-01..06` fixtures).

## License

Apache-2.0.
