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

### Prerequisites

- PostgreSQL with pgvector extension
- Ollama with nomic-embed-text model (`ollama pull nomic-embed-text`)

### Using Docker (Recommended)

```bash
# 1. Copy and configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL and OLLAMA_URL

# 2. Start the REST API
docker compose up

# The API will be available at http://localhost:19100
```

### Manual Installation

```bash
export POND_API_KEY=pond_sk_1234567890
export TENANT_NAME=test_tenant

# Install
uv pip install -r pyproject.toml
python -m spacy download en_core_web_lg

# Run API server
uvicorn pond.api.main:app --reload --port 19100

# Run MCP server
uv run python -m pond.mcp

# Add MCP Server to Claude Code
claude mcp add pond --env POND_API_KEY=$POND_API_KEY -- uv run --directory /home/jahanson/dev/Pond python -m pond.mcp

# Pond CLI
## Use CLI
pond --help

## create a new tenant
pond tenant create $TENANT_NAME

## generate a new key
pond key generate $TENANT_NAME
```

## Docker Configuration

The containerized REST server needs access to:
- Your PostgreSQL database
- Your Ollama instance

If these are running on your host machine, use `host.docker.internal` in your `.env`:
```
DATABASE_URL=postgresql://postgres:password@host.docker.internal:5432/pond
OLLAMA_URL=http://host.docker.internal:11434
```

### Docker Commands

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Rebuild after code changes
docker compose build
docker compose up
```