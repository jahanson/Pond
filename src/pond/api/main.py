"""Main FastAPI application."""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from pond.startup_check import check_configuration

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Just run the check - it logs its own critical errors
    check_configuration()
    
    yield


app = FastAPI(
    title="Pond",
    description="Semantic memory system for AI assistants",
    version="0.1.0",
    lifespan=lifespan,
)
