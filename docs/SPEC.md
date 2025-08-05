# Pond Implementation Specification

This document defines the implementation plan for Pond, a semantic memory system for AI assistants.

## Architecture Overview

```
pond/
├── api/
│   ├── main.py          # FastAPI app, middleware
│   ├── routes/          # API endpoints
│   └── models.py        # Pydantic models
├── services/
│   ├── embeddings.py    # Ollama client
│   ├── entities.py      # spaCy processing  
│   ├── validation.py    # Input validation
│   └── database.py      # Connection pool, queries
├── utils/
│   └── time_service.py  # Timezone-aware formatting
└── config.py            # Settings from environment
```

## Core Design Decisions

### 1. Database Architecture
- **PostgreSQL with pgvector** for semantic search
- **Schema-based multi-tenancy**: one schema per AI (claude, alpha, etc.)
- **Connection pooling**: 10-20 connections shared across tenants
- **Schema switching**: `SET search_path TO tenant` after connection acquire

```sql
CREATE SCHEMA claude;
SET search_path TO claude;

CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    tags JSONB DEFAULT '[]',
    entities JSONB DEFAULT '[]',  -- [{"text": "Sparkle", "type": "PERSON"}]
    actions JSONB DEFAULT '[]',   -- ["steal", "debug"] (lemmatized)
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true
);
```

### 2. Memory Processing Pipeline

All-or-nothing approach - any failure rejects entire memory:

1. Validate content length (max 7500 chars, no empty/whitespace-only)
2. Extract entities with spaCy (`en_core_web_lg`)
3. Extract actions (lemmatized verbs from all tenses)
4. Generate auto-tags (3-5 conservative, from entities/noun chunks/nouns)
5. Normalize and merge with user tags
6. Get embedding from Ollama (nomic-embed-text model)
7. Store in database (transaction)
8. Return splash (0.7-0.9 similarity, max 3, empty is valid)

### 3. Tag Philosophy
- **Normalization**: lowercase, lemmatize, spaces→hyphens
- **User tags preserved**: "python debugging" → "python-debugging"
- **Auto-tags from**: entities, noun chunks, significant nouns
- **No limit on count** (zero-one-infinity rule)
- **Deduplication**: merge user and auto tags

### 4. External Services
- **Ollama**: Required, no startup health check, fail at runtime
- **spaCy**: Use large model for accuracy
- **Timeouts**: 60s for embeddings (cold start), 30s for DB

### 5. API Design
- **Authentication**: Simple API key via `X-API-Key` header
- **Success responses**: Return data directly (no wrappers)
- **Error responses**: `{"error": "message", "request_id": "xxx"}`
- **HTTP status codes**: Use idiomatically (200, 400, 401, 500, 503)

### 6. Time Handling
- **Storage**: Always UTC with timezone (TIMESTAMPTZ)
- **Display**: Convert to local timezone via TimeService
- **Detection cascade**: param → env → geoip → system → UTC

### 7. Testing Strategy
- **Integration tests primary**: Real DB, mock only Ollama
- **Minimal unit tests**: Pure functions only
- **Test full flow**: API → DB → Response
- **Red-green-refactor**: Write tests from spec, then implement

### 8. Search Implementation (Staged)
- **Stage 1**: Semantic similarity only (ship this first)
- **Stage 2**: Add entity/action search
- **Stage 3**: Multi-faceted with scoring algorithm

## Implementation Order

1. **Shared utilities** (TimeService)
2. **Core services** (validation, embeddings, entities)
3. **Database layer** (pool, schema management)
4. **API framework** (FastAPI, middleware, models)
5. **Memory endpoints** (store with splash)
6. **Search endpoint** (semantic only first)
7. **Init and recent endpoints**
8. **Health endpoints**

## What We're NOT Building (Yet)

- Update/delete operations
- Memory relationships
- Dynamic entity learning (see `docs/entity_learning.md`)
- Text classification beyond tags
- Caching layer
- Complex search filters
- Pagination cursors

## Key Configuration

```bash
# Required
DATABASE_URL=postgresql://localhost:5432/pond
OLLAMA_URL=http://localhost:11434

# Optional
PORT=8000
POND_TIMEZONE=America/Los_Angeles
DB_POOL_SIZE=10
DB_POOL_MIN_SIZE=10
DB_POOL_MAX_SIZE=20
EMBEDDING_TIMEOUT=60
LOG_LEVEL=INFO
LOG_FORMAT=json  # or "pretty" for dev
```

## Error Philosophy

- **Fail completely** rather than store incomplete memories
- **Verbose internal logging**, concise API responses  
- **Clear AI-readable errors** for immediate diagnosis
- **Request IDs** for tracing issues
- **No degraded modes** - if it can't work properly, it fails

## API Endpoints

All under `/api/v1/{tenant}/`:
- `POST /store` - Store memory, return splash
- `POST /search` - Semantic search (query required)
- `POST /recent` - Recent memories by time
- `POST /init` - Current time and recent memories
- `GET /health` - Tenant-specific health

Global:
- `GET /api/v1/health` - System health (no auth)

## Success Criteria

System works when:
- Memories store with full extraction pipeline
- Splash returns relevant memories (0.7-0.9)
- Tenant isolation is absolute
- Search finds semantically related content
- All integration tests pass

## Additional Notes

- **Async pattern**: Use async for I/O (DB, HTTP), sync for CPU work (spaCy)
- **No summary field**: Removed from design, memories returned in full
- **Init endpoint**: Returns current time and recent memories (no static context)
- **Code style**: Ruff for formatting/linting, Pyright for type checking
- **Admin privacy**: Future CLI could show metadata without content

## Init Endpoint Details

`POST /api/v1/{tenant}/init` returns:
```json
{
    "current_time": "2025-08-04T19:42:00+00:00",
    "recent_memories": [
        {
            "id": 42,
            "content": "Memory content here",
            "created_at": "2025-08-04T19:36:00+00:00",
            "tags": ["tag1", "tag2"],
            "entities": [{"text": "Entity", "type": "TYPE"}],
            "actions": ["action1"]
        }
    ]
}
```

MCP server will format this as human-readable text with relative timestamps.