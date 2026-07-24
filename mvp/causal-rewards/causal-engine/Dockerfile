# Pinned analysis container for the Causal Rewards Protocol causal engine.
#
# The digest of the image built from THIS file is what a frozen manifest carries as
# analysis_plan.analysis_container_digest. Reproducibility (CLAUDE.md invariant 2) depends on it:
# same container + same manifest + same data => identical analysis.json hash and identical reward
# leaves.
#
# Build + record the digest:
#     make container
#
# The base image is pinned BY DIGEST, not by tag: tags are mutable and would silently change the
# interpreter build underneath a frozen manifest.

# python:3.11.11-slim-bookworm, pinned by the registry index digest (verified against
# registry-1.docker.io on 2026-07-23). The platform is pinned too, because an index digest still
# resolves to a per-architecture image and the interpreter build differs across architectures.
#   index digest (multi-arch): sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5
#   linux/amd64 manifest:      sha256:a8e0a3090316aed0b11037aac613aef32fb1747dcc1dcb5c0f6c727a0113a07f
FROM --platform=linux/amd64 python@sha256:081075da77b2b55c23c088251026fb69a7b2bf92471e491ff5fd75c192fd38e5

# Determinism knobs, set for every process in the image:
#   PYTHONHASHSEED   - str/bytes hashing is salted per process by default; pin it so any
#                      accidental dict/set-order dependence is at least stable (the engine is
#                      tested against a VARYING PYTHONHASHSEED, so this is belt-and-braces).
#   *_NUM_THREADS    - a threaded BLAS reduction is order-nondeterministic. The engine routes
#                      every committed reduction through math.fsum and solves K x K systems with
#                      its own Gaussian elimination, so no committed number touches BLAS; these
#                      pins protect any future edit that reintroduces one.
#   PYTHONDONTWRITEBYTECODE / TZ / LC_ALL - no stray .pyc, no locale- or timezone-dependent
#                      formatting anywhere near an artifact.
ENV PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1 \
    OMP_NUM_THREADS=1 \
    NUMEXPR_NUM_THREADS=1 \
    VECLIB_MAXIMUM_THREADS=1 \
    TZ=UTC \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8 \
    SOURCE_DATE_EPOCH=0 \
    CRP_REFERENCE_DIR=/opt/crp/reference

WORKDIR /opt/crp/engine

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade "pip==24.3.1" \
 && python -m pip install --no-cache-dir -r requirements.txt

# The RATIFIED conformance oracle. The engine imports its canonical/merkle/reward/assignment
# byte semantics from here rather than re-implementing them (see src/crp_engine/reference.py).
COPY --from=reference . /opt/crp/reference

COPY pyproject.toml README.md ./
COPY src ./src
COPY tests ./tests
RUN python -m pip install --no-cache-dir --no-deps -e .

ENTRYPOINT ["crp-engine"]
CMD ["--help"]
