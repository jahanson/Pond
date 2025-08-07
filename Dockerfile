# Stage 1: Build the frontend
FROM node:20-slim AS frontend-builder
WORKDIR /app/web
COPY web/package*.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# Stage 2: Build the Python server
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
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

# Copy the built visualizer from the frontend stage
COPY --from=frontend-builder /app/web/dist ./web/dist

# Set Python path
ENV PYTHONPATH="/app/src:$PYTHONPATH"

# Expose port
EXPOSE 8000

# Health check - disabled for development (we want to see crashes immediately)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
#     CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Run the application as a module
CMD ["python", "-m", "pond"]