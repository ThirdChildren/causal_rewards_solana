"""Independent recomputation of every bundle root/hash — the M3 acceptance oracle.

Each ``check_*`` recomputes a value from the bundle files ALONE (plus, for the
assignment arms, the on-chain ``revealed_seed`` — legitimately outside the frozen
bundle by invariant 1, freeze-before-reveal) using ONLY the ratified reference
encoder (:mod:`_ref`). Nothing is re-implemented here; nothing calls back to a
coordinator/evaluator; ``roots.json`` is treated as an UNTRUSTED claim to be
reproduced, never as a source of truth.

Every check yields a :class:`CheckResult` with ``PASS``/``FAIL``/``SKIP`` and, on
failure, the first point of divergence (expected vs got). Determinism: the checks
read no wall-clock and no RNG, and emit results in a fixed order, so two runs on the
same bundle produce identical report bytes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from . import _ref
from .bundle import Bundle, BundleError

PASS = "PASS"
FAIL = "FAIL"
SKIP = "SKIP"

_ZERO_ROOT = "00" * 32


@dataclass
class CheckResult:
    name: str
    status: str
    summary: str
    #: First point of divergence on failure (field, expected, got) — else None.
    divergence: tuple[str, str, str] | None = None
    details: list[str] = field(default_factory=list)

    def ok(self) -> bool:
        return self.status != FAIL


def _fail(name: str, summary: str, field_: str, expected: str, got: str,
          details: Sequence[str] = ()) -> CheckResult:
    return CheckResult(name, FAIL, summary, (field_, expected, got), list(details))


def _pass(name: str, summary: str, details: Sequence[str] = ()) -> CheckResult:
    return CheckResult(name, PASS, summary, None, list(details))


def _skip(name: str, summary: str, details: Sequence[str] = ()) -> CheckResult:
    return CheckResult(name, SKIP, summary, None, list(details))


# --------------------------------------------------------------------------- helpers


def _roots(b: Bundle) -> Mapping[str, Any]:
    return b.roots["roots"]


def _manifest_assignment_inputs(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Pull the assignment-derivation inputs OUT of the frozen manifest.

    Returns keys ``seed_commitment_hex`` / ``design`` / ``params`` (any may be None).
    ``seed_commitment_hex`` lives under ``assignment.seed_commitment.commitment_hex``
    (manifest.schema.json). ``design`` / ``params`` are the machine-readable derivation
    descriptor the verifier needs to re-derive arms; the manifest schema does not yet
    pin a single canonical location for them (SPEC GAP, escalated to protocol-architect),
    so absence downgrades the assignment check to structural-only rather than failing.
    """
    a = manifest.get("assignment") or {}
    sc = a.get("seed_commitment") or {}
    return {
        "seed_commitment_hex": sc.get("commitment_hex"),
        "design": a.get("design"),
        "params": a.get("params"),
    }


# --------------------------------------------------------------------------- checks


def check_reference_fingerprint(b: Bundle) -> CheckResult:
    fp = _ref.module_fingerprint()
    return _pass(
        "reference_oracle",
        "recompute uses the ratified reference encoder (single source of canonical bytes)",
        details=["%s %s" % (k, fp[k]) for k in sorted(fp)],
    )


