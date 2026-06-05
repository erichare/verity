"""Alembic environment, wired to Verity's SQLModel metadata and settings.

The database URL comes from ``verity_catalog`` settings (not ``alembic.ini``), so
migrations target whatever the app targets — SQLite locally, Postgres on deploy.
``render_as_batch`` is on so future migrations work on SQLite.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine
from sqlmodel import SQLModel

from alembic import context
from verity_catalog import models  # noqa: F401  (registers tables on SQLModel.metadata)
from verity_catalog.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata
DB_URL = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(DB_URL)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
