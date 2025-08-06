"""
Entry point for running Pond MCP server as a module.

Usage:
    python -m pond.mcp
    uv run python -m pond.mcp
"""

from pond.mcp.server import mcp

if __name__ == "__main__":
    mcp.run()