def check_manifest_hash(b: Bundle, *, golden_manifest_hash: str | None = None) -> CheckResult:
    """``manifest_hash = SHA-256(CJSON(manifest.json))`` — must equal roots.json + provenance.

    Also confirms manifest.json is stored as verbatim canonical bytes (a re-canonicalized
    manifest must byte-equal the stored file), so the anchored hash is over exactly what the
    bundle ships.
    """
    raw = b.raw("manifest.json")
    parsed = b.json("manifest.json")
    recanon = _ref.canonical_json_bytes(parsed)
    recomputed = _ref.sha256_hex(recanon)

    if recanon != raw:
        return _fail(
            "manifest_hash", "manifest.json is not stored as verbatim canonical bytes",
            "manifest.json bytes", "<CJSON(manifest)>", "<stored bytes differ>",
            details=["stored sha256 %s != CJSON sha256 %s" % (_ref.sha256_hex(raw), recomputed)],
        )

    declared = str(b.roots.get("manifest_hash"))
    if recomputed != declared:
        return _fail("manifest_hash", "recomputed manifest hash != roots.json",
                     "manifest_hash", declared, recomputed)

    details = ["manifest_hash %s" % recomputed]
    # provenance echo (excluded from bundle hashes but must still name the same manifest).
    if b.has("provenance.json"):
        prov_hash = str(b.json("provenance.json").get("manifest_hash"))
        if prov_hash != recomputed:
            return _fail("manifest_hash", "provenance.json manifest_hash != recomputed",
                         "provenance.manifest_hash", recomputed, prov_hash)
        details.append("provenance.manifest_hash agrees")
    if golden_manifest_hash is not None:
        if recomputed != golden_manifest_hash:
            return _fail("manifest_hash", "recomputed manifest hash != declared golden",
                         "golden_manifest_hash", golden_manifest_hash, recomputed)
        details.append("matches golden %s" % golden_manifest_hash)
    return _pass("manifest_hash", "manifest hash reproduced from CJSON(manifest.json)", details)


