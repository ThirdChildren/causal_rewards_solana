"""crp_verifier — the independent, offline M3 reproduction oracle.

Given an audit-bundle directory the verifier RE-COMPUTES every anchored root/hash from
the bundle files alone (plus, for the assignment arms, the on-chain revealed seed) using
only the ratified reference encoder in ``verifier-cli/reference/`` — it trusts nothing but
the bundle, never calls a coordinator/evaluator, and needs no network.

Public surface:

* :func:`crp_verifier.checks.run_all` — run every check, return ordered results.
* :func:`crp_verifier.cli.main` — the ``crp-verify`` console entry point.
* :class:`crp_verifier.bundle.Bundle` — the on-disk bundle loader.
"""

from __future__ import annotations

__all__ = ["__version__"]

#: Verifier release. Bumping this NEVER changes any recomputed root — those are pinned by
#: the reference encoder fingerprint the verifier reports, not by this package version.
__version__ = "0.1.0"
