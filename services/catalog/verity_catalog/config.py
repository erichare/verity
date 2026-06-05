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


@lru_cache
def get_settings() -> Settings:
    return Settings()
