"""
Configuration for Pond MCP Server using Pydantic Settings.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class MCPSettings(BaseSettings):
    """Settings for the Pond MCP server."""

    model_config = {
        # NO env_file - all config comes from MCP client via environment
        "case_sensitive": False
    }

    # Settings with sensible defaults
    pond_url: str = Field(
        default="http://localhost:19100", description="URL of the Pond API server"
    )
    pond_api_key: str = Field(
        ..., description="API key for authenticating with Pond (determines tenant)"
    )


@lru_cache
def get_settings() -> MCPSettings:
    """Get settings singleton - lazy loaded when first accessed."""
    return MCPSettings()