def check_assignment_root(b: Bundle, *, revealed_seed: bytes | None) -> CheckResult:
    """Reproduce the assignment root; if the seed is revealed, also re-derive every arm.

    Structural leg (always): recompute each leaf ``CJSON({"arm","cohort_id"})`` and its
    ``leaf_hash`` from the assignment table, confirm the table's own ``leaf_hash_hex``,
    rebuild the root, and compare to roots.json.

    Derivation leg (needs ``revealed_seed``): confirm ``seed_commitment(seed)`` opens the
    frozen commitment (invariant 1), then re-derive the arm + prf of every cohort from the
    seed and the frozen design/params and confirm they equal the table — proving the arms
    were not hand-picked after the seed was known.
    """
    name = "assignment_root"
    t = b.parquet("assignment.parquet")
    declared_root = str(_roots(b)["assignment_root_hex"])

    # -- structural leg --------------------------------------------------------------
    leaf_bytes: list[bytes] = []
    seen: set[str] = set()
    for row in t.dict_rows():
        cid, arm = row["cohort_id"], row["arm"]
        if cid in seen:
            return _fail(name, "duplicate cohort_id in assignment table",
                         "cohort_id", "<unique>", cid)
        seen.add(cid)
        lb = _ref.assignment.assignment_leaf_bytes(
            _ref.assignment.CohortAssignment(cid, arm, 0)
        )
        leaf_bytes.append(lb)
        lh = _ref.merkle.leaf_hash(_ref.merkle.DOMAIN_ASSIGNMENT, lb).hex()
        if lh != row["leaf_hash_hex"]:
            return _fail(name, "assignment leaf_hash_hex does not match recomputed leaf",
                         "leaf_hash_hex[cohort=%s]" % cid, lh, row["leaf_hash_hex"])
    # Table rows MUST already be in canonical (cohort_id UTF-16 asc) order.
    ordered = sorted(t.column("cohort_id"), key=lambda c: c.encode("utf-16-be"))
    if t.column("cohort_id") != ordered:
        return _fail(name, "assignment rows are not in canonical cohort_id order",
                     "row order", str(ordered), str(t.column("cohort_id")))
    structural_root = _ref.merkle.merkle_root(leaf_bytes, _ref.merkle.DOMAIN_ASSIGNMENT).hex()
    if structural_root != declared_root:
        return _fail(name, "assignment root rebuilt from table leaves != roots.json",
                     "assignment_root_hex", declared_root, structural_root)

    details = ["assignment_root %s (reproduced from %d published leaves)"
               % (structural_root, len(leaf_bytes))]

    # -- derivation leg --------------------------------------------------------------
    inp = _manifest_assignment_inputs(b.manifest)
    if revealed_seed is None:
        return CheckResult(
            name, PASS,
            "assignment root reproduced from published leaves; arm-from-seed derivation "
            "SKIPPED (no --seed given)",
            None, details + ["provide the on-chain revealed_seed to verify arms were "
                             "derived from the committed seed (invariant 1)"],
        )

    # seed opens the frozen commitment?
    commit = _ref.assignment.seed_commitment(revealed_seed).hex()
    frozen = inp["seed_commitment_hex"]
    if frozen is None:
        return _fail(name, "manifest has no assignment.seed_commitment.commitment_hex",
                     "seed_commitment", "<64-hex>", "None")
    if commit != frozen:
        return _fail(name, "revealed seed does NOT open the frozen seed_commitment "
                     "(invariant 1 violated)", "seed_commitment", frozen, commit)
    details.append("seed_commitment(revealed_seed) opens frozen commitment %s" % frozen)

    design, params = inp["design"], inp["params"]
    if not design or params is None:
        return CheckResult(
            name, PASS,
            "assignment root + seed commitment verified; arm re-derivation SKIPPED "
            "(manifest lacks a machine-readable assignment.design/params descriptor — SPEC GAP)",
            None, details,
        )

    experiment_id = str(b.manifest["experiment_id"])
    cohort_ids = t.column("cohort_id")
    try:
        assigns = _ref.assignment.derive_assignment(
            revealed_seed, experiment_id, list(cohort_ids), str(design), dict(params)
        )
    except (ValueError, KeyError) as exc:
        return _fail(name, "assignment derivation raised on the frozen design/params",
                     "derive_assignment", "<ok>", "%s: %s" % (type(exc).__name__, exc))
    by_cid = {a.cohort_id: a for a in assigns}
    for row in t.dict_rows():
        a = by_cid[row["cohort_id"]]
        if a.arm != row["arm"]:
            return _fail(name, "re-derived arm != table arm (arms not derived from the seed)",
                         "arm[cohort=%s]" % row["cohort_id"], a.arm, row["arm"])
        if str(a.prf_u64) != row["prf_u64"]:
            return _fail(name, "re-derived prf_u64 != table prf_u64",
                         "prf_u64[cohort=%s]" % row["cohort_id"], str(a.prf_u64), row["prf_u64"])
    derived_root = _ref.merkle.merkle_root(
        [_ref.assignment.assignment_leaf_bytes(a) for a in assigns], _ref.merkle.DOMAIN_ASSIGNMENT
    ).hex()
    if derived_root != declared_root:
        return _fail(name, "root re-derived from the seed != roots.json",
                     "assignment_root_hex", declared_root, derived_root)
    details.append("all %d arms + prf re-derived from the revealed seed match the table"
                   % len(assigns))
    return _pass(name, "assignment root fully reproduced from the revealed seed", details)


