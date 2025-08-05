"""Integration tests for database infrastructure."""
import asyncio

import pytest

from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import ensure_tenant_schema, list_tenants, tenant_exists

# Import fixtures
from tests.fixtures.database import test_db_pool, test_tenant, ensure_test_database

# Run this once per session to ensure test database exists
pytestmark = pytest.mark.usefixtures("ensure_test_database")


@pytest.mark.asyncio
async def test_database_pool_lifecycle(test_db_pool):
    """Test basic pool creation and closure."""
    # Use the test pool from fixture
    pool = test_db_pool

    # Test we can acquire connections
    async with pool.acquire() as conn:
        version = await conn.fetchval("SELECT version()")
        assert "PostgreSQL" in version

    # Pool will be closed by fixture, so we don't test that here


@pytest.mark.asyncio
async def test_tenant_schema_creation(test_db_pool):
    """Test creating tenant schemas."""
    pool = test_db_pool  # Use test database!

    try:
        # Create a test tenant schema
        async with pool.acquire() as conn:
            await ensure_tenant_schema(conn, "test_tenant_123")

        # Verify it exists
        async with pool.acquire() as conn:
            exists = await tenant_exists(conn, "test_tenant_123")
            assert exists

            # Check tables were created
            tables = await conn.fetch("""
                SELECT tablename 
                FROM pg_tables 
                WHERE schemaname = 'test_tenant_123'
            """)
            table_names = [t['tablename'] for t in tables]
            assert 'memories' in table_names

            # Check indexes were created
            indexes = await conn.fetch("""
                SELECT indexname 
                FROM pg_indexes 
                WHERE schemaname = 'test_tenant_123'
            """)
            index_names = [i['indexname'] for i in indexes]
            assert 'idx_memories_embedding' in index_names
            assert 'idx_memories_forgotten' in index_names

    finally:
        # Cleanup
        async with pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS test_tenant_123 CASCADE")
        pass  # Pool closed by fixture


@pytest.mark.asyncio
async def test_tenant_isolation(test_db_pool):
    """Test that tenants are properly isolated."""
    pool = test_db_pool  # Use test database!

    try:
        # Create two test tenants
        async with pool.acquire() as conn:
            await ensure_tenant_schema(conn, "tenant_a")
            await ensure_tenant_schema(conn, "tenant_b")

        # Insert data in tenant_a
        async with pool.acquire_tenant("tenant_a") as conn:
            await conn.execute("""
                INSERT INTO memories (content, metadata) 
                VALUES ('Memory in tenant A', '{"test": true}')
            """)

        # Insert data in tenant_b
        async with pool.acquire_tenant("tenant_b") as conn:
            await conn.execute("""
                INSERT INTO memories (content, metadata) 
                VALUES ('Memory in tenant B', '{"test": true}')
            """)

        # Verify isolation - tenant_a should only see its memory
        async with pool.acquire_tenant("tenant_a") as conn:
            memories = await conn.fetch("SELECT content FROM memories")
            assert len(memories) == 1
            assert memories[0]['content'] == 'Memory in tenant A'

        # tenant_b should only see its memory
        async with pool.acquire_tenant("tenant_b") as conn:
            memories = await conn.fetch("SELECT content FROM memories")
            assert len(memories) == 1
            assert memories[0]['content'] == 'Memory in tenant B'

    finally:
        # Cleanup
        async with pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS tenant_a CASCADE")
            await conn.execute("DROP SCHEMA IF EXISTS tenant_b CASCADE")
        pass  # Pool closed by fixture


@pytest.mark.asyncio
async def test_list_tenants(test_db_pool):
    """Test listing all tenants."""
    pool = test_db_pool  # Use test database!

    try:
        # Create some test tenants
        async with pool.acquire() as conn:
            await ensure_tenant_schema(conn, "alpha")
            await ensure_tenant_schema(conn, "beta")
            await ensure_tenant_schema(conn, "gamma")

        # List tenants
        async with pool.acquire() as conn:
            tenants = await list_tenants(conn)

        # Should include our test tenants (and maybe others)
        assert "alpha" in tenants
        assert "beta" in tenants
        assert "gamma" in tenants

        # Should not include system schemas
        assert "public" not in tenants
        assert "pg_catalog" not in tenants

    finally:
        # Cleanup
        async with pool.acquire() as conn:
            await conn.execute("DROP SCHEMA IF EXISTS alpha CASCADE")
            await conn.execute("DROP SCHEMA IF EXISTS beta CASCADE")
            await conn.execute("DROP SCHEMA IF EXISTS gamma CASCADE")
        pass  # Pool closed by fixture


@pytest.mark.asyncio
async def test_invalid_tenant_name(test_db_pool):
    """Test that invalid tenant names are rejected."""
    pool = test_db_pool  # Use test database!

    # Try SQL injection attempts
    with pytest.raises(ValueError, match="Invalid tenant name"):
        async with pool.acquire_tenant("tenant'; DROP TABLE memories; --") as conn:
            pass

    # Try special characters
    with pytest.raises(ValueError, match="Invalid tenant name"):
        async with pool.acquire_tenant("tenant-name") as conn:
            pass


@pytest.mark.asyncio
async def test_connection_pool_exhaustion():
    """Test pool behavior when all connections are in use."""
    # Create a small pool for testing
    from pond.config import settings

    # Save original settings
    original_url = settings.database_url
    original_min = settings.db_pool_min_size
    original_max = settings.db_pool_max_size

    # Override for test with pond_test database
    settings.database_url = settings.database_url.replace('/pond', '/pond_test')
    settings.db_pool_min_size = 1
    settings.db_pool_max_size = 2  # Very small pool

    pool = DatabasePool()

    try:
        await pool.initialize()

        # Acquire all connections
        conn1 = await pool.pool.acquire()
        conn2 = await pool.pool.acquire()

        # Try to acquire one more - should timeout
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                pool.pool.acquire(),
                timeout=1.0  # Short timeout for test
            )

        # Release connections
        await pool.pool.release(conn1)
        await pool.pool.release(conn2)

    finally:
        # Restore original settings
        settings.database_url = original_url
        settings.db_pool_min_size = original_min
        settings.db_pool_max_size = original_max
        await pool.close()
