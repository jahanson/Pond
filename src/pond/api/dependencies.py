"""Dependency injection for API endpoints."""

from fastapi import Request

from pond.domain import MemoryRepository
from pond.infrastructure.database import DatabasePool


async def get_db_pool(request: Request) -> DatabasePool:
    """Get database pool from app state."""
    return request.app.state.db_pool


async def get_repository(
    request: Request,
) -> MemoryRepository:
    """Get the singleton repository from app state."""
    return request.app.state.memory_repository


async def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")
