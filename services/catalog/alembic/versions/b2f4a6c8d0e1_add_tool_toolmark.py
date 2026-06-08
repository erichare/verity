"""add tool + toolmark (striated toolmarks) + scan.toolmark_id

Makes the catalog multi-modal across all three mark families: bullet lands
(striated), cartridge marks (impressed), and now **tool marks** (striated) via a
``Study ─< Tool ─< Toolmark ─< Scan`` path. A ``Scan`` may now attach to a
``Toolmark`` in addition to a ``Land`` or a ``Mark``.

RLS: the new tables get the same anon SELECT-only policy as the rest of the
public catalog (Postgres only; no-op on the local-first SQLite dev DB).

Revision ID: b2f4a6c8d0e1
Revises: 1f79f18c6aef
Create Date: 2026-06-08 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2f4a6c8d0e1"
down_revision: Union[str, Sequence[str], None] = "1f79f18c6aef"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# New tables that anon may read (SELECT-only), matching the existing RLS policy.
NEW_TABLES: tuple[str, ...] = ("tool", "toolmark")
ANON_ROLE = "anon"
POLICY = "anon_select"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "tool",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("study_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("kind", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("brand", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.ForeignKeyConstraint(["study_id"], ["study.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("tool", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_tool_external_id"), ["external_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_tool_kind"), ["kind"], unique=False)
        batch_op.create_index(batch_op.f("ix_tool_study_id"), ["study_id"], unique=False)

    op.create_table(
        "toolmark",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.Column("external_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("edge", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("side", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("angle_deg", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["tool_id"], ["tool.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("toolmark", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_toolmark_edge"), ["edge"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_toolmark_external_id"), ["external_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_toolmark_tool_id"), ["tool_id"], unique=False)

    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.add_column(sa.Column("toolmark_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_scan_toolmark_id"), ["toolmark_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_scan_toolmark_id", "toolmark", ["toolmark_id"], ["id"]
        )

    # Public read-only access for the new tables (Postgres/Supabase only).
    if _is_postgres():
        for table in NEW_TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'GRANT SELECT ON TABLE "{table}" TO {ANON_ROLE}')
            op.execute(
                f'CREATE POLICY {POLICY} ON "{table}" '
                f"FOR SELECT TO {ANON_ROLE} USING (true)"
            )


def downgrade() -> None:
    """Downgrade schema."""
    if _is_postgres():
        for table in NEW_TABLES:
            op.execute(f'DROP POLICY IF EXISTS {POLICY} ON "{table}"')
            op.execute(f'REVOKE SELECT ON TABLE "{table}" FROM {ANON_ROLE}')
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')

    with op.batch_alter_table("scan", schema=None) as batch_op:
        batch_op.drop_constraint("fk_scan_toolmark_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_scan_toolmark_id"))
        batch_op.drop_column("toolmark_id")

    with op.batch_alter_table("toolmark", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_toolmark_tool_id"))
        batch_op.drop_index(batch_op.f("ix_toolmark_external_id"))
        batch_op.drop_index(batch_op.f("ix_toolmark_edge"))
    op.drop_table("toolmark")

    with op.batch_alter_table("tool", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_tool_study_id"))
        batch_op.drop_index(batch_op.f("ix_tool_kind"))
        batch_op.drop_index(batch_op.f("ix_tool_external_id"))
    op.drop_table("tool")
