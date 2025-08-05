"""Pydantic models for API requests and responses."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SearchRequest(BaseModel):
    """Request to search memories."""
    
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)


class RecentRequest(BaseModel):
    """Request for recent memories."""
    
    hours: int = Field(default=24, ge=1, le=168)  # Max 1 week
    limit: int = Field(default=10, ge=1, le=100)


class InitRequest(BaseModel):
    """Request for initialization (empty body expected)."""
    pass


class MemoryResponse(BaseModel):
    """Response containing a memory."""
    
    id: int
    content: str
    tags: list[str]
    entities: list[dict[str, Any]]
    actions: list[str]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class StoreResponse(BaseModel):
    """Response after storing a memory."""
    
    memory: MemoryResponse
    splash: list[MemoryResponse]


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


class HealthResponse(BaseModel):
    """Response for health check."""
    
    status: str
    database: str
    embeddings: str
    version: str = "0.1.0"


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    error: str
    request_id: str