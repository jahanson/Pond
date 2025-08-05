-- Pond Database Schema
-- Clean, minimal core schema with flexible JSONB metadata

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;

-- Create schema for each tenant (AI)
CREATE SCHEMA IF NOT EXISTS claude;
CREATE SCHEMA IF NOT EXISTS alpha;

-- Set default schema
SET search_path TO claude;

-- Core memories table
CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    embedding vector(768),  -- nomic-embed-text produces 768-dim vectors
    forgotten BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}',
    
    -- Constraints
    CONSTRAINT content_not_empty CHECK (char_length(content) > 0),
    CONSTRAINT content_max_length CHECK (char_length(content) <= 7500)
);

-- Indexes for performance
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memories_forgotten ON memories (forgotten) WHERE NOT forgotten;
CREATE INDEX idx_memories_metadata_tags ON memories USING gin ((metadata->'tags'));
CREATE INDEX idx_memories_metadata_entities ON memories USING gin ((metadata->'entities'));
CREATE INDEX idx_memories_created_at ON memories ((metadata->>'created_at'));

-- Example queries that work with this schema:

-- Store a memory
-- INSERT INTO memories (content, embedding, metadata) 
-- VALUES ($1, $2, $3::jsonb);

-- Search by similarity (0.7-0.9 range for "splash")
-- SELECT id, content, metadata, 1 - (embedding <=> $1) as similarity
-- FROM memories 
-- WHERE NOT forgotten
-- AND embedding <=> $1 < 0.3  -- (1 - 0.7 = 0.3)
-- AND embedding <=> $1 > 0.1  -- (1 - 0.9 = 0.1)
-- ORDER BY embedding <=> $1
-- LIMIT 3;

-- Search by tags
-- SELECT * FROM memories 
-- WHERE metadata->'tags' @> '["python"]'::jsonb
-- AND NOT forgotten;

-- Get recent memories
-- SELECT * FROM memories 
-- WHERE (metadata->>'created_at')::timestamptz > $1
-- AND NOT forgotten
-- ORDER BY (metadata->>'created_at')::timestamptz DESC
-- LIMIT 10;