"""Startup configuration checks and logging."""

import structlog

logger = structlog.get_logger()


def check_configuration():
    """Check configuration at startup and log any issues."""
    from pond.config import settings

    if settings.embedding_provider is None:
        logger.critical(
            "EMBEDDING_PROVIDER not configured",
            help="Set EMBEDDING_PROVIDER=ollama or EMBEDDING_PROVIDER=mock"
        )
        return False

    return True


def get_health_status() -> dict:
    """Get health status for the embedding service configuration."""
    from pond.config import settings

    if settings.embedding_provider is None:
        return {
            "healthy": False,
            "service": "embeddings",
            "error": "EMBEDDING_PROVIDER not configured",
            "help": "Set EMBEDDING_PROVIDER=ollama or EMBEDDING_PROVIDER=mock",
        }

    return {
        "healthy": True,
        "service": "embeddings",
        "provider": settings.embedding_provider,
        "configured": True,
    }
