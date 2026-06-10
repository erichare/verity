"""add benchmark tables (split / fold / pair / submission) + anon-SELECT RLS

The open-benchmark contract lives in the catalog DB: frozen splits (pairs +
source-disjoint folds, committed to by a split_hash), and scored leaderboard
submissions. All four tables are publicly readable (anon SELECT, same policy as
the rest of the catalog); writes happen only through the privileged service
role (the loader CLI and the submission endpoint), never the anon key.

Revision ID: d4e6f8a0b2c4
Revises: b2f4a6c8d0e1
Create Date: 2026-06-09 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e6f8a0b2c4"
down_revision: Union[str, Sequence[str], None] = "b2f4a6c8d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES: tuple[str, ...] = (
    "benchmarksplit",
    "benchmarkfold",
    "benchmarkpair",
    "benchmarksubmission",
)
ANON_ROLE = "anon"
POLICY = "anon_select"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "benchmarksplit",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("modality", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("split_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("protocol_version", sa.Integer(), nullable=False),
        sa.Column("n_pairs", sa.Integer(), nullable=False),
        sa.Column("n_km", sa.Integer(), nullable=False),
        sa.Column("n_sources", sa.Integer(), nullable=False),
        sa.Column("n_folds", sa.Integer(), nullable=False),
        sa.Column("provenance", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmarksplit_name"), "benchmarksplit", ["name"], unique=True)
    op.create_index(op.f("ix_benchmarksplit_modality"), "benchmarksplit", ["modality"])
    op.create_index(op.f("ix_benchmarksplit_split_hash"), "benchmarksplit", ["split_hash"])

    op.create_table(
        "benchmarkfold",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("split_id", sa.Integer(), nullable=False),
        sa.Column("fold_index", sa.Integer(), nullable=False),
        sa.Column("n_test_pairs", sa.Integer(), nullable=False),
        sa.Column("test_sources", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["split_id"], ["benchmarksplit.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("split_id", "fold_index", name="uq_benchmarkfold_split_index"),
    )
    op.create_index(op.f("ix_benchmarkfold_split_id"), "benchmarkfold", ["split_id"])

    op.create_table(
        "benchmarkpair",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("split_id", sa.Integer(), nullable=False),
        sa.Column("pair_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hash_a", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("hash_b", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("label", sa.Integer(), nullable=False),
        sa.Column("source_a", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_b", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("folds", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.ForeignKeyConstraint(["split_id"], ["benchmarksplit.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("split_id", "pair_id", name="uq_benchmarkpair_split_pair"),
    )
    op.create_index(op.f("ix_benchmarkpair_split_id"), "benchmarkpair", ["split_id"])
    op.create_index(op.f("ix_benchmarkpair_pair_id"), "benchmarkpair", ["pair_id"])

    op.create_table(
        "benchmarksubmission",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("split_id", sa.Integer(), nullable=False),
        sa.Column("submitter", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("is_reference", sa.Boolean(), nullable=False),
        sa.Column("cllr", sa.Float(), nullable=False),
        sa.Column("cllr_std", sa.Float(), nullable=False),
        sa.Column("cllr_min", sa.Float(), nullable=False),
        sa.Column("auc", sa.Float(), nullable=False),
        sa.Column("calibration_loss", sa.Float(), nullable=False),
        sa.Column("metrics", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["split_id"], ["benchmarksplit.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_benchmarksubmission_split_id"), "benchmarksubmission", ["split_id"])
    op.create_index(op.f("ix_benchmarksubmission_submitter"), "benchmarksubmission", ["submitter"])
    op.create_index(
        op.f("ix_benchmarksubmission_is_reference"), "benchmarksubmission", ["is_reference"]
    )
    op.create_index(op.f("ix_benchmarksubmission_cllr"), "benchmarksubmission", ["cllr"])
    op.create_index(
        op.f("ix_benchmarksubmission_calibration_loss"),
        "benchmarksubmission",
        ["calibration_loss"],
    )

    # RLS + anon SELECT-only (PostgreSQL/Supabase deploys; no-op on SQLite).
    if _is_postgres():
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
            op.execute(f'GRANT SELECT ON TABLE "{table}" TO {ANON_ROLE}')
            op.execute(
                f'CREATE POLICY {POLICY} ON "{table}" FOR SELECT TO {ANON_ROLE} USING (true)'
            )


def downgrade() -> None:
    """Downgrade schema."""
    if _is_postgres():
        for table in TABLES:
            op.execute(f'DROP POLICY IF EXISTS {POLICY} ON "{table}"')
            op.execute(f'REVOKE SELECT ON TABLE "{table}" FROM {ANON_ROLE}')
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
    op.drop_table("benchmarksubmission")
    op.drop_table("benchmarkpair")
    op.drop_table("benchmarkfold")
    op.drop_table("benchmarksplit")
