# Pond API v1

Base URL: `http://localhost:19100/api/v1`

## RPC-Style Endpoints

### Core Operations

#### Initialize
```
POST /api/v1/{tenant}/init
```
Get personality context and recent memories for AI startup.

Response:
```json
{
  "context": "You're talking with Jeffery...",
  "recent_memories": [
    "Just discovered uv is faster than pip!",
    "Sparkle stole pizza again 😂"
  ]
}
```

#### Store
```
POST /api/v1/{tenant}/store
```
Store a new memory and receive related memories that surface.

Request:
```json
{
  "content": "Sparkle stole bacon this morning!",
  "tags": ["sparkle", "theft", "morning"]
}
```

Response:
```json
{
  "splashback": [
    {
      "content": "Sparkle's last theft was yesterday's pizza",
      "similarity": 0.89
    },
    {
      "content": "Starting to think Sparkle plans these heists",
      "similarity": 0.76
    }
  ]
}
```

#### Search
```
POST /api/v1/{tenant}/search
```
Search memories by semantic similarity or tags.

Request:
```json
{
  "query": "python debugging",
  "tags": ["python"],
  "limit": 10
}
```

Response:
```json
{
  "memories": [
    "That semicolon debugging session...",
    "Python error handling patterns"
  ]
}
```

#### Get Recent
```
POST /api/v1/{tenant}/recent
```
Get memories from the last N hours.

Request:
```json
{
  "hours": 24,
  "limit": 10
}
```

Response:
```json
{
  "memories": [
    "Discussed AI personality persistence",
    "Sparkle's morning theft"
  ]
}
```

### Visualization Endpoints

#### Get Vectors
```
POST /api/v1/{tenant}/vectors
```
Get memories with embeddings for 3D visualization.

Request:
```json
{
  "limit": 1000
}
```

Response:
```json
{
  "memories": [
    {
      "content": "Memory text",
      "embedding": [0.123, -0.456, ...],  // 768 dimensions
      "created_at": "2024-08-03T20:15:00Z"
    }
  ]
}
```

### Admin Operations

#### List Tenants
```
POST /api/v1/tenants/list
```
List all AI tenants (databases).

Response:
```json
{
  "tenants": ["claude", "alpha", "chatgpt"]
}
```

#### Create Tenant
```
POST /api/v1/tenants/create
```
Create a new tenant database.

Request:
```json
{
  "name": "claude"
}
```

#### Health Check
```
GET /api/v1/health
```
Service health status.

## MCP Tool Mapping

The MCP tools map directly to the API:

```
init()      → POST /api/v1/{tenant}/init
store()     → POST /api/v1/{tenant}/store  
search()    → POST /api/v1/{tenant}/search
recent()    → POST /api/v1/{tenant}/recent
```

## Notes

- All endpoints use POST for consistency (except health check)
- No IDs exposed in the API - memories are returned directly
- `{tenant}` in URLs refers to the AI name (e.g., "claude", "alpha")
- All timestamps are ISO 8601 in UTC
- Embeddings are 768-dimensional vectors from nomic-embed-text