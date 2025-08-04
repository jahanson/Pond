# Pond Implementation Specification

This document provides the detailed implementation plan for Pond, bridging our design vision with our test requirements.

## Deployment

### Containerization

Pond is designed to run in Docker containers for:
- Auto-start on system boot
- Easy management via Docker Desktop
- Resource isolation
- Consistent environment

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
RUN pip install -e .
COPY . .
CMD ["python", "-m", "pond.server"]
```

Container considerations:
- Health checks must work within container constraints
- No meaningful host disk space metrics
- Use Docker health check mechanism
- Log to stdout for Docker log collection

## Package Structure

```
pond/
├── __init__.py           # CLI entry point
├── __main__.py          # Allow "python -m pond"
├── server/              # REST API server
│   ├── __init__.py
│   ├── __main__.py      # "python -m pond.server"
│   └── ...
├── mcpserver/           # MCP server
│   ├── __init__.py
│   ├── __main__.py      # "python -m pond.mcpserver"
│   └── ...
├── services/            # Core business logic
│   ├── embeddings.py
│   ├── validation.py
│   └── entities.py
└── utils/               # Shared utilities
    ├── __init__.py
    └── time_service.py  # Shared by MCP and CLI
```

Usage:
- `uv run python -m pond.server` - Start REST API
- `uv run python -m pond.mcpserver` - Start MCP server
- `uv run pond [command]` - CLI commands

## Configuration

### Environment Variables

All configuration via environment variables for container compatibility:

```bash
# Required
DATABASE_URL=postgresql://user:pass@localhost:5432/pond  # Database name configurable!

# Optional with defaults
PORT=8000                          # REST API port
OLLAMA_URL=http://localhost:11434  # Ollama base URL
LOG_LEVEL=INFO                     # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                    # json or pretty (for development)

# MCP Server specific (when we build it)
MCP_TENANT=claude                  # Which tenant this MCP server represents

# Time Service
POND_TIMEZONE=America/Los_Angeles  # Override timezone detection

# Performance tuning
DB_POOL_SIZE=10                    # Database connection pool size
DB_POOL_TIMEOUT=30                 # Seconds to wait for connection
EMBEDDING_TIMEOUT=60               # Seconds to wait for Ollama

# Security
API_KEY=your-secret-key-here       # Required for all API calls except /health
```

### Docker Compose Example

```yaml
services:
  pond:
    image: pond:latest
    environment:
      DATABASE_URL: postgresql://postgres:postgres@db:5432/pond
      OLLAMA_URL: http://ollama:11434
      LOG_FORMAT: pretty
      API_KEY: ${POND_API_KEY:-development-key-change-me}
    ports:
      - "8000:8000"
    depends_on:
      - db
      - ollama
```

### Local Development

For `uv run` outside Docker:
```bash
# .env.local (gitignored)
DATABASE_URL=postgresql://localhost:5432/pond_dev
OLLAMA_URL=http://localhost:11434
PORT=8001
LOG_FORMAT=pretty
API_KEY=development-key-change-me
```

### Frontend Configuration

MCP server and CLI need the API key:
```bash
# MCP server startup
POND_API_KEY=your-key-here python -m pond.mcpserver

# CLI usage  
export POND_API_KEY=your-key-here
pond recent --tenant claude
```

## Core Architecture

### Services Layer (REST API Only)

#### 1. Embeddings Service (`pond.services.embeddings`)
```python
async def get_embedding(text: str) -> List[float]:
    # POST to http://localhost:11434/api/embeddings
    # Model: nomic-embed-text
    # Returns: 768-dimensional vector
    # On error: raise Exception with "embedding service" in message
    pass
```

#### 2. Validation Service (`pond.services.validation`)
```python
def validate_memory_length(content: str) -> bool:
    # Max 7500 chars
    # Reject empty/whitespace-only
    pass

def normalize_tag(tag: str) -> str:
    # lowercase
    # singular form (cats -> cat)
    # spaces to hyphens
    # remove special chars
    pass

