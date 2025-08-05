"""
Shared test fixtures for Pond.
"""
import asyncio
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
import pytest_asyncio
from httpx import AsyncClient

from pond.api.main import app
from pond.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[str, None]:
    """Create an isolated test database with tenant schemas."""
    # Use a fixed test database name (from DATABASE_URL)
    # Each test will create/drop schemas, not databases
    test_db_name = "pond_test"

    # Connect to postgres to ensure test database exists
    admin_conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database="postgres",
    )

    try:
        # Create test database if it doesn't exist
        exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1", test_db_name
        )
        if not exists:
            await admin_conn.execute(f'CREATE DATABASE "{test_db_name}"')

        await admin_conn.close()

        # Connect to the test database to enable pgvector
        test_conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=test_db_name,
        )

        try:
            # Enable pgvector extension at database level
            await test_conn.execute('CREATE EXTENSION IF NOT EXISTS vector')
        finally:
            await test_conn.close()

        yield test_db_name

    finally:
        # Note: We don't drop the database, just clean up schemas
        pass


@pytest_asyncio.fixture
async def test_tenant(test_db: str) -> AsyncGenerator[str, None]:
    """Create a test tenant schema."""
    tenant_name = f"test_{uuid.uuid4().hex[:8]}"

    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=test_db,
    )

    try:
        # Create schema for tenant
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{tenant_name}"')

        # Set search path to tenant schema
        await conn.execute(f'SET search_path TO "{tenant_name}"')

        # pgvector is already enabled at database level

        # Create memories table in tenant schema
        await conn.execute("""
            CREATE TABLE memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                tags JSONB DEFAULT '[]',
                entities JSONB DEFAULT '[]',
                actions JSONB DEFAULT '[]',
                embedding public.vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                active BOOLEAN DEFAULT true
            );
            
            CREATE INDEX idx_memories_created_at ON memories(created_at);
            CREATE INDEX idx_memories_embedding ON memories 
            USING ivfflat (embedding vector_cosine_ops);
            CREATE INDEX idx_memories_entities ON memories USING gin(entities);
        """)

        yield tenant_name

    finally:
        # Clean up test schema
        await conn.execute(f'DROP SCHEMA IF EXISTS "{tenant_name}" CASCADE')
        await conn.close()


@pytest_asyncio.fixture
async def test_client(test_db: str, test_tenant: str) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with an isolated tenant schema."""
    # Override the database name for this test
    settings.db_name = test_db

    # The test client will use test_tenant in URLs
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        async with AsyncClient(
            transport=test_client.transport,
            base_url="http://test",
            headers={"X-API-Key": settings.api_key or "test-key"}
        ) as client:
            # Store tenant name for tests to use
            client.test_tenant = test_tenant
            yield client


@pytest.fixture
def mock_embedding():
    """Return a predictable embedding vector for testing."""
    # 768-dimensional vector with predictable values
    return [0.1] * 768


@pytest.fixture
def mock_ollama_response(monkeypatch):
    """Mock Ollama API responses."""
    async def mock_post(*args, **kwargs):
        class MockResponse:
            def json(self):
                return {"embedding": [0.1] * 768}

            @property
            def status_code(self):
                return 200

        return MockResponse()

    # This will be used to patch httpx.AsyncClient.post
    monkeypatch.setattr("httpx.AsyncClient.post", mock_post)
