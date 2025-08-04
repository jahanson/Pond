# Pond Implementation Specification

This document provides the detailed implementation plan for Pond, bridging our design vision with our test requirements.

## Core Architecture

### Services Layer

#### 1. Time Service (`pond.services.time_service`)
```python
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
        # Case insensitive
        pass
    
    def parse_datetime(self, dt_str: str) -> datetime:
        # Multiple format support
        pass
```

#### 2. Embeddings Service (`pond.services.embeddings`)
```python
async def get_embedding(text: str) -> List[float]:
    # POST to http://localhost:11434/api/embeddings
    # Model: nomic-embed-text
    # Returns: 768-dimensional vector
    # On error: raise Exception with "embedding service" in message
    pass
```

#### 3. Validation Service (`pond.services.validation`)
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

### Database Layer

#### Schema
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    tenant TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    tags JSONB DEFAULT '[]',
    entities JSONB DEFAULT '[]',  -- [{"text": "Sparkle", "type": "PERSON"}]
    actions JSONB DEFAULT '[]',   -- ["stole", "ate"]
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true
);

CREATE INDEX idx_memories_tenant ON memories(tenant);
CREATE INDEX idx_memories_created_at ON memories(created_at);
CREATE INDEX idx_memories_embedding ON memories USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_memories_entities ON memories USING gin(entities);
```

#### Connection Management
- Use asyncpg for async PostgreSQL
- Connection string from environment
- Separate database per tenant (pond_claude, pond_alpha, etc.)
- Pool connections appropriately

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
    created_at: str  # Formatted by time service

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
```

#### Middleware
- Request ID generation (UUID) for every request
- Add X-Request-ID header to all responses
- Request logging with IDs
- Error handling with proper status codes

#### Routes
All routes under `/api/v1/{tenant}/`:
- `POST /store` - Store memory with splashback
- `POST /init` - Get context and recent memories
- `POST /search` - Semantic or entity search
- `POST /recent` - Get recent memories by time
- `GET /health` - Health check (no tenant)

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
    pass
```

#### Memory Storage Flow
1. Validate memory length
2. Extract entities and actions
3. Generate auto-tags from content
4. Merge with user-provided tags
5. Normalize all tags
6. Get embedding from Ollama
7. Store in database
8. Get splashback memories
9. Return splashback

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
   - Schema creation
   - Connection management
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

6. **Phase 6: Polish**
   - Comprehensive error handling
   - Performance optimization
   - Complete test coverage

## Key Decisions

1. **No External IDs**: The database ID is never exposed. All operations use content/search.

2. **Simple Entity Extraction**: Extract what's there, don't infer. If it says "Sparkle the cat", extract both "Sparkle" (PERSON) and "cat" as entities.

3. **Tag Philosophy**: Tags are normalized but unlimited in count. User tags and auto-generated tags are merged.

4. **Splashback Range**: 0.7-0.9 similarity is the "sweet spot" - related but not duplicate.

5. **Time Handling**: 
   - Database: Always store as UTC with timezone (TIMESTAMPTZ)
   - Internal: Always work with UTC datetime objects
   - Display: Convert to AI's timezone only in response formatting
   - The TimeService handles all display formatting at the last moment

6. **Multi-tenancy**: Complete isolation via tenant field. Future: separate databases.

## What We're NOT Building (Yet)

1. **Update/Delete**: Memories are immutable for now
2. **Pagination Cursors**: Simple limit/offset for now  
3. **Complex Query Filters**: Just search and time-based for now
4. **Memory Relationships**: No explicit linking between memories
5. **Versioning**: No memory versions or edit history
6. **Caching**: No Redis or response caching yet

## Success Criteria

All tests pass when:
1. Services implement their contracts exactly
2. Database schema matches test fixtures
3. API returns expected response formats
4. Splashback works within similarity bounds
5. Tenant isolation is absolute
6. Entity extraction identifies people, places, organizations