def validate_tags(tags: List[str]) -> bool:
    # Only validate format via normalize_tag
    # No count limit (zero-one-infinity rule)
    # Handle None gracefully
    pass
```

#### 4. Entity Service (`pond.services.entities`)
```python
def extract_entities(text: str) -> List[Dict[str, str]]:
    # Use spaCy to extract entities
    # Return: [{"text": "Sparkle", "type": "PERSON"}, ...]
    # Types: PERSON, LOCATION, ORGANIZATION, etc.
    pass

def extract_actions(text: str) -> List[str]:
    # Extract verbs from text
    # Return: ["stole", "debugged", ...]
    pass

def generate_auto_tags(text: str, entities: List[Dict]) -> List[str]:
    # Generate tags from content
    # Include entity names
    # Include significant nouns
    # All normalized via normalize_tag
    pass
```

### Shared Utilities Layer

#### Time Service (`pond.utils.time_service`)
```python
# Shared by MCP server and CLI for human-readable time formatting
# NOT used by REST API (which uses ISO 8601)
class TimeService:
    def __init__(self, timezone: Optional[str] = None):
        # Timezone detection order: param -> env -> geoip -> UTC
        pass
    
    def now(self) -> datetime:
        # Always returns UTC datetime with timezone info
        return datetime.now(ZoneInfo("UTC"))
    
    def format_date(self, dt: datetime) -> str:
        # "Monday, August 4, 2025"
        # Convert to service timezone first
        pass
    
    def format_time(self, dt: datetime) -> str:
        # "7:03 a.m. PDT"
        # Include timezone abbreviation
        pass
    
    def format_age(self, dt: datetime) -> str:
        # "26 hours ago" or "in 5 minutes"
        # Relative to now()
        pass
    
    def parse_interval(self, interval: str) -> timedelta:
        # "1 hour", "3 days", "yesterday"
        # Used by CLI for commands like "pond recent --since yesterday"
        pass
    
    def parse_datetime(self, dt_str: str) -> datetime:
        # Multiple format support for CLI input
        pass
```

### Database Layer

#### Migration Management (Alembic)

We use Alembic from day one to manage schema changes:

```python
# alembic/env.py - Custom logic for multi-schema migrations
async def run_migrations_online():
    """Run migrations on all tenant schemas."""
    connectable = create_async_engine(DATABASE_URL)
    
    async with connectable.connect() as connection:
        # Get all tenant schemas
        result = await connection.execute(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('public', 'information_schema', 'pg_catalog')"
        )
        schemas = [row[0] for row in result]
        
        # Run migration on each schema
        for schema in schemas:
            await connection.execute(f"SET search_path TO {schema}")
            await connection.run_sync(do_run_migrations)
```

Migration commands:
```bash
# Create new migration
alembic revision -m "add_entities_field"

# Run migrations (all schemas)
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

Special considerations:
- pgvector extension must be created per schema
- Each migration runs on ALL tenant schemas
- New tenant creation must run all migrations
- Test database gets migrations too

#### Database Architecture
- **One database** - name from DATABASE_URL (default: `pond`)
- **Multiple schemas** - one per tenant (`claude`, `alpha`, etc.)
- **Schema isolation** - each tenant's data in separate schema
- **Test isolation** - use different database name (e.g., `pond_test`)

Example structure:
```
Database: pond
├── Schema: claude
│   └── Table: memories
├── Schema: alpha
│   └── Table: memories
└── Schema: public (unused)
```

#### Schema Creation (per tenant)
```sql
-- Create schema for new tenant
CREATE SCHEMA IF NOT EXISTS claude;

-- Switch to tenant schema
SET search_path TO claude;

-- Enable pgvector in this schema
CREATE EXTENSION IF NOT EXISTS vector SCHEMA claude;

-- Create tables in tenant schema
CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    summary TEXT,
    tags JSONB DEFAULT '[]',
    entities JSONB DEFAULT '[]',  -- [{"text": "Sparkle", "type": "PERSON"}]
    actions JSONB DEFAULT '[]',   -- ["stole", "ate"]
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true
);

CREATE INDEX idx_memories_created_at ON memories(created_at);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memories_entities ON memories USING gin(entities);
```

