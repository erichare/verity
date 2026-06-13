"""S3 blob store tests — key layout (no network) + a full round-trip on a fake
S3 (moto), so the deploy-path store is verified without touching a real bucket."""

from __future__ import annotations

import pytest

from verity_catalog.store import sha256_hex
from verity_catalog.store_s3 import S3BlobStore, blob_key


def test_key_layout_matches_local_store():
    """The S3 key must be the same sharded layout as LocalBlobStore so a blob's
    address is identical on either backend."""
    h = "abcd1234" + "0" * 56
    assert blob_key(h) == f"ab/cd/{h}.bin"
    store = S3BlobStore("bucket", client=object())  # client unused for key calc
    assert store.key_for(h) == f"ab/cd/{h}.bin"


def test_public_url_only_when_configured():
    h = "ef01" + "0" * 60
    no_url = S3BlobStore("bucket", client=object())
    assert no_url.public_url(h) is None
    with_url = S3BlobStore(
        "bucket", client=object(), public_base_url="https://cdn.example.com/"
    )
    assert with_url.public_url(h) == f"https://cdn.example.com/ef/01/{h}.bin"


def test_empty_bucket_rejected():
    with pytest.raises(ValueError):
        S3BlobStore("")


@pytest.fixture
def s3_store():
    moto = pytest.importorskip("moto")
    import boto3

    with moto.mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="verity-test")
        yield S3BlobStore("verity-test", client=client)


def test_put_get_roundtrip_and_verifies_hash(s3_store: S3BlobStore):
    data = b"hello r2"
    h = s3_store.put(data)
    assert h == sha256_hex(data)
    assert s3_store.exists(h)
    assert s3_store.get(h) == data
    assert s3_store.count() == 1


def test_put_is_idempotent(s3_store: S3BlobStore):
    data = b"same bytes"
    assert s3_store.put(data) == s3_store.put(data)
    assert s3_store.count() == 1


def test_get_missing_raises_keyerror(s3_store: S3BlobStore):
    with pytest.raises(KeyError):
        s3_store.get("0" * 64)


def test_exists_false_for_absent(s3_store: S3BlobStore):
    assert s3_store.exists("1" * 64) is False


def test_probe_reachable_bucket_is_a_noop(s3_store: S3BlobStore):
    # A reachable bucket: probe returns without walking objects (even when empty).
    assert s3_store.probe() is None


def test_probe_raises_on_unreachable_bucket(s3_store: S3BlobStore):
    # A misconfigured/absent bucket must make the health probe fail (non-200), the
    # same way an AccessDenied from a misscoped R2 token does in prod.
    from botocore.exceptions import ClientError

    bad = S3BlobStore("does-not-exist", client=s3_store.client)
    with pytest.raises(ClientError):
        bad.probe()
