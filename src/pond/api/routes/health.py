"""Health check endpoints."""

from fastapi import APIRouter, Depends

from pond.api.dependencies import get_db_pool
from pond.api.models import SystemHealthResponse
from pond.infrastructure.database import DatabasePool
from pond.startup_check import get_health_status

router = APIRouter(tags=["health"])


@router.get("/api/v1/health", response_model=SystemHealthResponse)
async def health_check(db_pool: DatabasePool = Depends(get_db_pool)) -> SystemHealthResponse:
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
