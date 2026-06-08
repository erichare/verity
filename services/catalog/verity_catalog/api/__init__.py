"""Verity data-catalog REST API (FastAPI).

A faceted, read-only HTTP layer over the normalized catalog + content-addressed
blob store. Local-first by default (SQLite + local FS); the same code serves
Postgres + S3/R2 when deployed, selected purely by config.
"""
