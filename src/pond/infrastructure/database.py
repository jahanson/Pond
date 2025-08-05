"""Database connection pool and management."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import asyncpg
from asyncpg import Connection, Pool

from pond.config import settings

logger = logging.getLogger(__name__)


class DatabasePool:
    """Manages database connection pool for the application.

    This class handles:
    - Connection pooling (reusing expensive connections)
    - Tenant isolation via PostgreSQL schemas
    - Proper connection lifecycle management
    """

    def __init__(self):
        self._pool: Pool | None = None

    async def initialize(self) -> None:
        """Initialize the connection pool.

        Called once at application startup.
        """
        logger.info(
            f"Initializing database pool with {settings.db_pool_min_size}-{settings.db_pool_max_size} connections"
        )

        # Define setup function to register vector type for each connection
        async def setup_connection(conn):
            from pgvector.asyncpg import register_vector

            await register_vector(conn)

        self._pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            # Command timeout for long operations like similarity search
            command_timeout=30.0,
            # pgvector requires this type to be registered
            server_settings={
                "jit": "off"  # JIT can slow down pgvector operations
            },
            # Register vector type for each connection
            setup=setup_connection,
        )

        # Test the pool and register vector type
        async with self._pool.acquire() as conn:
            # Register the vector type for pgvector in public schema
            # This makes it available to all schemas
            await conn.execute("SET search_path TO public")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

            # Register vector type with asyncpg
            from pgvector.asyncpg import register_vector

            await register_vector(conn)

            version = await conn.fetchval("SELECT version()")
            logger.info(f"Connected to PostgreSQL: {version}")

    async def close(self) -> None:
        """Close all connections in the pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database pool closed")

    @property
    def pool(self) -> Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError(
                "Database pool not initialized. Call initialize() first."
            )
        return self._pool

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[Connection]:
        """Acquire a connection from the pool.

        Usage:
            async with db_pool.acquire() as conn:
                await conn.fetch("SELECT * FROM memories")
        """
        async with self.pool.acquire() as conn:
            yield conn

    @asynccontextmanager
    async def acquire_tenant(self, tenant: str) -> AsyncIterator[Connection]:
        """Acquire a connection with tenant schema set.

        This ensures all queries run in the tenant's schema.

        Args:
            tenant: Schema name (e.g., 'claude', 'alpha')

        Usage:
            async with db_pool.acquire_tenant('claude') as conn:
                # All queries here run in the 'claude' schema
                await conn.fetch("SELECT * FROM memories")
        """
        async with self.pool.acquire() as conn:
            # Sanitize tenant name to prevent SQL injection
            # Only allow alphanumeric and underscore
            if not tenant.replace("_", "").isalnum():
                raise ValueError(f"Invalid tenant name: {tenant}")

            # Set the search path for this connection
            await conn.execute(f"SET search_path TO {tenant}, public")
            yield conn
            # search_path automatically resets when connection returns to pool


# Global pool instance
_db_pool = DatabasePool()


def get_db_pool() -> DatabasePool:
    """Get the global database pool instance."""
    return _db_pool
