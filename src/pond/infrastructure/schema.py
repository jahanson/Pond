"""Database schema management for multi-tenant setup."""

import logging

from asyncpg import Connection

logger = logging.getLogger(__name__)


async def ensure_tenant_schema(conn: Connection, tenant: str) -> None:
    """Ensure a tenant's schema exists with all required tables.

    This function is idempotent - safe to call multiple times.

    Args:
        conn: Database connection (NOT in a transaction)
        tenant: Tenant name (will be used as schema name)
    """
    logger.info(f"Ensuring schema exists for tenant: {tenant}")

    # Validate tenant name
    if not tenant.replace("_", "").isalnum():
        raise ValueError(f"Invalid tenant name: {tenant}")

    # Create schema if not exists
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {tenant}")

    # Switch to the tenant's schema (include public for vector type)
    await conn.execute(f"SET search_path TO {tenant}, public")

    # Create the memories table with all our features
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id SERIAL PRIMARY KEY,
            content TEXT NOT NULL,
            content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
            embedding vector(768),
            forgotten BOOLEAN DEFAULT false,
            metadata JSONB DEFAULT '{}',

            -- Constraints from our spec
            CONSTRAINT content_not_empty CHECK (char_length(content) > 0),
            CONSTRAINT content_max_length CHECK (char_length(content) <= 7500)
        )
    """)

    # Add tsvector column if it doesn't exist (for migration)
    # This handles existing tables that don't have the column yet
    await conn.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_schema = current_schema()
                AND table_name = 'memories' 
                AND column_name = 'content_tsv'
            ) THEN
                ALTER TABLE memories 
                ADD COLUMN content_tsv tsvector 
                GENERATED ALWAYS AS (to_tsvector('english', content)) STORED;
            END IF;
        END $$;
    """)

    # Create indexes for performance
    # Note: CREATE INDEX IF NOT EXISTS requires PostgreSQL 9.5+

    # For full-text search on content
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_content_tsv
        ON memories USING gin (content_tsv)
    """)

    # For vector similarity search (using IVFFlat for better performance at scale)
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_embedding
        ON memories USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # For filtering active memories
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_forgotten
        ON memories (forgotten)
        WHERE NOT forgotten
    """)

    # For tag searches in metadata
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_metadata_tags
        ON memories USING gin ((metadata->'tags'))
    """)

    # For entity searches in metadata
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_metadata_entities
        ON memories USING gin ((metadata->'entities'))
    """)

    # For recent memories queries
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_memories_created_at
        ON memories ((metadata->>'created_at'))
    """)

    logger.info(f"Schema '{tenant}' is ready")


async def list_tenants(conn: Connection) -> list[str]:
    """List all tenant schemas in the database.

    Excludes system schemas (pg_*, information_schema, public).
    """
    rows = await conn.fetch("""
        SELECT schema_name
        FROM information_schema.schemata
        WHERE schema_name NOT IN ('public', 'information_schema')
        AND schema_name NOT LIKE 'pg_%'
        ORDER BY schema_name
    """)
    return [row["schema_name"] for row in rows]


async def tenant_exists(conn: Connection, tenant: str) -> bool:
    """Check if a tenant schema exists."""
    exists = await conn.fetchval(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = $1
        )
    """,
        tenant,
    )
    return exists


async def get_tenant_stats(conn: Connection, tenant: str) -> dict:
    """Get statistics for a tenant.

    Returns:
        Dict with memory_count, embedding_count, oldest_memory, newest_memory
    """
    await conn.execute(f"SET search_path TO {tenant}")

    stats = await conn.fetchrow("""
        SELECT
            COUNT(*) as memory_count,
            COUNT(embedding) as embedding_count,
            MIN(metadata->>'created_at') as oldest_memory,
            MAX(metadata->>'created_at') as newest_memory,
            COUNT(*) FILTER (WHERE forgotten) as forgotten_count
        FROM memories
    """)

    return (
        dict(stats)
        if stats
        else {
            "memory_count": 0,
            "embedding_count": 0,
            "oldest_memory": None,
            "newest_memory": None,
            "forgotten_count": 0,
        }
    )