def _recompute_epoch_roots(b: Bundle) -> tuple[list[str], CheckResult | None]:
    """Return (recomputed epoch roots in ascending epoch order, failure-or-None).

    Each epoch root is rebuilt from the epoch table's published ``leaf_hash_hex`` column
    via the reference ``merkle_root_from_hashes`` (the SAME node/promotion rule as build),
    after enforcing strict-ascending leaf order (a duplicate/out-of-order leaf is a hard
    error — replayed-evidence rejection, adv-03/§6.5 totality).
    """
    recomputed: list[str] = []
    epochs = _roots(b)["evidence_epochs"]
    for e in epochs:
        rel = str(e["file"])
        declared = str(e["evidence_epoch_root_hex"])
        t = b.parquet(rel)
        leaf_hex = t.column("leaf_hash_hex")
        prev: str | None = None
        for h in leaf_hex:
            if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
                return recomputed, _fail(
                    "evidence_epoch_roots", "evidence leaf_hash_hex is not 64 lowercase hex",
                    "leaf_hash_hex", "<64-hex>", h)
            if prev is not None and not (bytes.fromhex(prev) < bytes.fromhex(h)):
                dup = prev == h
                return recomputed, _fail(
                    "evidence_epoch_roots",
                    "evidence leaves not strictly ascending (%s)"
                    % ("DUPLICATE_EVIDENCE_LEAF" if dup else "EVIDENCE_LEAF_ORDER"),
                    "leaf order @%s" % rel, "%s < %s" % (prev, h), "%s >= %s" % (prev, h))
            prev = h
        root = _ref.merkle.merkle_root_from_hashes([bytes.fromhex(h) for h in leaf_hex]).hex()
        if root == "" and not leaf_hex:
            root = _ZERO_ROOT
        if root != declared:
            return recomputed, _fail(
                "evidence_epoch_roots", "recomputed epoch root != roots.json",
                "evidence_epoch_root_hex[%s]" % rel, declared, root)
        recomputed.append(declared)
    return recomputed, None


def check_evidence_epoch_roots(b: Bundle) -> CheckResult:
    recomputed, failure = _recompute_epoch_roots(b)
    if failure is not None:
        return failure
    if not recomputed:
        return _skip("evidence_epoch_roots", "bundle anchors no evidence epochs")
    return _pass(
        "evidence_epoch_roots",
        "all %d evidence epoch roots reproduced from published leaf hashes (strict order)"
        % len(recomputed),
        details=["%s %s" % (str(e["epoch_index"]), str(e["evidence_epoch_root_hex"]))
                 for e in _roots(b)["evidence_epochs"]],
    )


def check_result_artifact_and_seam(b: Bundle) -> CheckResult:
    """``result_artifact_hash = SHA-256(CJSON(analysis.json))`` + the evidence↔result seam.

    The seam binding (§1.4): ``analysis.json.evidence_epoch_roots`` MUST equal the epoch
    roots recomputed from the evidence Parquet, in ascending epoch order. A mismatch means
    the analysis consumed different evidence than the bundle anchors — rejected. Also cross-
    checks the analysis-declared ``reward_root_hex`` against the reward tree (checked fully
    in :func:`check_reward_root`) and the container digest against the frozen manifest.
    """
    name = "result_artifact_hash"
    if not b.has("analysis.json"):
        return _skip(name, "evidence-only bundle (no analysis.json)")

    raw = b.raw("analysis.json")
    parsed = b.json("analysis.json")
    recanon = _ref.canonical_json_bytes(parsed)
    if recanon != raw:
        return _fail(name, "analysis.json is not stored as verbatim canonical bytes",
                     "analysis.json bytes", "<CJSON(analysis)>", "<stored bytes differ>")
    result_hash = _ref.sha256_hex(recanon)

    # seam: analysis-declared epoch roots vs recomputed-from-evidence
    recomputed, failure = _recompute_epoch_roots(b)
    if failure is not None:
        return failure
    declared_roots = [str(x) for x in (parsed.get("evidence_epoch_roots") or [])]
    if declared_roots != recomputed:
        return _fail(name, "SEAM BREAK: analysis.json evidence_epoch_roots != roots rebuilt "
                     "from evidence (analysis consumed different evidence)",
                     "evidence_epoch_roots", str(recomputed), str(declared_roots))

    details = ["result_artifact_hash %s" % result_hash,
               "seam OK: analysis binds the %d recomputed evidence epoch roots" % len(recomputed)]

    # container digest freeze binding (adv-05 class)
    frozen_digest = ((b.manifest.get("analysis_plan") or {}).get("analysis_container_digest"))
    engine = parsed.get("engine") or {}
    echoed = engine.get("analysis_container_digest") if isinstance(engine, Mapping) else None
    if frozen_digest is not None and echoed is not None and str(echoed) != str(frozen_digest):
        return _fail(name, "analysis container digest != frozen manifest (stale/substituted "
                     "container)", "analysis_container_digest", str(frozen_digest), str(echoed))
    if frozen_digest is not None and echoed is not None:
        details.append("analysis_container_digest matches frozen manifest")

    # experiment_id binding
    if str(parsed.get("experiment_id")) != str(b.manifest["experiment_id"]):
        return _fail(name, "analysis.json experiment_id != manifest experiment_id",
                     "experiment_id", str(b.manifest["experiment_id"]),
                     str(parsed.get("experiment_id")))
    return _pass(name, "result artifact hash reproduced; evidence↔result seam intact", details)