#### Connection Management
- Parse database name from DATABASE_URL
- Use asyncpg for async PostgreSQL  
- Schema selection: `SET search_path TO {tenant}`
- Pool connections at database level

### API Layer

#### Request/Response Models
```python
# All use Pydantic for validation

class StoreMemoryRequest:
    content: str
    tags: Optional[List[str]] = None

class Memory:
    content: str
    summary: Optional[str]
    tags: List[str]
    entities: List[Dict[str, str]]
    actions: List[str]
    similarity: Optional[float]  # Only in splashback
    created_at: str  # ISO 8601 UTC (e.g., "2025-08-04T14:03:00Z")

class StoreMemoryResponse:
    splashback: List[Memory]

class InitResponse:
    context: str
    recent_memories: List[str]  # Just content strings

class SearchRequest:
    query: Optional[str]  # For semantic search
    entity: Optional[str]  # For entity search
    limit: int = 10

class SearchResponse:
    memories: List[str]  # Just content strings for now

class RecentRequest:
    hours: int = 24
    limit: int = 50

class RecentResponse:
    memories: List[str]  # Just content strings for now

class TenantHealthResponse:
    status: str  # "healthy", "empty", "inactive"
    tenant: str
    stats: Dict  # Memory counts, date ranges, velocity
    # Exact shape TBD based on implementation experience
    # Ideas to explore:
    # - memory_count, earliest/latest memory
    # - activity patterns (velocity, peak times)
    # - entity/tag statistics
    # - splashback effectiveness metrics
    # - storage usage
```

#### Middleware

**Security Middleware**
```python
async def api_key_middleware(request: Request, call_next):
    # Skip auth for health check
    if request.url.path == "/api/v1/health":
        return await call_next(request)
    
    # Check API key
    api_key = request.headers.get("X-API-Key")
    if not api_key or api_key != settings.api_key:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized"}
        )
    
    return await call_next(request)
```

**Request Tracking Middleware**
- Request ID generation (UUID) for every request
- Add X-Request-ID header to all responses
- Request logging with IDs

**Error Handling Middleware**
```python
async def error_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    
    if isinstance(exc, ValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": str(exc),
                "request_id": request_id
            }
        )
    elif isinstance(exc, OllamaConnectionError):
        return JSONResponse(
            status_code=503,
            content={
                "error": f"Embedding service unavailable: {exc}",
                "request_id": request_id
            }
        )
    else:
        # Log full error internally
        logger.error("unhandled_error", 
                    request_id=request_id,
                    error=str(exc),
                    traceback=traceback.format_exc())
        
        # Return sanitized error to client
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal error processing request",
                "request_id": request_id
            }
        )
```

#### Routes
All routes under `/api/v1/{tenant}/`:
- `POST /store` - Store memory with splashback
- `POST /init` - Get context and recent memories
- `POST /search` - Semantic or entity search
- `POST /recent` - Get recent memories by time
- `GET /health` - Tenant-specific health and statistics

Global health check:
- `GET /api/v1/health` - System health (no auth required)

### Core Logic

#### Splashback Algorithm
```python
async def get_splashback(tenant: str, embedding: List[float]) -> List[Memory]:
    # Query for similar memories
    # Similarity range: 0.7 to 0.9
    # Exclude exact matches (>0.9)
    # Order by similarity descending
    # Limit to 3 results
    # Include all memory fields in response
    # IMPORTANT: Empty splashback is valid and meaningful!
    # It indicates the AI is exploring new conceptual territory
    pass
```

