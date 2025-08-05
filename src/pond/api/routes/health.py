"""Health check endpoints."""

import structlog
from fastapi import APIRouter, Depends

from pond.api.dependencies import get_db_pool, get_repository, get_tenant
from pond.api.models import SystemHealthResponse, TenantHealthResponse
from pond.domain.repository import MemoryRepository
from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import get_tenant_stats
from pond.startup_check import get_health_status

logger = structlog.get_logger()
router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=SystemHealthResponse)
async def health_check(db_pool: DatabasePool = Depends(get_db_pool)) -> SystemHealthResponse:  # noqa: B008
    """System health check - no authentication required."""
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

    return SystemHealthResponse(
        status="healthy" if db_status == "healthy" else "degraded",
        database=db_status,
        embeddings=embedding_status,
    )


@router.get("/api/v1/{tenant}/health", response_model=TenantHealthResponse)
async def tenant_health_check(
    tenant: str = Depends(get_tenant),
    repository: MemoryRepository = Depends(get_repository),  # noqa: B008
    db_pool: DatabasePool = Depends(get_db_pool),  # noqa: B008
) -> TenantHealthResponse:
    """Tenant-specific health check with statistics."""
    try:
        # Get tenant statistics
        async with db_pool.acquire() as conn:
            stats = await get_tenant_stats(conn, tenant)

        # Check embedding health
        embedding_health = get_health_status()

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
            status="healthy",
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
        embedding_health = get_health_status()
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
