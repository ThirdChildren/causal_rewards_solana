"""Record the analysis-container digests in ``container.lock.json``.

Two digests, for two different jobs:

``recipe_digest``
    SHA-256 over the *build recipe* — the Dockerfile, the pinned requirements, and every engine
    source file, hashed in a fixed path order with length-prefixed names. Computable with no
    docker daemon, on any machine. Its job is to make "the container inputs changed" detectable
    *before* anyone rebuilds, and to bind the committed source tree to the frozen manifest.

``image_digest``
    The OCI image digest that `analysis_plan.analysis_container_digest` must carry. Only a real
    ``docker build`` can produce it. Until the image is built this field is ``null`` and the
    frozen manifest cannot be filled in.

Deterministic: sorted file order, raw bytes, no wall-clock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "container.lock.json"

#: Everything that can change a committed number. Order is fixed by the sorted relative path.
RECIPE_FILES = ("Dockerfile", "requirements.txt", "pyproject.toml")
RECIPE_DIRS = ("src",)


def _iter_recipe_paths() -> list[Path]:
    paths = [ROOT / f for f in RECIPE_FILES if (ROOT / f).is_file()]
    for d in RECIPE_DIRS:
        paths.extend(sorted((ROOT / d).rglob("*.py")))
    return sorted(paths, key=lambda p: str(p.relative_to(ROOT)))


def recipe_digest() -> str:
    h = hashlib.sha256()
    for p in _iter_recipe_paths():
        rel = str(p.relative_to(ROOT)).encode("utf-8")
        h.update(len(rel).to_bytes(4, "big"))
        h.update(rel)
        data = p.read_bytes()
        h.update(len(data).to_bytes(8, "big"))
        h.update(data)
    return "sha256:" + h.hexdigest()


def reference_digest() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    from crp_engine.reference import reference_source_digest

    return reference_source_digest()


def image_digest(image: str) -> str | None:
    try:
        out = subprocess.run(
            ["docker", "image", "inspect", image, "--format", "{{index .Id}}"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        print("could not read the image digest (%s); leaving image_digest null" % exc,
              file=sys.stderr)
        return None
    return out if out.startswith("sha256:") else "sha256:" + out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--image", default=None, help="built image reference, e.g. crp-causal-engine:0.1.0")
    p.add_argument("--recipe-only", action="store_true")
    args = p.parse_args(argv)

    existing = json.loads(LOCK.read_text(encoding="utf-8")) if LOCK.is_file() else {}
    obj = {
        "schema": "crp.container_lock/v1",
        "image_name": args.image or existing.get("image_name"),
        "image_digest": (
            existing.get("image_digest")
            if args.recipe_only or not args.image
            else image_digest(args.image)
        ),
        "recipe_digest": recipe_digest(),
        "reference_source_digest": reference_digest(),
        "base_image": "python@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5",
        "note": (
            "image_digest is what a frozen manifest's analysis_plan.analysis_container_digest "
            "must carry. recipe_digest is a docker-free binding of the build inputs and is NOT a "
            "substitute for it."
        ),
    }
    LOCK.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("recipe_digest  %s" % obj["recipe_digest"])
    print("reference      %s" % obj["reference_source_digest"])
    print("image_digest   %s" % (obj["image_digest"] or "<not built>"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
