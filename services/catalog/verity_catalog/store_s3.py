"""S3-compatible content-addressed blob store.

The deploy-path counterpart to :class:`~verity_catalog.store.LocalBlobStore`.
Works against any S3 API — Cloudflare R2, AWS S3, MinIO — selected purely by
``endpoint_url``/credentials, with the *same* sharded key layout
(``<ab>/<cd>/<hash>.bin``) so a blob's address is identical on either backend and
the SHA-256 the catalog records is still the object key. ``boto3`` is an optional
dependency, imported lazily, so the base package stays light.
"""

from __future__ import annotations

from .store import BlobStore, sha256_hex


def blob_key(content_hash: str) -> str:
    """The S3 object key for ``content_hash`` — sharded by the first two hash
    bytes, mirroring ``LocalBlobStore`` exactly so addresses are backend-stable."""
    return f"{content_hash[:2]}/{content_hash[2:4]}/{content_hash}.bin"


class S3BlobStore(BlobStore):
    """Stores immutable byte blobs in an S3 bucket, keyed by SHA-256 content hash.

    ``put`` is idempotent (it skips the upload when the key already exists) and
    self-verifying (it recomputes the hash of the bytes before storing, so a key
    can never disagree with its content). The bucket is treated as immutable and
    write-once, exactly like the filesystem store.
    """

    def __init__(
        self,
        bucket: str,
        *,
        endpoint_url: str | None = None,
        region: str = "auto",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        public_base_url: str | None = None,
        client=None,
    ):
        if not bucket:
            raise ValueError("S3BlobStore requires a bucket name")
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.region = region
        self.public_base_url = public_base_url.rstrip("/") if public_base_url else None
        self._access_key_id = access_key_id
        self._secret_access_key = secret_access_key
        self._client = client  # injectable for tests

    # -- lazy boto3 client ------------------------------------------------- #
    @property
    def client(self):
        if self._client is None:
            try:
                import boto3
            except ImportError as exc:  # pragma: no cover - exercised only without the extra
                raise RuntimeError(
                    "the S3 blob store requires boto3 — install the 's3' extra"
                ) from exc
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self._access_key_id,
                aws_secret_access_key=self._secret_access_key,
            )
        return self._client

    # -- key helpers ------------------------------------------------------- #
    def key_for(self, content_hash: str) -> str:
        return blob_key(content_hash)

    def public_url(self, content_hash: str) -> str | None:
        """A directly-fetchable URL for ``content_hash`` when a public base URL is
        configured (e.g. an R2 custom domain), else ``None``."""
        if not self.public_base_url:
            return None
        return f"{self.public_base_url}/{self.key_for(content_hash)}"

    # -- BlobStore interface ----------------------------------------------- #
    def put(self, data: bytes) -> str:
        content_hash = sha256_hex(data)  # verify: the key is derived from the bytes
        if self.exists(content_hash):
            return content_hash  # dedup: identical content already stored
        self.client.put_object(
            Bucket=self.bucket,
            Key=self.key_for(content_hash),
            Body=data,
            ContentType="application/octet-stream",
        )
        return content_hash

    def get(self, content_hash: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            resp = self.client.get_object(Bucket=self.bucket, Key=self.key_for(content_hash))
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                raise KeyError(content_hash) from exc
            raise
        return resp["Body"].read()

    def exists(self, content_hash: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self.key_for(content_hash))
            return True
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404", "NotFound"):
                return False
            raise

    def count(self) -> int:
        """Number of stored blobs (paginated ``list_objects_v2`` over the bucket)."""
        paginator = self.client.get_paginator("list_objects_v2")
        total = 0
        for page in paginator.paginate(Bucket=self.bucket):
            total += page.get("KeyCount", len(page.get("Contents", [])))
        return total
