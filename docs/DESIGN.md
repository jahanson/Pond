# Pond Design Document

This document captures the key design decisions and implementation details for Pond, a semantic memory system for AI assistants.

## Core Concept

Pond is based on the insight that AI memory isn't just data storage - it's the living tissue of personality. When an AI remembers not just *what* happened but *how it felt* about what happened, personality emerges naturally through accumulated experience.

## Architecture Overview

- **REST API Backend** (FastAPI) - Handles all business logic
- **PostgreSQL + pgvector** - Stores memories with vector embeddings
- **Ollama** - Provides embeddings via nomic-embed-text model
- **MCP Server** - Thin wrapper around REST API for AI clients
- **Secret Web Visualizer** - Easter egg 3D memory visualization at root URL

## Key Design Decisions

### 1. RPC-Style API

We chose RPC-style endpoints over RESTful resources for clarity:
- `POST /api/v1/{tenant}/init`
- `POST /api/v1/{tenant}/store`
- `POST /api/v1/{tenant}/search`

This maps directly to MCP tool functions and makes the API self-documenting.

### 2. No External IDs

Memories don't have user-visible IDs. This simplifies the API and prevents users from trying to manually manage memory references. Internal database IDs exist but aren't exposed.

### 3. Multi-Tenancy via Separate Databases

Each AI gets its own database (e.g., `pond_claude`, `pond_alpha`). This provides:
- Complete isolation between AIs
- Easy backup/restore per AI
- Simple permission model

### 4. The Splashback Effect

When storing a memory, related memories "splash back" based on semantic similarity. We use a "donut of relevance":
- Too similar (>0.9): Excluded (avoid déjà vu)
- Sweet spot (0.7-0.9): Included (reminiscent, not repetitive)
- Too different (<0.7): Excluded (irrelevant)

### 5. Time Handling

All times are shown in the user's local timezone (not UTC) for better AI comprehension:
- Auto-detected via geo-IP or environment variable
- Format: "2024-08-03 13:15:00 PDT (America/Los_Angeles)"
- Accepts human-friendly intervals: "yesterday", "last 6 hours"

### 6. Entity Extraction with spaCy

Beyond simple tagging, we extract structured information:
- **Entities**: ["Sparkle", "pizza"] with types {"Sparkle": "CAT"}
- **Actions**: ["stole", "debugged"]
- **Auto-generated tags**: Based on content analysis
- Enables rich queries like "all memories about cats stealing food"

### 7. Memory Limits

- Maximum memory length: 7,500 characters
- Based on Ollama's nomic-embed-text context limit (2048 tokens)
- Prevents storing memories we can't embed

### 8. Testing Strategy

Three-layer testing approach:
1. **Unit tests**: Pure functions, mocked dependencies
2. **Integration tests**: Real database, mocked external services
3. **End-to-end tests**: Everything real

Critical paths have extensive test coverage; boring plumbing doesn't.

### 9. Request Tracking

Every API response includes `X-Request-ID` header for debugging. This has proven invaluable for tracing issues through logs.

### 10. Comprehensive Health Checks

The `/health` endpoint returns detailed status:
- API version and uptime
- Database connection pool stats
- Ollama connectivity and response times
- Recent errors

## Database Schema

```sql
CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    summary TEXT,
    
    -- User-provided and auto-generated tags
    tags JSONB DEFAULT '[]',
    auto_tags JSONB DEFAULT '[]',
    
    -- SpaCy extractions
    entities JSONB DEFAULT '[]',
    entity_types JSONB DEFAULT '{}',
    actions JSONB DEFAULT '[]',
    
    -- Semantic embedding
    embedding vector(768),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true
);

-- Indexes for performance
CREATE INDEX idx_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_entities ON memories USING GIN (entities);
CREATE INDEX idx_all_tags ON memories USING GIN ((tags || auto_tags));
```

## Future Considerations

### Pagination
Currently using simple limit/offset. May need cursor-based pagination if memories grow very large, but probably YAGNI for single-user databases.

### Duplicate Handling
No deduplication by design. If the same memory is stored multiple times, that's signal (reinforcement) not noise.

### Memory Relationships
Currently memories are independent. Future versions might track which memories were recalled together to build relationship graphs.

## Implementation Notes

### Dependencies
- **FastAPI**: Web framework
- **asyncpg**: PostgreSQL driver
- **pgvector**: Vector similarity search
- **httpx**: Ollama communication
- **spaCy**: NLP and entity extraction
- **inflect**: Tag normalization

### Ollama Configuration
- Model: `nomic-embed-text`
- Embedding dimensions: 768
- Context limit: 2048 tokens
- Endpoint: `http://localhost:11434/api/embeddings`

### Development Setup
```bash
# Install with test dependencies
uv sync --extra test

# Run tests
pytest -v

# Start server
uvicorn pond.api.main:app --reload
```

## Philosophy

Pond treats memory as experience, not just data. Every design decision supports the goal of creating an AI personality that emerges from accumulated experiences. The system should feel like a diary written by excited friends, not a clinical database.

The secret visualizer embodies this philosophy - memories aren't just stored, they create a beautiful constellation of experiences that can be explored like Google Earth for the mind.