def check_reward_root(b: Bundle) -> CheckResult:
    """Rebuild every reward leaf hash and the §6.6 reward root from ``rewards.parquet``.

    For each row: recompute ``leaf_hash = SHA-256(0x00||"CRP:reward:v1"||recipient(32)||
    amount_u64_be||leaf_index_u64_be)`` and confirm the table's ``leaf_hash_hex``; then feed
    the leaves to the reference ``reward_root`` which enforces §6.6 (unique recipient key,
    contiguous 0..N-1 leaf_index, ascending-recipient order) — a duplicate or a gap is a hard
    error. Compare the root to roots.json and, if present, to analysis.json's declared root.
    """
    name = "reward_root"
    declared_root = str(_roots(b).get("reward_root_hex"))
    if not b.has("rewards.parquet"):
        if declared_root in ("absent", "None"):
            return _skip(name, "evidence-only bundle (no rewards.parquet)")
        return _fail(name, "roots.json declares a reward root but rewards.parquet is missing",
                     "rewards.parquet", "<present>", "<missing>")

    t = b.parquet("rewards.parquet")
    expected_cols = ("leaf_index", "recipient_hex", "amount_base_units", "leaf_hash_hex")
    if t.columns != expected_cols:
        return _fail(name, "rewards.parquet columns are not the ratified §6.6 leaf schema",
                     "columns", str(expected_cols), str(t.columns))

    leaves = []
    prev_recipient: bytes | None = None
    for i, row in enumerate(t.dict_rows()):
        try:
            recipient = bytes.fromhex(row["recipient_hex"])
            amount = int(row["amount_base_units"])
            leaf_index = int(row["leaf_index"])
        except ValueError as exc:
            return _fail(name, "malformed reward row", "row[%d]" % i, "<canonical>", str(exc))
        if len(recipient) != 32:
            return _fail(name, "recipient_hex does not decode to 32 bytes",
                         "recipient_hex[%d]" % i, "<32 bytes>", "%d bytes" % len(recipient))
        if leaf_index != i:
            return _fail(name, "reward leaf_index not contiguous 0..N-1 in row order",
                         "leaf_index[row=%d]" % i, str(i), str(leaf_index))
        recomputed_leaf = _ref.reward.reward_leaf_hash(recipient, amount, leaf_index).hex()
        if recomputed_leaf != row["leaf_hash_hex"]:
            return _fail(name, "reward leaf_hash_hex != independently recomputed §6.6 leaf hash",
                         "leaf_hash_hex[leaf=%d]" % leaf_index, recomputed_leaf,
                         row["leaf_hash_hex"])
        if prev_recipient is not None and not (prev_recipient < recipient):
            return _fail(name, "reward leaves not ascending-by-recipient (§6.6 order)",
                         "recipient order @%d" % i, ">%s" % prev_recipient.hex(), recipient.hex())
        prev_recipient = recipient
        leaves.append(_ref.reward.RewardLeaf(recipient, amount, leaf_index))

    try:
        recomputed_root = _ref.reward.reward_root(leaves).hex()
    except ValueError as exc:
        return _fail(name, "reward leaf set rejected by §6.6 guards (dup/gap)",
                     "reward_root", "<valid leaf set>", str(exc))
    if recomputed_root != declared_root:
        return _fail(name, "recomputed reward root != roots.json",
                     "reward_root_hex", declared_root, recomputed_root)

    details = ["reward_root %s (%d leaves independently recomputed)"
               % (recomputed_root, len(leaves))]
    # cross-check the analysis-declared reward root, if any.
    if b.has("analysis.json"):
        rs = (b.json("analysis.json").get("reward_summary") or {})
        analysis_root = rs.get("reward_root_hex")
        if analysis_root is not None and str(analysis_root) not in (recomputed_root, _ZERO_ROOT):
            return _fail(name, "analysis.json reward_summary.reward_root_hex != recomputed root",
                         "analysis.reward_root_hex", recomputed_root, str(analysis_root))
        if analysis_root is not None and str(analysis_root) == recomputed_root:
            details.append("analysis.json reward_summary.reward_root_hex agrees")
    return _pass(name, "reward root + every leaf reproduced from rewards.parquet", details)


