"""Dependency injection for API endpoints."""

from typing import Annotated

from fastapi import Depends, Path, Request

from pond.domain import MemoryRepository
from pond.infrastructure.database import DatabasePool
from pond.services.embeddings import get_embedding_provider


async def get_db_pool(request: Request) -> DatabasePool:
    """Get database pool from app state."""
    return request.app.state.db_pool


async def get_repository(
    tenant: Annotated[str, Path(description="Tenant name")],
    request: Request,
    db_pool: Annotated[DatabasePool, Depends(get_db_pool)],
) -> MemoryRepository:
    """Get repository for a specific tenant.
    
    Creates a MemoryRepository with the tenant's schema and
    appropriate embedding provider.
    """
    # Try to get embedding provider, but allow None for degraded mode
    try:
        embedding_provider = get_embedding_provider()
    except Exception:
        # Running in degraded mode without embeddings
        embedding_provider = None
    
    return MemoryRepository(db_pool, tenant, embedding_provider)


async def get_request_id(request: Request) -> str:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")