"""Shared test fixtures and configuration."""

import asyncio
import os
from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient

from pond.infrastructure.database import DatabasePool

# Test configuration
TEST_TENANT = "test_tenant"
TEST_API_KEY = "test-api-key-12345"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def db_pool() -> AsyncGenerator[DatabasePool, None]:
    """Create a database pool for testing."""
    pool = DatabasePool()
    await pool.initialize()

    # Create test schema
    async with pool.acquire() as conn:
        # First ensure pgvector extension exists in public schema
        await conn.execute("SET search_path TO public")
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        quoted_tenant = await conn.fetchval("SELECT quote_ident($1)", TEST_TENANT)
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_tenant} CASCADE")
        await conn.execute(f"CREATE SCHEMA {quoted_tenant}")

        # Create tables in test schema - vector type is available from public schema
        await conn.execute(f"SET search_path TO {quoted_tenant}, public")
        await conn.execute("""
            CREATE TABLE memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                tags JSONB DEFAULT '[]'::jsonb,
                entities JSONB DEFAULT '[]'::jsonb,
                actions JSONB DEFAULT '[]'::jsonb,
                embedding vector(768),
                created_at TIMESTAMPTZ DEFAULT NOW(),
                active BOOLEAN DEFAULT true
            )
        """)

        # Create indexes
        await conn.execute("CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops)")
        await conn.execute("CREATE INDEX idx_memories_created_at ON memories(created_at DESC)")
        await conn.execute("CREATE INDEX idx_memories_active ON memories(active) WHERE active = true")

        # Create API key table in public schema
        await conn.execute("SET search_path TO public")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                tenant VARCHAR(63) PRIMARY KEY,
                api_key_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

        # Insert test API key
        import hashlib
        key_hash = hashlib.sha256(TEST_API_KEY.encode()).hexdigest()
        await conn.execute(
            "INSERT INTO api_keys (tenant, api_key_hash) VALUES ($1, $2) ON CONFLICT (tenant) DO UPDATE SET api_key_hash = $2",
            TEST_TENANT, key_hash
        )

    yield pool

    # Cleanup
    async with pool.acquire() as conn:
        quoted_tenant = await conn.fetchval("SELECT quote_ident($1)", TEST_TENANT)
        await conn.execute(f"DROP SCHEMA IF EXISTS {quoted_tenant} CASCADE")
        await conn.execute("DELETE FROM api_keys WHERE tenant = $1", TEST_TENANT)

    await pool.close()


@pytest.fixture
async def client(db_pool: DatabasePool) -> AsyncGenerator[AsyncClient, None]:
    """Create an async HTTP client for testing."""
    # Mock the embedding provider to use mock embeddings
    os.environ["EMBEDDING_PROVIDER"] = "mock"

    # Create a test-specific app instance to avoid modifying the global one
    from fastapi import FastAPI

    from pond.api.middleware import (
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        RequestIDMiddleware,
    )
    from pond.api.routes import health, memories
    from pond.domain import MemoryRepository
    from pond.infrastructure.auth import APIKeyManager

    # Create a fresh v1 API app
    test_api_v1 = FastAPI(
        title="Pond API v1 Test",
        version="1.0.0",
    )

    # Include routes
    test_api_v1.include_router(health.router)
    test_api_v1.include_router(memories.router)

    # Create main test app
    test_app = FastAPI(title="Pond Test")

    # Initialize state
    test_app.state.db_pool = db_pool
    test_app.state.api_key_manager = APIKeyManager(db_pool)
    test_app.state.memory_repository = MemoryRepository(db_pool)

    # Share state with v1 app
    test_api_v1.state = test_app.state

    # Mount v1 API
    test_app.mount("/api/v1", test_api_v1)

    # Add middleware with MOCK authentication for testing
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request

    class MockAuthMiddleware(BaseHTTPMiddleware):
        """Mock auth that accepts our test API key."""
        async def dispatch(self, request: Request, call_next):
            # Check for API key header
            api_key = request.headers.get("X-API-Key")
            if api_key == TEST_API_KEY:
                request.state.tenant = TEST_TENANT
            else:
                request.state.tenant = None
            return await call_next(request)

    test_app.add_middleware(MockAuthMiddleware)
    test_app.add_middleware(ErrorHandlingMiddleware)
    test_app.add_middleware(LoggingMiddleware)
    test_app.add_middleware(RequestIDMiddleware)

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def api_headers() -> dict:
    """Get headers with test API key."""
    return {"X-API-Key": TEST_API_KEY}
