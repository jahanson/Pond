"""Entry point for running Pond as a module: python -m pond"""

import os

import uvicorn

from pond.config import settings


def main():
    """Run the Pond REST API server."""
    import logging
    import sys

    # Log which port configuration is being used
    port_source = "default (19100)"
    if "PORT" in os.environ:
        port_source = "PORT environment variable"
    elif "POND_PORT" in os.environ:
        port_source = "POND_PORT environment variable"

    print(f"Starting Pond on port {settings.port} (from {port_source})")

    # Suppress the scary stack traces from startup failures
    if not settings.debug:
        # In production mode, suppress the stack trace noise
        logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)

    try:
        uvicorn.run(
            "pond.api.main:app",
            host=settings.host,
            port=settings.port,
            reload=settings.debug,
            log_level=settings.log_level.lower() if settings.debug else "critical",
        )
    except SystemExit:
        # Clean exit without additional messages
        sys.exit(1)


if __name__ == "__main__":
    main()
