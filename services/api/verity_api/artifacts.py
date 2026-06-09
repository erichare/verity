"""In-process content-addressed artifact store for the glass-box step API.

Every artifact — an uploaded surface, or an intermediate the pipeline produces — is
stored by the SHA-256 of its canonical serialization and addressed by that handle, with
a ``produced_by`` record naming the step, its parameters, and its input handles. Because
inputs are themselves handles, a chain of steps is a content-addressed DAG: the final
handle commits to every parameter and input that produced it.

Intermediates are a CACHE, not a system of record — entries carry a TTL and the store is
size-capped (LRU eviction). Swap this in-process store for the catalog's on-disk
``BlobStore`` when durable, cross-instance artifacts are needed; the handle scheme is the
same SHA-256 content address.
"""

from __future__ import annotations

import hashlib
import io
import json
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass

import numpy as np

from verity.surface import Surface

# Surface kinds carry pixel pitch; the handle must cover it (same heights, different dx is
# a different artifact). Other array kinds hash the array bytes alone.
_SURFACE_KINDS = frozenset({"surface", "surface.bandpassed"})


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def _npy_bytes(arr: np.ndarray) -> bytes:
    """Deterministic ``.npy`` of a float64, C-contiguous array — the canonical array blob."""
    buf = io.BytesIO()
    np.save(buf, np.ascontiguousarray(np.asarray(arr, dtype=np.float64)))
    return buf.getvalue()


@dataclass(frozen=True)
class Artifact:
    handle: str  # "sha256:<hex>"
    kind: str  # surface | surface.bandpassed | signature.1d | signature.2d
    meta: dict  # shape, dx/dy, length, source provenance …
    produced_by: dict  # {step, code, params, inputs, engine_version, output}
    data: bytes  # the .npy bytes (served by /data, loadable with np.load)
    created: float

    def summary(self) -> dict:
        """Everything but the raw bytes — the addressable record."""
        return {
            "handle": self.handle,
            "kind": self.kind,
            "meta": self.meta,
            "produced_by": self.produced_by,
            "bytes": len(self.data),
        }


class ArtifactStore:
    """A thread-safe, TTL'd, size-capped content-addressed cache of pipeline artifacts."""

    def __init__(self, *, max_items: int = 512, ttl_s: float = 3600.0) -> None:
        self._items: OrderedDict[str, Artifact] = OrderedDict()
        self._max = max_items
        self._ttl = ttl_s
        self._lock = threading.Lock()

    def _evict(self, now: float) -> None:
        for h in [h for h, a in self._items.items() if now - a.created > self._ttl]:
            del self._items[h]
        while len(self._items) > self._max:
            self._items.popitem(last=False)  # LRU

    def put_array(
        self, arr: np.ndarray, *, kind: str, meta: dict, produced_by: dict, now: float | None = None
    ) -> Artifact:
        """Store an array artifact and return it. The handle hashes the array bytes plus
        the pitch (for surfaces), so identical content dedupes and distinct content can't
        collide."""
        now = time.time() if now is None else now
        data = _npy_bytes(arr)
        hash_meta = (
            {k: meta[k] for k in ("dx", "dy") if k in meta} if kind in _SURFACE_KINDS else {}
        )
        digest = _sha256(_canonical({"kind": kind, "meta": hash_meta}) + b"\x00" + data)
        handle = f"sha256:{digest}"
        art = Artifact(
            handle=handle,
            kind=kind,
            meta=meta,
            produced_by={**produced_by, "output": handle},
            data=data,
            created=now,
        )
        with self._lock:
            self._items[handle] = art
            self._items.move_to_end(handle)
            self._evict(now)
        return art

    def get(self, handle: str) -> Artifact | None:
        with self._lock:
            art = self._items.get(handle)
            if art is not None:
                self._items.move_to_end(handle)
            return art

    def array(self, handle: str) -> np.ndarray | None:
        art = self.get(handle)
        return None if art is None else np.load(io.BytesIO(art.data), allow_pickle=False)

    def surface(self, handle: str) -> Surface | None:
        art = self.get(handle)
        if art is None or art.kind not in _SURFACE_KINDS:
            return None
        heights = np.load(io.BytesIO(art.data), allow_pickle=False)
        return Surface(heights=heights, dx=float(art.meta["dx"]), dy=float(art.meta["dy"]))


# One process-wide store. Intermediates live here for their TTL; restart clears them.
STORE = ArtifactStore()