**Design Decision: Threshold-Based Splashback**
- We only return memories above 0.7 similarity threshold
- We do NOT always return top 3 regardless of similarity
- Empty splashback is intentional and informative
- Rationale: 
  - Early days: Unrelated memories would be confusing for identity formation
  - Established AI: Unrelated memories are wasteful noise when exploring new topics
  - Empty splashback signals "this is new territory" which is valuable information

#### Memory Storage Flow (All-or-Nothing)
1. Validate memory length
2. Extract entities and actions  
3. Generate auto-tags from content
4. Merge with user-provided tags
5. Normalize all tags
6. Get embedding from Ollama
7. Store in database (transaction)
8. Get splashback memories
9. Return splashback

**Failure Handling**: ANY step failure = complete rejection
- Database transaction ensures atomicity
- Clear error messages for AI consumption
- No partial states allowed

Example error responses:
```json
{
  "error": "Failed to generate embedding: Ollama service unavailable at http://localhost:11434",
  "request_id": "abc-123"
}

{
  "error": "Memory too long: 8234 characters exceeds maximum of 7500",
  "request_id": "def-456"  
}

{
  "error": "Entity extraction failed: spaCy model 'en_core_web_sm' not found",
  "request_id": "ghi-789"
}
```

#### New Tenant Creation Flow
```python
async def create_tenant_schema(tenant_name: str):
    """Create schema for new tenant and run all migrations."""
    async with get_db_connection() as conn:
        # Create schema
        await conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{tenant_name}"')
        
        # Switch to new schema
        await conn.execute(f'SET search_path TO "{tenant_name}"')
        
        # Run all migrations on new schema
        # This ensures new tenants get current schema
        await run_alembic_migrations(conn, tenant_name)
```

This happens automatically on first request to a new tenant.

#### Search Implementation
- Semantic search: Get embedding of query, find similar
- Entity search: Query entities JSONB field
- Can combine both in future
- Always respect tenant isolation

## Testing Strategy

### Unit Tests Should Pass With:
- Mocked Ollama responses
- No database required
- Focus on business logic

### Integration Tests Should Pass With:
- Real database (test databases)
- Mocked Ollama (predictable embeddings)
- Full API request/response cycle

## Implementation Order

1. **Phase 1: Core Services**
   - Time service with all formatting methods
   - Validation service with tag normalization
   - Embeddings service with Ollama client

2. **Phase 2: Database Layer**
   - Alembic setup with multi-schema support
   - Initial migration (create memories table)
   - Connection management with schema switching
   - Basic CRUD operations

3. **Phase 3: Entity Extraction**
   - spaCy setup and configuration
   - Entity extraction
   - Action extraction
   - Auto-tag generation

4. **Phase 4: API Framework**
   - FastAPI app setup
   - Request/response models
   - Middleware (request IDs)
   - Error handling

5. **Phase 5: Core Features**
   - Memory storage with all extractions
   - Splashback implementation
   - Search (semantic and entity)
   - Init endpoint
   - Basic tenant health endpoint (minimal implementation)

6. **Phase 6: Polish**
   - Comprehensive error handling
   - Performance optimization
   - Complete test coverage

## Key Decisions

1. **No External IDs**: The database ID is never exposed. All operations use content/search.

2. **Simple Entity Extraction**: Extract what's there, don't infer. If it says "Sparkle the cat", extract both "Sparkle" (PERSON) and "cat" as entities.

3. **Tag Philosophy**: Tags are normalized but unlimited in count. User tags and auto-generated tags are merged.

4. **Splashback Range**: 
   - 0.7-0.9 similarity is the "sweet spot" - related but not duplicate
   - Empty splashback is valid when no memories meet threshold
   - We don't force unrelated memories just to fill the response

5. **Time Handling**: 
   - Database: Always store as UTC with timezone (TIMESTAMPTZ)
   - Internal: Always work with UTC datetime objects
   - Display: Convert to AI's timezone only in response formatting
   - The TimeService handles all display formatting at the last moment

6. **Multi-tenancy**: Complete isolation via PostgreSQL schemas (one schema per tenant).

