"""Prometheus metrics definitions for Pond."""

from functools import wraps

from prometheus_client import Counter, Gauge, Histogram

# Business metrics
memories_stored = Counter(
    "pond_memories_stored_total",
    "Total memories stored",
    ["tenant"],
)

searches_performed = Counter(
    "pond_searches_performed_total",
    "Total searches performed",
    ["tenant", "type"],  # type: semantic, recent, text
)

memory_store_duration = Histogram(
    "pond_memory_store_duration_seconds",
    "Time to store a memory including all processing",
    ["tenant"],
)

embedding_duration = Histogram(
    "pond_embedding_duration_seconds",
    "Time to generate embeddings",
    ["provider"],  # ollama, mock, etc.
)

search_duration = Histogram(
    "pond_search_duration_seconds",
    "Time to execute search",
    ["tenant", "type"],
)

database_operation_duration = Histogram(
    "pond_database_operation_duration_seconds",
    "Database operation duration",
    ["operation", "tenant"],
)

# Current state gauges
current_memory_count = Gauge(
    "pond_memory_count",
    "Current number of memories",
    ["tenant"],
)

database_pool_connections = Gauge(
    "pond_database_pool_connections",
    "Database connection pool status",
    ["state"],  # active, idle, total
)

# Error tracking
operation_errors = Counter(
    "pond_operation_errors_total",
    "Total errors by operation",
    ["operation", "error_type", "tenant"],
)


def track_operation(metric: Histogram, operation: str):
    """Decorator for tracking async operations with metrics.

    Automatically times the operation and tracks errors.

    Args:
        metric: The Histogram metric to track timing
        operation: Name of the operation for labeling

    Example:
        @track_operation(database_operation_duration, "store")
        async def store_memory(self, tenant: str, ...):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(self, tenant: str, *args, **kwargs):
            # Handle both direct tenant parameter and extracting from args
            labels = {"tenant": tenant, "operation": operation}

            # Filter labels based on what the metric accepts
            if "operation" not in metric._labelnames:
                labels = {"tenant": tenant}

            with metric.labels(**labels).time():
                try:
                    result = await func(self, tenant, *args, **kwargs)
                    return result
                except Exception as e:
                    operation_errors.labels(
                        operation=operation,
                        error_type=type(e).__name__,
                        tenant=tenant,
                    ).inc()
                    raise

        return wrapper

    return decorator


def track_embedding_operation(provider: str):
    """Decorator specifically for embedding operations.

    Args:
        provider: Name of the embedding provider (ollama, mock, etc.)
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            with embedding_duration.labels(provider=provider).time():
                try:
                    result = await func(*args, **kwargs)
                    return result
                except Exception as e:
                    operation_errors.labels(
                        operation="embedding",
                        error_type=type(e).__name__,
                        tenant="system",  # Embeddings aren't tenant-specific
                    ).inc()
                    raise

        return wrapper

    return decorator
