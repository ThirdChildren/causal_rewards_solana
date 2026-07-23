"""Content-addressed store: address == sha256(bytes), idempotent, mirrorable."""

from __future__ import annotations

from pathlib import Path

import fixtures as fx

from crp_evidence import _ref
from crp_evidence.cas import ContentAddressedStore
from crp_evidence.roots import evidence_epoch_root


def test_batch_object_address_is_sha256_of_canonical_bytes(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    obj = store.put_batch(b)
    data = _ref.canonical_json_bytes(b)
    assert obj.sha256_hex == _ref.sha256_hex(data)
    assert (tmp_path / obj.rel_path).read_bytes() == data
    assert obj.rel_path.startswith("objects/%s/%s/" % (obj.sha256_hex[:2], obj.sha256_hex[2:4]))


def test_stored_bytes_are_the_evidence_leaf_preimage(tmp_path: Path) -> None:
    """A verifier can rebuild the epoch tree straight from stored objects."""
    store = ContentAddressedStore(tmp_path)
    batches = [fx.make_batch(epoch_index="0", cohort_id=c) for c in fx.COHORT_IDS]
    objs = [store.put_batch(b) for b in batches]
    root, records = evidence_epoch_root(batches)
    rebuilt = []
    for o in objs:
        raw = store.get(o.sha256_hex, "json")
        rebuilt.append(
            _ref.sha256(_ref.merkle.LEAF_PREFIX + _ref.merkle.DOMAIN_EVIDENCE + raw).hex()
        )
    assert sorted(rebuilt) == [r["leaf_hash_hex"] for r in records]
    assert len(root) == 64


def test_put_is_idempotent(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    b = fx.make_batch(epoch_index="0", cohort_id="cohort-a")
    a1 = store.put_batch(b)
    a2 = store.put_batch(b)
    assert a1 == a2
    assert len(list(store.iter_objects())) == 1


def test_verify_detects_corruption(tmp_path: Path) -> None:
    store = ContentAddressedStore(tmp_path)
    obj = store.put_batch(fx.make_batch(epoch_index="0", cohort_id="cohort-a"))
    assert store.verify() == []
    p = tmp_path / obj.rel_path
    p.write_bytes(p.read_bytes() + b" ")
    assert store.verify() == [obj.rel_path]


def test_store_is_mirrorable_by_byte_copy(tmp_path: Path) -> None:
    import shutil

    src = ContentAddressedStore(tmp_path / "a")
    for c in fx.COHORT_IDS:
        src.put_batch(fx.make_batch(epoch_index="0", cohort_id=c))
    shutil.copytree(tmp_path / "a", tmp_path / "b")
    assert ContentAddressedStore(tmp_path / "b").verify() == []
