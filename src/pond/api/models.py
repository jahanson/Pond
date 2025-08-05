"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Request models

class StoreRequest(BaseModel):
    """Request to store a memory."""

    content: str = Field(..., min_length=1, max_length=7500)
    tags: list[str] = Field(default_factory=list)

    @field_validator("content")
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Ensure content is not just whitespace."""
        if not v.strip():
            raise ValueError("Content cannot be empty or whitespace-only")
        return v

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, v: list[str]) -> list[str]:
        """Clean and validate tags."""
        # Remove empty strings and duplicates
        return list({tag.strip() for tag in v if tag.strip()})


class SearchRequest(BaseModel):
    """Request to search memories.

    If query is empty or not provided, returns recent memories (same as /init).
    """

    query: str = Field(default="", max_length=500)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Clean the query string."""
        # Empty queries are allowed - they return recent memories
        return v.strip()


class RecentRequest(BaseModel):
    """Request for recent memories."""

    hours: float | None = Field(default=24, gt=0, le=720)  # Max 30 days
    limit: int = Field(default=10, ge=1, le=100)


class InitRequest(BaseModel):
    """Request for initialization (empty body expected)."""
    pass


# Response models

class EntityResponse(BaseModel):
    """Entity extracted from memory."""

    text: str
    type: str


class MemoryResponse(BaseModel):
    """Response containing a memory."""

    id: int
    content: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
    entities: list[EntityResponse] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_memory(cls, memory: Any) -> "MemoryResponse":
        """Convert a Memory domain object to response model."""
        # Extract entities from metadata
        entities = []
        if memory.metadata and "entities" in memory.metadata:
            entities = [
                EntityResponse(text=e["text"], type=e["type"])
                for e in memory.metadata["entities"]
            ]

        # Extract tags and actions from metadata
        tags = []
        actions = []
        if memory.metadata:
            tags = memory.metadata.get("tags", [])
            # Actions come as list of dicts with 'lemma' key
            actions_raw = memory.metadata.get("actions", [])
            if actions_raw and isinstance(actions_raw[0], dict):
                actions = [a.get("lemma", str(a)) for a in actions_raw]
            else:
                actions = actions_raw

        # Get created_at from metadata - it should already be a datetime from the database
        created_at = memory.metadata.get("created_at") if memory.metadata else None
        if not isinstance(created_at, datetime):
            # This shouldn't happen - database always has created_at
            from pond.utils.time_service import TimeService
            created_at = TimeService().now()

        return cls(
            id=memory.id,
            content=memory.content,
            created_at=created_at,
            tags=tags,
            entities=entities,
            actions=actions,
        )


class StoreResponse(BaseModel):
    """Response after storing a memory."""

    id: int
    splash: list[MemoryResponse] = Field(default_factory=list)


class SearchResponse(BaseModel):
    """Response for search results."""

    memories: list[MemoryResponse]
    count: int


class RecentResponse(BaseModel):
    """Response for recent memories."""

    memories: list[MemoryResponse]
    count: int


class InitResponse(BaseModel):
    """Response for initialization."""

    current_time: datetime
    recent_memories: list[MemoryResponse]


class TenantHealthResponse(BaseModel):
    """Response for tenant-specific health check."""

    status: str
    tenant: str
    memory_count: int
    embedding_count: int
    oldest_memory: datetime | None = None
    newest_memory: datetime | None = None
    embedding_provider: str
    embedding_healthy: bool


class SystemHealthResponse(BaseModel):
    """Response for system-wide health check."""

    status: str
    database: str
    embeddings: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    request_id: str | None = None
    details: dict[str, Any] | None = None
