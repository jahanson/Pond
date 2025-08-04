# Pond Test Requirements

This document summarizes what the test suite tells us about how Pond should work.

## Core Services

### 1. Embeddings Service (`pond.services.embeddings`)
- **Function**: `get_embedding(text: str) -> List[float]`
- Calls Ollama at `http://localhost:11434/api/embeddings`
- Uses model `nomic-embed-text`
- Returns 768-dimensional float vector
- On connection error, raises Exception with "embedding service" in message

### 2. Time Service (`pond.services.time_service`)
- **Class**: `TimeService(timezone: Optional[str] = None)`
- **Methods**:
  - `now() -> datetime` - Returns current UTC datetime (timezone-aware)
  - `format_date(dt: datetime) -> str` - Format: "Monday, August 4, 2025"
  - `format_time(dt: datetime) -> str` - Format: "7:03 a.m. PDT"
  - `format_age(dt: datetime) -> str` - Format: "26 hours ago" (relative to now)
  - `parse_interval(interval: str) -> timedelta` - Parse "1 hour", "3 days", "yesterday", etc.
  - `parse_datetime(dt_str: str) -> datetime` - Parse various datetime formats
  - Auto-detects timezone from: config → env → geo-IP → UTC
  - Handles DST transitions correctly

### 3. Validation Service (`pond.services.validation`)
- **Functions**:
  - `validate_memory_length(content: str) -> bool` - Max 7500 chars, reject empty/whitespace
  - `normalize_tag(tag: str) -> str` - Lowercase, singular form, hyphens for spaces, no special chars
  - `validate_tags(tags: List[str]) -> bool` - Max 20 tags allowed

## API Endpoints

### 1. Store Memory
- **Endpoint**: `POST /api/v1/{tenant}/store`
- **Request**: 
  ```json
  {
    "content": "memory text",
    "tags": ["optional", "tags"]  // Optional
  }
  ```
- **Response**:
  ```json
  {
    "splashback": [
      {
        "content": "related memory",
        "similarity": 0.85,
        // ... other fields
      }
    ]
  }
  ```
- First memory returns empty splashback
- Related memories (0.7+ similarity) splash back

### 2. Initialize/Get Context
- **Endpoint**: `POST /api/v1/{tenant}/init`
- **Response**:
  ```json
  {
    "context": "personality context string",
    "recent_memories": ["memory1", "memory2", ...]
  }
  ```
- Returns recent memories and personality context

### 3. Search Memories
- **Endpoint**: `POST /api/v1/{tenant}/search`
- **Request**:
  ```json
  {
    "query": "search text",      // For semantic search
    "entity": "Sparkle",         // For entity search (optional)
    "limit": 10
  }
  ```
- **Response**:
  ```json
  {
    "memories": [...]
  }
  ```

### 4. Get Recent Memories
- **Endpoint**: `POST /api/v1/{tenant}/recent`
- **Request**:
  ```json
  {
    "hours": 24,
    "limit": 50
  }
  ```
- **Response**:
  ```json
  {
    "memories": [...]
  }
  ```

### 5. Health Check
- **Endpoint**: `GET /api/v1/health`
- All responses include `X-Request-ID` header
- Returns comprehensive component status

## Key Features from Tests

### Splashback Effect
- When storing a new memory, related memories (similarity 0.7-0.9) are returned
- Too similar (>0.9) are excluded to avoid déjà vu
- Too different (<0.7) are excluded as irrelevant

### Multi-Tenancy
- Each tenant has isolated memory space
- Tenant names appear in URL paths

### Entity Extraction
- System should extract entities from memories
- Entity-based search should be supported
- Auto-tag generation from content

### Request Tracking
- Every response includes unique `X-Request-ID` header
- Used for debugging and tracing

## Database Schema (from conftest.py)
```sql
CREATE TABLE memories (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    summary TEXT,
    tags JSONB DEFAULT '[]',
    embedding vector(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT true
);
```

Note: The schema in conftest might need updating based on our design doc requirements.