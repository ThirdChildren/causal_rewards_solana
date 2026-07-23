# Evidence service (M3) — golden-vector gate + determinism gate.
#
# Uses a local venv at .venv with pinned deps (requirements.txt). `make setup` creates it.
PY := PYTHONPATH=src .venv/bin/python
PIP := .venv/bin/pip
TV ?= ../test-vectors/evidence
OUT ?= out/bundle

.PHONY: setup test vectors determinism bundle verify clean

setup:
	python3 -m venv .venv
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -r requirements.txt

test:
	$(PY) -m pytest -q

# HARD ACCEPTANCE GATE: reproduce every ratified evidence golden root. Exit 1 on any mismatch.
vectors:
	$(PY) -m crp_evidence.cli vectors --test-vectors $(TV)

# Determinism gate: build the same bundle twice IN SEPARATE PROCESSES; bundle_content_hash
# and every parquet file's bytes must be identical.
determinism:
	$(PY) -m pytest -q tests/test_determinism.py

clean:
	rm -rf out .pytest_cache .venv
