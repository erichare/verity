"""enable RLS on alembic_version (deny-all for API roles)

Alembic's own bookkeeping table is created outside the model layer, so the
catalog's RLS migrations never covered it. In a Supabase deploy the ``public``
schema is exposed through PostgREST and default privileges grant new tables to
the API roles — leaving migration state readable *and writable* by ``anon``
(flagged Critical by the Supabase security advisor, lint 0013).

Enable RLS with **no policies** (deny-all for ``anon``/``authenticated``) and
revoke their direct grants for defense in depth. Alembic itself is unaffected:
it connects as the table's owner (``postgres``), which bypasses RLS unless
FORCE is set (it is not).

Revision ID: c8d0e2f4a6b8
Revises: d4e6f8a0b2c4
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c8d0e2f4a6b8"
down_revision: Union[str, Sequence[str], None] = "d4e6f8a0b2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

API_ROLES = ("anon", "authenticated")


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""
    if not _is_postgres():
        return  # no-op on SQLite (local-first dev DB has no RLS or API roles)
    op.execute("ALTER TABLE alembic_version ENABLE ROW LEVEL SECURITY")
    for role in API_ROLES:
        op.execute(f"REVOKE ALL ON TABLE alembic_version FROM {role}")


def downgrade() -> None:
    """Downgrade schema."""
    if not _is_postgres():
        return
    op.execute("ALTER TABLE alembic_version DISABLE ROW LEVEL SECURITY")
