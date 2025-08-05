"""API middleware for auth, request tracking, and error handling."""

import time
import uuid
from collections.abc import Callable
from typing import ClassVar

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from pond.infrastructure.auth import APIKeyManager

logger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add request ID."""
        request_id = str(uuid.uuid4())

        # Store in request state for other middleware/handlers
        request.state.request_id = request_id

        # Add to structlog context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            # Clear context after request
            structlog.contextvars.clear_contextvars()


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Log request details and response status."""
        start_time = time.time()

        # Skip logging for health checks (too noisy)
        if request.url.path == "/api/v1/health":
            return await call_next(request)

        # Log request
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )

        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Global error handler for consistent error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Catch exceptions and return consistent error format."""
        try:
            return await call_next(request)
        except Exception as exc:
            # Get request ID if available
            request_id = getattr(request.state, "request_id", "unknown")

            # Log the full exception internally
            logger.exception(
                "unhandled_exception",
                exc_type=type(exc).__name__,
                exc_message=str(exc),
            )

            # Return user-friendly error
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "error": "An internal error occurred",
                    "request_id": request_id,
                },
            )


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Check API key authentication and extract tenant."""

    # Paths that don't require authentication
    PUBLIC_PATHS: ClassVar[set[str]] = {
        "/api/v1/health",
        "/api/v1/docs",
        "/api/v1/openapi.json",
        "/api/v1/redoc",
        "/favicon.ico",  # Browser auto-requests this
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check API key and extract tenant from it."""
        # Skip auth for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)

        # Check if we're in development mode (no auth)
        # This is determined by checking if any API keys exist in the database
        # We'll handle this check in the lifespan/startup
        if hasattr(request.app.state, "auth_disabled") and request.app.state.auth_disabled:
            # Extract tenant from URL path for development
            # Path format: /api/v1/{tenant}/...
            path_parts = request.url.path.strip("/").split("/")
            if len(path_parts) >= 3 and path_parts[0] == "api" and path_parts[1] == "v1":
                request.state.tenant = path_parts[2]
            else:
                request.state.tenant = None
            return await call_next(request)

        # Check API key header
        provided_key = request.headers.get("X-API-Key")

        if not provided_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Unauthorized"},
            )

        # Validate key and get tenant
        api_key_manager: APIKeyManager = request.app.state.api_key_manager
        tenant = await api_key_manager.validate_key(provided_key)

        if not tenant:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "Unauthorized"},
            )

        # Store tenant in request state for use by endpoints
        request.state.tenant = tenant

        # Also validate that the tenant in the URL matches the key's tenant
        # Path format: /api/v1/{tenant}/...
        path_parts = request.url.path.strip("/").split("/")
        if len(path_parts) >= 3 and path_parts[0] == "api" and path_parts[1] == "v1":
            url_tenant = path_parts[2]
            if url_tenant != tenant:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"error": "API key not authorized for this tenant"},
                )

        return await call_next(request)
