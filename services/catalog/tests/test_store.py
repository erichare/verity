import pytest

from verity_catalog.store import LocalBlobStore, sha256_hex


def test_put_get_roundtrip(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    data = b"hello x3p"
    h = store.put(data)
    assert h == sha256_hex(data)
    assert store.exists(h)
    assert store.get(h) == data
    assert store.count() == 1


def test_put_is_idempotent_and_dedups(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    data = b"same bytes"
    h1 = store.put(data)
    h2 = store.put(data)
    assert h1 == h2
    assert store.count() == 1  # stored once, not twice


def test_distinct_content_distinct_blobs(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    store.put(b"a")
    store.put(b"b")
    assert store.count() == 2


def test_get_missing_raises(tmp_path):
    store = LocalBlobStore(tmp_path / "blobs")
    with pytest.raises(KeyError):
        store.get("0" * 64)
