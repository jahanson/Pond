"""Dependency injection for API endpoints."""

from typing import Annotated

from fastapi import Path, Request

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


async def get_tenant(
    tenant: Annotated[str, Path(description="Tenant name")],
    request: Request,
) -> str:
    """Get and validate tenant from path and auth.

    The AuthenticationMiddleware has already validated that:
    1. The API key is valid for this tenant
    2. The tenant in the URL matches the key's tenant

    This dependency just extracts the validated tenant.
    """
    # The middleware stores the authenticated tenant in request.state
    auth_tenant = getattr(request.state, "tenant", None)

    # In development mode with auth disabled, use the URL tenant
    if auth_tenant is None:
        return tenant

    # In production, ensure URL tenant matches authenticated tenant
    if auth_tenant != tenant:
        # This shouldn't happen - middleware should have caught it
        raise ValueError(f"Tenant mismatch: {tenant} != {auth_tenant}")

    return tenant
