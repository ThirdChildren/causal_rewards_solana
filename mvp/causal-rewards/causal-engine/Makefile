# Causal engine (M3): tests, the golden reward gate, the determinism gate, the container digest.
#
# Uses a local venv at .venv with the exact pins in requirements.txt. `make setup` creates it.
PY  := PYTHONPATH=src .venv/bin/python
PIP := .venv/bin/pip
REFERENCE := ../verifier-cli/reference
IMAGE ?= crp-causal-engine:0.1.0

.PHONY: setup test golden determinism vectors demo container recipe-digest digest clean

setup:
	python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt

test:
	$(PY) -m pytest -q

# HARD ACCEPTANCE GATE: the ratified reward vectors in ../test-vectors/reward/.
golden:
	$(PY) -m pytest tests/test_reward_golden.py -q

# HARD ACCEPTANCE GATE: two fresh processes -> byte-identical artifacts.
determinism:
	$(PY) -m pytest tests/test_determinism.py -q

# Replay the ratified reward vectors through the CLI and print every root.
vectors:
	$(PY) -m crp_engine.cli vectors

# End-to-end demo run into out/demo (deterministic; seed is the only randomness source).
demo:
	$(PY) -c "import json,pathlib; from crp_engine.demo import write_demo; \
	  write_demo('out/demo', json.loads(pathlib.Path('../specs/examples/manifest.example.json').read_text()), \
	  bytes.fromhex('00'*24+'0123456789abcdef'))"
	$(PY) -m crp_engine.cli analyze \
	  --manifest out/demo/manifest.json --panel out/demo/panel.parquet \
	  --participants out/demo/participants.parquet \
	  --seed 0000000000000000000000000000000000000000000000000123456789abcdef \
	  --out out/demo/artifacts

# Deterministic RECIPE digest: sha256 over Dockerfile + requirements + every source file.
# Computable without docker; recorded in container.lock.json so a mismatch is detectable even
# before the image is built.
recipe-digest:
	$(PY) tools/container_lock.py --recipe-only

# Build the pinned analysis container and record BOTH digests in container.lock.json.
# Requires BuildKit for the named `reference` build context (the ratified conformance oracle).
container:
	DOCKER_BUILDKIT=1 docker build \
	  --build-context reference=$(REFERENCE) \
	  -t $(IMAGE) .
	$(PY) tools/container_lock.py --image $(IMAGE)

digest:
	$(PY) -m crp_engine.cli digest

clean:
	rm -rf out .pytest_cache **/__pycache__
