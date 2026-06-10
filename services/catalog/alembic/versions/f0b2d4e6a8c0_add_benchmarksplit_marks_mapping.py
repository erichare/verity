"""add benchmarksplit.marks_csv_gz (the mark-hash → scan-hash mapping)

Benchmark pair ids for multi-scan marks are composite hashes (SHA-256 of the
sorted scan hashes), so a third party can only resolve them with the builder's
``marks.csv.gz``. Store it verbatim (gzipped CSV bytes) on the split so the
replication kit — assembled from DB rows alone — can ship it; ``load-benchmark``
populates it from the split directory.

Revision ID: f0b2d4e6a8c0
Revises: c8d0e2f4a6b8
Create Date: 2026-06-10 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f0b2d4e6a8c0"
down_revision: Union[str, Sequence[str], None] = "c8d0e2f4a6b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "benchmarksplit",
        sa.Column("marks_csv_gz", sa.LargeBinary(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("benchmarksplit") as batch_op:
        batch_op.drop_column("marks_csv_gz")
