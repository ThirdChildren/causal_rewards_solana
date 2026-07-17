# DePIN simulator (M1 alpha) — deterministic baseline + determinism gate.
#
# Uses a local venv at .venv with pinned deps. `make setup` creates it.
PY := PYTHONPATH=src .venv/bin/python
PIP := .venv/bin/pip
SCENARIO ?= scenarios/baseline_alpha.json
SEED ?=
OUT ?= out/baseline_alpha

.PHONY: setup baseline hash determinism test clean

setup:
	python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt

# Emit the deterministic baseline bundle (sensors, cohort assignment, observation counts) + hash.
baseline:
	$(PY) -m depin_sim.cli run --scenario $(SCENARIO) $(if $(SEED),--seed $(SEED),) --out $(OUT)

# Print ONLY the content hash of a scenario run.
hash:
	$(PY) -m depin_sim.cli hash --scenario $(SCENARIO) $(if $(SEED),--seed $(SEED),)

# Determinism gate: run the same scenario+seed twice, fail if the content hashes differ.
determinism:
	@h1=$$($(PY) -m depin_sim.cli hash --scenario $(SCENARIO)); \
	 h2=$$($(PY) -m depin_sim.cli hash --scenario $(SCENARIO)); \
	 echo "run1: $$h1"; echo "run2: $$h2"; \
	 if [ -z "$$h1" ]; then echo "DETERMINISM FAIL: empty hash (run error)"; exit 1; fi; \
	 if [ "$$h1" != "$$h2" ]; then echo "DETERMINISM FAIL: hashes differ"; exit 1; fi; \
	 echo "DETERMINISM OK: identical content hash across reruns"

test:
	$(PY) -m pytest -q

clean:
	rm -rf out .pytest_cache
