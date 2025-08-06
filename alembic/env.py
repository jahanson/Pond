"""Alembic environment configuration for Pond."""

import asyncio
import os
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Load .env file
load_dotenv(Path(__file__).parent.parent / ".env")

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get database URL from environment variable or use default
database_url = os.getenv("DATABASE_URL", config.get_main_option("sqlalchemy.url"))
# Convert to async URL for asyncpg driver
if database_url and database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

# We don't have ORM models, so we'll manage the schema manually
target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations with the given connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode with async support."""
    from urllib.parse import urlparse

    import asyncpg

    # Parse database URL to get connection details
    parsed = urlparse(database_url)
    db_name = parsed.path.lstrip('/')

    # Try to create database if it doesn't exist
    try:
        # Connect to postgres database to create our target database
        admin_url = database_url.replace(f"/{db_name}", "/postgres")
        admin_conn = await asyncpg.connect(admin_url.replace("postgresql+asyncpg://", "postgresql://"))

        # Check if database exists
        exists = await admin_conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname = $1)",
            db_name
        )

        if not exists:
            # Create database
            await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
            print(f"Created database: {db_name}")

        await admin_conn.close()
    except Exception as e:
        # If we can't create the database, continue anyway - maybe it exists
        print(f"Note: Could not check/create database: {e}")

    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = database_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