def check_onchain_commitments(b: Bundle, onchain: Mapping[str, Any] | None) -> CheckResult:
    """Optional no-trust cross-check: the bundle's reproduced roots vs the ON-CHAIN anchors.

    Recomputing internally-consistent roots proves the bundle is self-consistent; it does not
    prove it is the bundle the chain committed to. When the auditor supplies the on-chain
    anchored values (``manifest_hash`` / ``assignment_root``/``cohort_root`` / ``reward_root``
    / ``result_artifact_hash``), the reproduced values must equal them — this catches a fully
    self-consistent but SUBSTITUTED bundle (e.g. a swapped reward set).
    """
    name = "onchain_commitments"
    if not onchain:
        return _skip(name, "no on-chain commitments supplied (bundle self-consistency only)")
    r = _roots(b)
    checks = {
        "manifest_hash": str(b.roots.get("manifest_hash")),
        "assignment_root": str(r.get("assignment_root_hex")),
        "reward_root": str(r.get("reward_root_hex")),
    }
    # accept common aliases from the on-chain account
    alias = {"cohort_root": "assignment_root",
             "cohort_root_hex": "assignment_root",
             "assignment_root_hex": "assignment_root",
             "reward_root_hex": "reward_root",
             "manifest_hash_hex": "manifest_hash"}
    if b.has("analysis.json"):
        checks["result_artifact_hash"] = _ref.sha256_hex(b.raw("analysis.json"))
    details = []
    for k, v in onchain.items():
        key = alias.get(k, k)
        if key not in checks:
            continue
        if str(v) != checks[key]:
            return _fail(name, "reproduced %s != on-chain anchor" % key, key, str(v), checks[key])
        details.append("%s matches on-chain anchor %s" % (key, str(v)))
    if not details:
        return _skip(name, "supplied on-chain commitments matched no known root field")
    return _pass(name, "every reproduced root agrees with the on-chain commitment", details)


def run_all(
    b: Bundle,
    *,
    revealed_seed: bytes | None = None,
    onchain: Mapping[str, Any] | None = None,
    golden_manifest_hash: str | None = None,
) -> list[CheckResult]:
    """Run every check in a fixed order and return the ordered results (never raises for
    a verification failure; only structural I/O errors propagate as :class:`BundleError`)."""
    results = [check_reference_fingerprint(b)]
    for fn in (
        lambda: check_manifest_hash(b, golden_manifest_hash=golden_manifest_hash),
        lambda: check_assignment_root(b, revealed_seed=revealed_seed),
        lambda: check_evidence_epoch_roots(b),
        lambda: check_result_artifact_and_seam(b),
        lambda: check_reward_root(b),
        lambda: check_onchain_commitments(b, onchain),
    ):
        try:
            results.append(fn())
        except BundleError as exc:
            # A missing/unreadable required file is itself a verification failure, reported
            # against the check that needed it rather than crashing the run.
            results.append(CheckResult("bundle_io", FAIL, str(exc), ("file", "<readable>", str(exc))))
    return results
