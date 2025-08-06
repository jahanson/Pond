"""Main FastAPI application."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from pond.domain import MemoryRepository
from pond.infrastructure.auth import APIKeyManager
from pond.infrastructure.database import DatabasePool
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

    # Initialize singleton MemoryRepository
    logger.info("initializing_memory_repository")
    app.state.memory_repository = MemoryRepository(app.state.db_pool)
    logger.info(
        "memory_repository_ready",
        spacy_model_loaded=bool(app.state.memory_repository._nlp),
    )

    # API key authentication is always required
    logger.info("API key authentication required for all endpoints")

    yield

    # Cleanup
    logger.info("closing_database_pool")
    await app.state.db_pool.close()


# Create v1 API app
api_v1 = FastAPI(
    title="Pond API v1",
    description="Semantic memory system for AI assistants",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

# Include v1 routes
from .routes import health, memories  # noqa: E402

api_v1.include_router(health.router)
api_v1.include_router(memories.router)

# Create main app and mount v1
app = FastAPI(
    title="Pond",
    description="Semantic memory system for AI assistants",
    lifespan=lifespan,
    docs_url=None,  # Disable docs at root
    openapi_url=None,  # Disable openapi at root
    redoc_url=None,  # Disable redoc at root
)

# Mount v1 API
# Share the main app's state with the sub-app
api_v1.state = app.state
app.mount("/api/v1", api_v1)

# Add middleware to main app
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(ErrorHandlingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
