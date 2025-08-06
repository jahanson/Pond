"""Health check endpoints."""

import structlog
from fastapi import APIRouter, Depends, Request

from pond.api.dependencies import get_db_pool
from pond.api.models import SystemHealthResponse, TenantHealthResponse
from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import get_tenant_stats
from pond.startup_check import get_health_status

logger = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(
    request: Request,
    db_pool: DatabasePool = Depends(get_db_pool),  # noqa: B008
) -> SystemHealthResponse | TenantHealthResponse:
    """Health check - returns different data based on authentication.

    - No API key: Returns basic system health
    - Valid API key: Returns system health + tenant-specific stats
    - Invalid API key: Already rejected by middleware (401)
    """
    # Check database
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    # Check embeddings
    embedding_health = get_health_status()
    embedding_status = "healthy" if embedding_health["healthy"] else "degraded"

    # Check if we have an authenticated tenant
    tenant = getattr(request.state, "tenant", None)

    if tenant:
        # Authenticated - return tenant-specific health
        try:
            # Get tenant statistics
            async with db_pool.acquire() as conn:
                stats = await get_tenant_stats(conn, tenant)

            # Parse dates if they exist
            oldest = None
            newest = None
            if stats["oldest_memory"]:
                from datetime import datetime

                oldest = datetime.fromisoformat(stats["oldest_memory"])
            if stats["newest_memory"]:
                from datetime import datetime

                newest = datetime.fromisoformat(stats["newest_memory"])

            logger.info(
                "tenant_health_check",
                tenant=tenant,
                memory_count=stats["memory_count"],
                embedding_count=stats["embedding_count"],
            )

            return TenantHealthResponse(
                status="healthy" if db_status == "healthy" else "degraded",
                tenant=tenant,
                memory_count=stats["memory_count"],
                embedding_count=stats["embedding_count"],
                oldest_memory=oldest,
                newest_memory=newest,
                embedding_provider=embedding_health["provider"],
                embedding_healthy=embedding_health["healthy"],
            )

        except Exception as e:
            logger.exception(
                "tenant_health_error",
                tenant=tenant,
                error=str(e),
            )
            # Return degraded status with partial info
            return TenantHealthResponse(
                status="degraded",
                tenant=tenant,
                memory_count=0,
                embedding_count=0,
                oldest_memory=None,
                newest_memory=None,
                embedding_provider=embedding_health["provider"],
                embedding_healthy=False,
            )
    else:
        # Not authenticated - return basic system health only
        return SystemHealthResponse(
            status="healthy" if db_status == "healthy" else "degraded",
            database=db_status,
            embeddings=embedding_status,
        )
