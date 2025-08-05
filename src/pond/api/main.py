"""Main FastAPI application."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from pond.infrastructure.auth import APIKeyManager
from pond.infrastructure.database import DatabasePool
from pond.infrastructure.schema import list_tenants
from pond.startup_check import check_configuration

from .middleware import (
    AuthenticationMiddleware,
    ErrorHandlingMiddleware,
    LoggingMiddleware,
    RequestIDMiddleware,
)

# Configure structlog for our app only
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Run configuration check
    check_configuration()

    # Initialize database pool
    logger.info("initializing_database_pool")
    app.state.db_pool = DatabasePool()
    await app.state.db_pool.initialize()
    logger.info("database_pool_ready")

    # Initialize API key manager
    app.state.api_key_manager = APIKeyManager(app.state.db_pool)

    # Check if we should disable auth (development mode)
    # We'll disable auth if no API keys exist in any tenant
    auth_disabled = True
    async with app.state.db_pool.acquire() as conn:
        tenants = await list_tenants(conn)
        for tenant in tenants:
            keys = await app.state.api_key_manager.list_keys(tenant)
            if keys:
                auth_disabled = False
                break

    app.state.auth_disabled = auth_disabled
    if auth_disabled:
        logger.warning("No API keys found - authentication disabled for development")
    else:
        logger.info(f"API key authentication enabled ({len(tenants)} tenants configured)")

    yield

    # Cleanup
    logger.info("closing_database_pool")
    await app.state.db_pool.close()


app = FastAPI(
    title="Pond",
    description="Semantic memory system for AI assistants",
    version="0.1.0",
    lifespan=lifespan,
)

# Add middleware in reverse order (last added = first executed)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# Include routes
from .routes import health, memories

app.include_router(health.router)
app.include_router(memories.router)
