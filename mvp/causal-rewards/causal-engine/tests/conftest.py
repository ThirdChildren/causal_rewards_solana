"""Shared fixtures. No network, no wall-clock, no unseeded randomness."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parents[2]
SPEC_MANIFEST = REPO / "specs" / "examples" / "manifest.example.json"
REWARD_VECTORS = REPO / "test-vectors" / "reward"


@pytest.fixture(scope="session")
def spec_manifest_obj() -> dict[str, Any]:
    return json.loads(SPEC_MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture
def manifest_obj(spec_manifest_obj) -> dict[str, Any]:
    """A mutable copy of the ratified example manifest."""
    return copy.deepcopy(spec_manifest_obj)