7. **Security**: Simple API key authentication suitable for localhost:
   - Single shared key from environment variable
   - Required header: `X-API-Key: <key>`
   - Health check endpoint is public
   - No complex auth flows for local-only service

8. **Error Philosophy**: Fail completely rather than store incomplete memories
   - All-or-nothing transaction approach
   - Clear, AI-readable error messages
   - No partial states in database
   - Integrity over availability

## What We're NOT Building (Yet)

1. **Update/Delete**: Memories are immutable for now
2. **Pagination Cursors**: Simple limit/offset for now  
3. **Complex Query Filters**: Just search and time-based for now
4. **Memory Relationships**: No explicit linking between memories
5. **Versioning**: No memory versions or edit history
6. **Caching**: No Redis or response caching yet
7. **Full Tenant Health Stats**: Endpoint exists but returns minimal data initially

## Logging and Observability

### Structured Logging

#### Library: structlog
```python
import structlog

logger = structlog.get_logger()

# Development: Pretty, colored output
# Production: JSON lines for parsing
```

#### What to Log

**API Layer**
- Every request: method, path, tenant, request_id, response_time
- Authentication/authorization decisions
- Validation failures with details
- Error responses with stack traces

**Memory Operations**
```python
# Good - logs metadata only
logger.info("memory.stored", 
    tenant="claude",
    request_id=request_id,
    length=len(content),
    tag_count=len(tags),
    entity_count=len(entities),
    splashback_count=len(splashback)
)

# BAD - never log actual memory content!
# logger.info("stored memory", content=memory_content)  # NO!
```

**Embedding Service**
- Ollama requests: start, duration, success/failure
- Token count (if available)
- Cache hits/misses (when we add caching)
- Connection failures and retries

**Database Operations**
- Slow queries (>100ms)
- Connection pool exhaustion
- Transaction rollbacks

**Entity Extraction**
- Processing time
- Entities found by type
- Auto-tags generated count

#### Log Levels
- **DEBUG**: Detailed flow, not for production
- **INFO**: Normal operations, key business events
- **WARNING**: Degraded but functioning (Ollama slow, etc.)
- **ERROR**: Failures that need attention

### Metrics

#### Key Metrics to Track
```python
# Using prometheus_client or similar
request_duration = Histogram('pond_request_duration_seconds', 
                           'Request duration',
                           ['method', 'endpoint', 'status'])

memory_store_duration = Histogram('pond_memory_store_seconds',
                                'Time to store memory',
                                ['tenant'])

splashback_memories = Histogram('pond_splashback_count',
                              'Number of memories in splashback',
                              ['tenant'])

embedding_cache_hit_rate = Counter('pond_embedding_cache_hits',
                                 'Embedding cache hit rate',
                                 ['hit'])
```

### Health Checks

Health endpoint should return what we CAN meaningfully observe in a container:
```json
{
  "status": "healthy",
  "timestamp": "2025-08-04T14:03:00Z",
  "components": {
    "database": {
      "status": "healthy",
      "pool_size": 10,
      "pool_available": 8,
      "response_time_ms": 2
    },
    "ollama": {
      "status": "healthy", 
      "response_time_ms": 45
    }
  },
  "version": "1.0.0",
  "uptime_seconds": 3600
}
```

### Privacy and Security

**Never Log**:
- Memory content
- Full request/response bodies
- Database queries with actual data
- API keys or secrets

**Always Log**:
- Who did what when (audit trail)
- Performance characteristics
- Error conditions
- Resource usage

### Observability Stack (Future)

For production deployment:
1. **Logs**: structlog → stdout → log aggregator
2. **Metrics**: Prometheus + Grafana
3. **Traces**: OpenTelemetry (when we go distributed)
4. **Alerts**: Based on error rates, response times, resource usage

## Success Criteria

All tests pass when:
1. Services implement their contracts exactly
2. Database schema matches test fixtures
3. API returns expected response formats
4. Splashback works within similarity bounds
5. Tenant isolation is absolute
6. Entity extraction identifies people, places, organizations