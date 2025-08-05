"""Memory management API endpoints."""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status

from pond.api.dependencies import get_repository, get_tenant
from pond.api.models import (
    MemoryResponse,
    StoreRequest,
    StoreResponse,
)
from pond.domain.repository import MemoryRepository

logger = structlog.get_logger()

router = APIRouter(
    prefix="/api/v1/{tenant}",
    tags=["memories"],
)


@router.post("/store", response_model=StoreResponse)
async def store_memory(
    request: Request,
    store_request: StoreRequest,
    tenant: str = Depends(get_tenant),
    repository: MemoryRepository = Depends(get_repository),
) -> StoreResponse:
    """Store a new memory and return related memories (splash).
    
    The splash contains semantically similar memories (0.7-0.9 similarity)
    to help maintain context.
    """
    try:
        # Store the memory
        logger.info(
            "storing_memory",
            tenant=tenant,
            content_length=len(store_request.content),
            tag_count=len(store_request.tags),
        )
        
        memory, splash_memories = await repository.store(
            content=store_request.content,
            user_tags=store_request.tags,
        )
        
        logger.info(
            "memory_stored",
            tenant=tenant,
            memory_id=memory.id,
            splash_count=len(splash_memories),
        )
        
        # Convert to response models
        memory_response = MemoryResponse.from_memory(memory)
        splash_response = [MemoryResponse.from_memory(m) for m in splash_memories]
        
        return StoreResponse(
            id=memory.id,
            splash=splash_response,
        )
        
    except ValueError as e:
        # Validation errors from the repository
        logger.warning(
            "store_validation_error",
            tenant=tenant,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Unexpected errors
        logger.exception(
            "store_error",
            tenant=tenant,
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store memory",
        )