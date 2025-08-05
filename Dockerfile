# Containerize JUST the REST server
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files and README (required by pyproject.toml)
COPY pyproject.toml uv.lock README.md ./

# Install dependencies using uv to system Python (FAST!)
RUN uv pip install --system --no-cache . && \
    python -m spacy download en_core_web_lg

# Copy application code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application
CMD ["uvicorn", "pond.api.main:app", "--host", "0.0.0.0", "--port", "8000"]