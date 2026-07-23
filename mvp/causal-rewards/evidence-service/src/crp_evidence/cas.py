"""Content-addressed batch storage.

Storage is hash-named, immutable, and flat: an object's path IS its identity, so mirroring a
store across providers is a plain byte copy with no index to keep in sync. This is the "data
availability discipline" requirement — a bundle must be replayable by a party with no access
to our infrastructure, which rules out any storage design whose correctness depends on a
hosted lookup service.

Layout::

    <root>/objects/<aa>/<bb>/<64-hex-sha256>.<ext>
    <root>/objects/.../<hash>.json      one signed batch header, CJSON bytes
    <root>/objects/.../<hash>.parquet   one materialized table

The two-level ``aa/bb`` fan-out keeps directory sizes sane at 10^6 objects. The address is
SHA-256 of the STORED BYTES, always — never of a logical view — so verifying the store is
``sha256(read(path)) == basename(path)`` and nothing else.

Batch objects are stored as their **canonical** bytes (``CJSON(batch)``), which makes the
object address equal to the batch's evidence leaf preimage hash input: ``leaf_hash =
SHA-256(0x00 || "CRP:evidence:v1" || <the exact bytes at this path>)``. A verifier can rebuild
the epoch tree straight from the store without re-serializing anything.

Writes are idempotent: storing identical content twice is a no-op, not an error (the ingestion
ledger, not the store, is where replay is detected — the store has no opinion about how many
times someone asked it to hold the same bytes).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from . import _ref
from .errors import EvidenceRejected, RejectionCode

__all__ = ["ContentAddressedStore", "StoredObject"]


@dataclass(frozen=True)
class StoredObject:
    sha256_hex: str
    rel_path: str
    size: int
    media_type: str

    def to_dict(self) -> dict[str, str]:
        return {
            "media_type": self.media_type,
            "path": self.rel_path,
            "sha256": self.sha256_hex,
            "size": str(self.size),
        }


class ContentAddressedStore:
    """A flat, immutable, hash-named object store on a local filesystem path."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    # -- addressing ------------------------------------------------------------

    @staticmethod
    def address(data: bytes) -> str:
        return _ref.sha256_hex(data)

    def rel_path_for(self, digest: str, ext: str) -> str:
        if len(digest) != 64:
            raise ValueError("digest must be 64 hex chars")
        return "objects/%s/%s/%s.%s" % (digest[0:2], digest[2:4], digest, ext)

    def path_for(self, digest: str, ext: str) -> Path:
        return self.root / self.rel_path_for(digest, ext)

    # -- writes ----------------------------------------------------------------

    def put_bytes(self, data: bytes, ext: str, media_type: str) -> StoredObject:
        digest = self.address(data)
        rel = self.rel_path_for(digest, ext)
        path = self.root / rel
        if path.exists():
            existing = path.read_bytes()
            if existing != data:  # pragma: no cover - SHA-256 collision
                raise EvidenceRejected(
                    RejectionCode.BUNDLE_CONTENT_ADDRESS_MISMATCH,
                    "content address collision at %s" % rel,
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return StoredObject(digest, rel, len(data), media_type)

    def put_batch(self, batch: Mapping[str, Any]) -> StoredObject:
        """Store a signed batch header as its canonical bytes. Address == CJSON hash.

        NOTE this address is SHA-256(CJSON(batch)) over the WHOLE batch including
        ``batch_signature``; it is deliberately NOT ``header_hash_hex`` (which is over the
        batch MINUS the signature). Both are recorded in the evidence table so neither is
        mistaken for the other.
        """
        data = _ref.canonical_json_bytes(batch)
        return self.put_bytes(data, "json", "application/json")

    def put_parquet(self, data: bytes) -> StoredObject:
        return self.put_bytes(data, "parquet", "application/vnd.apache.parquet")

    # -- reads / integrity -----------------------------------------------------

    def get(self, digest: str, ext: str) -> bytes:
        return self.path_for(digest, ext).read_bytes()

    def iter_objects(self) -> Iterator[Path]:
        base = self.root / "objects"
        if not base.exists():
            return iter(())
        return iter(sorted(p for p in base.rglob("*") if p.is_file()))

    def verify(self) -> list[str]:
        """Re-hash every object; return the relative paths whose address does not match."""
        bad: list[str] = []
        for p in self.iter_objects():
            digest = p.stem
            if self.address(p.read_bytes()) != digest:
                bad.append(str(p.relative_to(self.root)))
        return bad
