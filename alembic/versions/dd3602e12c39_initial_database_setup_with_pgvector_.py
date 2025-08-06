"""Initial database setup with pgvector and tenant schemas

Revision ID: dd3602e12c39
Revises:
Create Date: 2025-08-05 17:56:18.839825

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'dd3602e12c39'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create initial database structure with pgvector extension and tenant schemas."""
    # Create pgvector extension in public schema
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Create default tenants - claude and alpha
    for tenant in ["claude", "alpha"]:
        # Create schema
        op.execute(f"CREATE SCHEMA IF NOT EXISTS {tenant}")

        # Create memories table in tenant schema
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {tenant}.memories (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                content_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
                embedding vector(768),
                forgotten BOOLEAN DEFAULT false,
                metadata JSONB DEFAULT '{{}}',

                CONSTRAINT content_not_empty CHECK (char_length(content) > 0),
                CONSTRAINT content_max_length CHECK (char_length(content) <= 7500)
            )
        """)

        # Create api_keys table for tenant authentication
        op.execute(f"""
            CREATE TABLE IF NOT EXISTS {tenant}.api_keys (
                id SERIAL PRIMARY KEY,
                key_hash VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_used TIMESTAMPTZ,
                active BOOLEAN DEFAULT true
            )
        """)

        # Create indexes for performance
        # Full-text search on content
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_content_tsv
            ON {tenant}.memories USING gin (content_tsv)
        """)

        # Vector similarity search
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_embedding
            ON {tenant}.memories USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        # Active memories filter
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_forgotten
            ON {tenant}.memories (forgotten)
            WHERE NOT forgotten
        """)

        # Tag searches in metadata
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_metadata_tags
            ON {tenant}.memories USING gin ((metadata->'tags'))
        """)

        # Entity searches in metadata
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_metadata_entities
            ON {tenant}.memories USING gin ((metadata->'entities'))
        """)

        # Recent memories queries
        op.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{tenant}_memories_created_at
            ON {tenant}.memories ((metadata->>'created_at'))
        """)


def downgrade() -> None:
    """Drop tenant schemas and pgvector extension."""
    # Drop tenant schemas (CASCADE will drop all tables and indexes)
    for tenant in ["claude", "alpha"]:
        op.execute(f"DROP SCHEMA IF EXISTS {tenant} CASCADE")

    # Drop pgvector extension
    op.execute("DROP EXTENSION IF EXISTS vector")
