"""Database fixtures for testing."""
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest_asyncio

from pond.config import settings
from pond.infrastructure.database import DatabasePool


@pytest_asyncio.fixture
async def test_db_pool() -> AsyncGenerator[DatabasePool, None]:
    """Create a database pool connected to the test database.
    
    Uses pond_test database which should already exist.
    Each test gets isolated via unique tenant schemas.
    """
    # Override the database URL to use test database
    original_url = settings.database_url
    settings.database_url = settings.database_url.replace('/pond', '/pond_test')

    pool = DatabasePool()
    await pool.initialize()

    yield pool

    await pool.close()
    # Restore original URL
    settings.database_url = original_url


@pytest_asyncio.fixture
async def test_tenant(test_db_pool: DatabasePool) -> AsyncGenerator[str, None]:
    """Create a unique tenant schema for test isolation.
    
    Automatically cleaned up after test.
    """
    # Generate unique tenant name
    tenant = f"test_{uuid.uuid4().hex[:8]}"

    # Create the schema
    async with test_db_pool.acquire() as conn:
        from pond.infrastructure.schema import ensure_tenant_schema
        await ensure_tenant_schema(conn, tenant)

    yield tenant

    # Cleanup
    async with test_db_pool.acquire() as conn:
        await conn.execute(f"DROP SCHEMA IF EXISTS {tenant} CASCADE")


@pytest_asyncio.fixture
async def ensure_test_database():
    """Ensure pond_test database exists with pgvector extension.
    
    This runs once per test session.
    """
    # Connect to postgres database to create test database
    conn = await asyncpg.connect(
        host=settings.db_host or "localhost",
        port=settings.db_port or 5432,
        user=settings.db_user or "postgres",
        password=settings.db_password,
        database="postgres",
    )

    try:
        # Create test database if needed
        exists = await conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = 'pond_test'"
        )
        if not exists:
            await conn.execute('CREATE DATABASE "pond_test"')
            print("Created pond_test database")
    finally:
        await conn.close()

    # Now connect to test database and ensure pgvector
    conn = await asyncpg.connect(
        host=settings.db_host or "localhost",
        port=settings.db_port or 5432,
        user=settings.db_user or "postgres",
        password=settings.db_password,
        database="pond_test",
    )

    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        print("Ensured pgvector extension in pond_test")
    finally:
        await conn.close()
