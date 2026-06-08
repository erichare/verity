"""enable RLS + anon SELECT-only policy (PostgreSQL only)

Go-live hardening for the Supabase/Postgres deploy: the catalog is a *public*,
read-only mirror of public-domain scans, so we enable row-level security on every
table and grant an anon SELECT-only policy. Writes go through the privileged
ingestion role (which bypasses RLS), never the anon API key.

GUARDED to PostgreSQL: ``op.get_bind().dialect.name`` is checked so this is a
no-op on SQLite (the local-first dev DB Alembic also runs against). SQLite has no
RLS, and the catalog is single-user there.

Revision ID: 1f79f18c6aef
Revises: 5ed39b57d680
Create Date: 2026-06-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '1f79f18c6aef'
down_revision: Union[str, Sequence[str], None] = '5ed39b57d680'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Every catalog table that anon may read. Reference/derived tables included so the
# whole public catalog is browseable read-only.
TABLES: tuple[str, ...] = (
    "study",
    "firearm",
    "bullet",
    "cartridgecase",
    "land",
    "mark",
    "instrument",
    "scan",
    "scantrace",
    "pairdiagnostic",
)

# Supabase's anonymous role. SELECT is granted to it directly (DDL GRANT) and an
# RLS policy then permits the rows; both are required under RLS.
ANON_ROLE = "anon"
POLICY = "anon_select"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""
    if not _is_postgres():
        return  # no-op on SQLite (local-first dev DB has no RLS)
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'GRANT SELECT ON TABLE "{table}" TO {ANON_ROLE}')
        # SELECT-only policy for anon: read everything, write nothing.
        op.execute(
            f'CREATE POLICY {POLICY} ON "{table}" '
            f"FOR SELECT TO {ANON_ROLE} USING (true)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    if not _is_postgres():
        return
    for table in TABLES:
        op.execute(f'DROP POLICY IF EXISTS {POLICY} ON "{table}"')
        op.execute(f'REVOKE SELECT ON TABLE "{table}" FROM {ANON_ROLE}')
        op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
