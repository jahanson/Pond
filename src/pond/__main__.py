"""Entry point for running Pond as a module: python -m pond"""

import os

import uvicorn

from pond.config import settings


def main():
    """Run the Pond REST API server."""
    # Log which port configuration is being used
    port_source = "default (19100)"
    if "PORT" in os.environ:
        port_source = "PORT environment variable"
    elif "POND_PORT" in os.environ:
        port_source = "POND_PORT environment variable"

    print(f"Starting Pond on port {settings.port} (from {port_source})")

    uvicorn.run(
        "pond.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
