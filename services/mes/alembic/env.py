"""Alembic env.py — reads DATABASE_URL from FACTORYLM_DATABASE_URL env var."""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add services/mes to path so we can import backend.*
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.database import Base  # noqa: E402 — must come after sys.path insert
import backend.models.db_models  # noqa: F401 — registers all models with Base

config = context.config

# Allow FACTORYLM_DATABASE_URL env var to override alembic.ini
db_url = os.environ.get("FACTORYLM_DATABASE_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
