"""
Shared test fixtures for Pond.
"""
import asyncio
import uuid
from typing import AsyncGenerator

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
    """Create an isolated test database for each test."""
    # Generate unique test database name
    test_db_name = f"pond_test_{uuid.uuid4().hex[:8]}"
    
    # Connect to postgres to create test database
    admin_conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database="postgres",
    )
    
    try:
        # Create test database
        await admin_conn.execute(f'CREATE DATABASE "{test_db_name}"')
        
        # Connect to test database and set up schema
        test_conn = await asyncpg.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=test_db_name,
        )
        
        try:
            # Create pgvector extension
            await test_conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            
            # Create memories table
            await test_conn.execute("""
                CREATE TABLE memories (
                    id SERIAL PRIMARY KEY,
                    content TEXT NOT NULL,
                    summary TEXT,
                    tags JSONB DEFAULT '[]',
                    embedding vector(768),
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    active BOOLEAN DEFAULT true
                );
                
                CREATE INDEX idx_embedding ON memories 
                USING ivfflat (embedding vector_cosine_ops);
                CREATE INDEX idx_active_created ON memories(active, created_at DESC);
                CREATE INDEX idx_tags ON memories USING GIN (tags);
            """)
            
            yield test_db_name
            
        finally:
            await test_conn.close()
            
    finally:
        # Clean up test database
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{test_db_name}"')
        await admin_conn.close()


@pytest_asyncio.fixture
async def test_client(test_db: str) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with an isolated database."""
    # Override the database name for this test
    settings.db_name = test_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
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