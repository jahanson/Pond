"""Entry point for running Pond as a module: python -m pond"""

import uvicorn

from pond.config import settings


def main():
    """Run the Pond REST API server."""
    uvicorn.run(
        "pond.api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
