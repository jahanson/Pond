"""
Pond MCP Server - FastMCP 2.0 implementation.

Exposes REST API endpoints as MCP tools with Jinja2 templating for responses.
"""

import uuid
from pathlib import Path
from typing import Any

import httpx
import structlog
import yaml
from fastmcp import FastMCP
from jinja2 import Environment, FileSystemLoader
from pydantic import Field

from pond.mcp.config import get_settings
from pond.utils.time_service import TimeService

logger = structlog.get_logger()


def _is_verbose_logging() -> bool:
    """Check if verbose logging is enabled via log level."""
    import os
    log_level = os.getenv("LOG_LEVEL", "INFO")
    return log_level.upper() == "DEBUG"


# Initialize FastMCP server
mcp = FastMCP(
    name="Pond Memory System",
    instructions="""
    This server provides semantic memory storage and retrieval for AI assistants.

    Available operations:
    - Store memories with automatic tagging and entity extraction
    - Search memories using semantic similarity and text matching
    - Retrieve recent memories within a time window
    - Initialize context with current time and recent memories
    - Check system and tenant health
    """,
)

# Set up Jinja2 environment
template_dir = Path(__file__).parent / "templates"
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False,  # MCP tools return plain text, not HTML  # noqa: S701
)

# Initialize TimeService
time_service = TimeService()

# Settings will be lazy-loaded when needed
_settings = None


def get_config():
    """Get configuration settings (lazy-loaded)."""
    global _settings
    if _settings is None:
        _settings = get_settings()
    return _settings


def format_age(dt_str: str) -> str:
    """Format an ISO datetime string as a relative age."""
    if not dt_str:
        return ""
    dt = time_service.parse_datetime(dt_str)
    return time_service.format_age(dt)


def format_datetime(dt_str: str) -> str:
    """Format an ISO datetime string as a human-readable datetime."""
    if not dt_str:
        return ""
    dt = time_service.parse_datetime(dt_str)
    return time_service.format_datetime(dt)


# Register the filters with Jinja2
jinja_env.filters["format_age"] = format_age
jinja_env.filters["format_datetime"] = format_datetime
jinja_env.filters["get_day_label"] = lambda dt_str: time_service.get_day_label(time_service.parse_datetime(dt_str))
jinja_env.filters["get_date_key"] = lambda dt_str: time_service.get_date_key(time_service.parse_datetime(dt_str))


