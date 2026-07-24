---
name: verifier-cli-architecture
description: How the crp-verify CLI is wired — single encoder bridge, check order, exit codes, the real fixture bundle, offline install path
metadata:
  type: project
---

The M3 verifier lives in `mvp/causal-rewards/verifier-cli/`. Completed on the committed
partial (checks.py/bundle.py/_ref.py were already there).

**Single-encoder rule (load-bearing).** All canonical/Merkle/leaf/derivation goes through
`verifier-cli/reference/` via `src/crp_verifier/_ref.py`. NEVER re-implement crypto in the
verifier — drift is impossible by construction only if this holds. `_ref` prepends the
reference dir to sys.path; override with `CRP_REFERENCE_DIR` for wheel installs.

**Layout added:** `src/crp_verifier/{__init__,cli,adversarial}.py`, `pyproject.toml`
(only runtime dep `pyarrow==18.1.0`, console script `crp-verify=crp_verifier.cli:main`),
`fixtures/build_golden_bundle.py`, `fixtures/bundles/golden-happy/` (committed real bundle),
`tests/` (conftest + happy/golden-roots/adversarial/cli/determinism).

**Check order (run_all):** reference_oracle, manifest_hash, assignment_root,
evidence_epoch_roots, result_artifact_hash (+seam), reward_root, onchain_commitments.
Exit codes: 0 OK, 1 verify-failed, 2 usage, 3 bundle IO. SKIP is not a failure.

**CLI flags:** `--seed <64hex>` runs the assignment derivation leg (re-derive every arm from
the committed seed; confirms seed opens frozen commitment — invariant 1). `--onchain <json>`
cross-checks reproduced roots vs on-chain anchors (aliases cohort_root→assignment_root etc.).
`--json` emits byte-stable `json.dumps(sort_keys, separators=(",",":"))`. No wall-clock/RNG.

**Offline env gotcha:** this box has NO pyarrow/setuptools in system python. To prove
`pip install -e .` I made a venv with `python3 -m venv --system-site-packages` (gets system
setuptools 68.1.2) + a `.pth` bridging `evidence-service/.venv/.../site-packages` (gets
pyarrow 18.1.0), then `pip install --no-index --no-deps --no-build-isolation -e .`. node 24 +
`sdk/typescript/dist/` are available for cross-impl checks.

**Adversarial harness** (`adversarial.py`): `evaluate_fixture` recomputes each
`test-vectors/adversarial/adv-0X` reject condition from inputs via _ref; scope BUNDLE (bundle
recompute enforces) vs ONCHAIN (settlement/state guard, confirmed by recompute). adv-01/02/03/05
are BUNDLE; adv-04/06 are ONCHAIN. Bundle tampers in tests use a `resync_result_hash` helper to
model a self-consistent attacker so the targeted guard is the only divergence.
