# Pond

A semantic memory system for AI assistants.

## Architecture

```
+-------------+     +-------------+
|  AI Client  |     |     CLI     |
|    (MCP)    |     |   (Click)   |
+------+------+     +------+------+
       |                   |
       +-------------------+
                |
         +------v------+
         |  REST API   |
         |  (FastAPI)  |
         +------+------+
                |
         +------v------+
         |  PostgreSQL |
         |  + pgvector |
         +-------------+
```

## API

The REST API runs on port 19100:
- Base URL: `http://localhost:19100/api/v1`
- OpenAPI docs: `http://localhost:19100/api/v1/docs`

## Project Structure

- `src/pond/` - Main Python package
  - `api/` - REST API server
  - `mcp/` - MCP server for AI assistants  
  - `cli/` - Command-line interface
  - `models/` - Database models
  - `services/` - Business logic

## Features

- **Memory Storage**: Store and retrieve semantic memories with vector embeddings
- **Splashback**: Related memories surface when storing new ones
- **Multi-tenant**: Separate databases per AI (pond_claude, pond_alpha, etc.)
- **Auto-backup**: Hourly backups of all databases

## Quick Start

```bash
# Install
cd src && uv pip install -e .

# Run API server
uvicorn pond.api.main:app --reload

# Run MCP server
pond-mcp

# Use CLI
pond --help
```