async def make_request(method: str, endpoint: str, json: dict | None = None) -> dict:
    """Make an authenticated request to the Pond API."""
    # Generate a unique request ID for tracing
    mcp_request_id = str(uuid.uuid4())

    config = get_config()
    url = f"{config.pond_url}/api/v1/{endpoint}"
    headers = {"X-API-Key": config.pond_api_key} if config.pond_api_key else {}

    # Add MCP request ID for correlation
    headers["X-MCP-Request-ID"] = mcp_request_id

    logger.info(
        "mcp_api_request_start",
        mcp_request_id=mcp_request_id,
        method=method,
        endpoint=endpoint,
        url=url,
        has_api_key=bool(config.pond_api_key),
        request_body_keys=list(json.keys()) if json else None,
    )

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json or {})
            else:
                logger.error(
                    "mcp_unsupported_method",
                    mcp_request_id=mcp_request_id,
                    method=method,
                )
                raise ValueError(f"Unsupported method: {method}")

            logger.info(
                "mcp_api_response_received",
                mcp_request_id=mcp_request_id,
                status_code=response.status_code,
                response_size=len(response.content),
                api_request_id=response.headers.get("X-Request-ID"),  # API's request ID
            )

            response.raise_for_status()
            response_data = response.json()

            logger.info(
                "mcp_api_request_complete",
                mcp_request_id=mcp_request_id,
                endpoint=endpoint,
                success=True,
                response_keys=list(response_data.keys()) if isinstance(response_data, dict) else None,
            )

            return response_data

    except httpx.HTTPStatusError as e:
        logger.error(
            "mcp_api_http_error",
            mcp_request_id=mcp_request_id,
            endpoint=endpoint,
            status_code=e.response.status_code,
            response_text=e.response.text[:500],  # Truncated error response
            api_request_id=e.response.headers.get("X-Request-ID"),
        )
        raise
    except httpx.TimeoutException:
        logger.error(
            "mcp_api_timeout",
            mcp_request_id=mcp_request_id,
            endpoint=endpoint,
        )
        raise
    except Exception as e:
        logger.error(
            "mcp_api_unexpected_error",
            mcp_request_id=mcp_request_id,
            endpoint=endpoint,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


def render_template(template_name: str, data: dict[str, Any]) -> str:
    """Render a Jinja2 template with the given data.

    Always injects current_time into the context if not already present.
    """
    # Add current time if not already in data
    if "current_time" not in data:
        data["current_time"] = time_service.now().isoformat()

    template = jinja_env.get_template(template_name)
    return template.render(**data)


@mcp.tool(name="store")
async def store(content: str, tags: list[str] = Field(default_factory=list)) -> str:  # noqa: B008
    """
    Store a new memory with optional tags.

    The memory will be processed to extract entities, actions, and generate
    auto-tags. Returns the stored memory ID and any related memories (splash).
    """
    if _is_verbose_logging():
        logger.info(
            "mcp_store_called",
            content_length=len(content),
            tag_count=len(tags),
            tags=tags,
            content_preview=content[:100],
        )

    try:
        data = await make_request("POST", "store", {"content": content, "tags": tags})

        # Log the successful response
        if _is_verbose_logging():
            logger.info(
                "mcp_store_success",
                memory_id=data.get("id"),
                splash_count=len(data.get("splash", [])),
            )

        result = render_template("store.md.j2", data)
        if _is_verbose_logging():
            logger.info(
                "mcp_store_template_rendered",
                template_length=len(result),
            )

        return result

    except Exception as e:
        logger.error(
            "mcp_store_failed",
            content_length=len(content),
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@mcp.tool(name="search")
async def search(query: str, limit: int = 10) -> str:
    """
    Search for memories using semantic similarity and text matching.

    The search uses a multiplex approach combining:
    - Full-text search
    - Entity/tag/action matching
    - Semantic similarity via embeddings
    """
    if _is_verbose_logging():
        logger.info(
            "mcp_search_called",
            query=query,
            limit=limit,
        )

    try:
        data = await make_request("POST", "search", {"query": query, "limit": limit})

        if _is_verbose_logging():
            logger.info(
                "mcp_search_success",
                result_count=data.get("count", 0),
                memory_ids=[m.get("id") for m in data.get("memories", [])],
            )

        return render_template("search.md.j2", data)

    except Exception as e:
        logger.error(
            "mcp_search_failed",
            query=query,
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@mcp.tool(name="recent")
async def recent(hours: float = 24.0, limit: int = 10) -> str:
    """
    Retrieve memories from the last N hours.

    Returns memories in reverse chronological order (newest first).
    """
    data = await make_request("POST", "recent", {"hours": hours, "limit": limit})
    return render_template("recent.md.j2", data)


@mcp.tool(name="init")
async def init() -> str:
    """
    Initialize context with current time and recent memories.

    This is typically called at the start of a conversation to establish
    temporal context and load relevant recent memories.
    """
    if _is_verbose_logging():
        logger.info("mcp_init_called")

    try:
        data = await make_request("POST", "init", {})

        if _is_verbose_logging():
            logger.info(
                "mcp_init_success",
                current_time=data.get("current_time"),
                recent_memory_count=len(data.get("recent_memories", [])),
            )

        return render_template("init.md.j2", data)

    except Exception as e:
        logger.error(
            "mcp_init_failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        raise


@mcp.tool(name="health")
async def health() -> str:
    """
    Check the health of the Pond system for the current tenant.

    Returns memory counts, embedding status, and date ranges.
    """
    # Get health status - tenant is determined by the API key
    health_data = await make_request("GET", "health", None)

    # Convert to YAML for clean, human-readable output
    return yaml.dump(health_data, default_flow_style=False, sort_keys=False)


if __name__ == "__main__":
    # Run the server with stdio transport (default)
    mcp.run()
