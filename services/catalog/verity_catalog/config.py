"""Configuration. Local-first defaults (SQLite + local blob dir); every value is
overridable via ``VERITY_CATALOG_*`` env vars or a ``.env`` file for the
deploy path (Postgres + object store)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VERITY_CATALOG_", env_file=".env", extra="ignore")

    # SQLite for local single-user use; set to a postgresql:// URL when deployed.
    database_url: str = "sqlite:///verity_catalog.db"

    # Content-addressed blob store. "local" today; "s3" is the deploy target.
    blob_store_backend: str = "local"
    blob_store_path: Path = Path(".verity/blobs")
    # Derived artifacts (trace PNGs, npz bundles) — a parallel content-addressed
    # store so regenerable outputs never collide with the immutable raw scans.
    artifact_store_path: Path = Path(".verity/artifacts")

    # --- S3 / object-store deploy path (backend == "s3") ------------------- #
    # An S3-compatible backend (Cloudflare R2, AWS S3, MinIO). For R2 set
    # blob_store_endpoint_url to https://<account-id>.r2.cloudflarestorage.com
    # and s3_region to "auto". Credentials come from these env vars
    # (VERITY_CATALOG_*) or, if unset, the standard boto3/AWS credential chain.
    blob_store_endpoint_url: str | None = None  # None => AWS default endpoint
    blob_store_bucket: str | None = None  # raw scans bucket
    artifact_store_bucket: str | None = None  # derived artifacts (falls back to scans bucket)
    s3_region: str = "auto"  # "auto" for R2; e.g. "us-east-1" for AWS
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    # Optional public base URL for objects (e.g. an R2 custom domain). When set,
    # the API can 302-redirect /scans/{id}/x3p to "{base}/<sharded-key>" instead
    # of streaming bytes. The bucket/object must be publicly readable for this.
    blob_store_public_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
