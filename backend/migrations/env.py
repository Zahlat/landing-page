"""Async Alembic environment.

Database URL, in order of precedence:
1. sqlalchemy.url set programmatically on the Config (the test suite does this)
2. `alembic -x db=test ...` -> TEST_DATABASE_URL
3. DATABASE_URL
alembic.ini deliberately holds no URL, so no credentials live in a committed file.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401  (registers every model on Base.metadata)
from app.core.config import get_settings
from app.models.base import Base

config = context.config

if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    explicit = config.get_main_option("sqlalchemy.url")
    if explicit:
        return explicit
    settings = get_settings()
    if context.get_x_argument(as_dictionary=True).get("db") == "test":
        if not settings.test_database_url:
            raise RuntimeError("TEST_DATABASE_URL is not set")
        return settings.test_database_url.get_secret_value()
    return settings.database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(_database_url(), poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
