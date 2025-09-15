"""Memory repository for database operations."""

from __future__ import annotations

import asyncio
import json

import numpy as np
import structlog
from pendulum import DateTime

from pond.config import get_settings
from pond.infrastructure.database import DatabasePool
from pond.metrics import current_memory_count, database_operation_duration
from pond.services.embeddings import (
    EmbeddingNotConfigured,
    EmbeddingProvider,
    get_embedding_provider,
)

from .entities import Action, Entity
from .memory import Memory

logger = structlog.get_logger()


def _is_verbose_logging() -> bool:
    """Check if verbose logging is enabled via log level."""
    settings = get_settings()
    return settings.log_level.upper() == "DEBUG"


class MemoryRepository:
    """Repository for storing and retrieving memories."""

    def __init__(
        self,
        db_pool: DatabasePool,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize with database pool."""
        self.db_pool = db_pool
        self._nlp = None
        self._embedding_provider = embedding_provider
        self._provider_error = None

        # Try to get provider if not explicitly provided
        if self._embedding_provider is None:
            try:
                self._embedding_provider = get_embedding_provider()
            except EmbeddingNotConfigured as e:
                # Store the error to raise later when embeddings are actually needed
                self._provider_error = e
                logger.critical(f"Embedding provider not configured: {e}")

    @property
    def nlp(self):
        """Lazy load spaCy model for entity/action extraction."""
        if self._nlp is None:
            import spacy

            self._nlp = spacy.load("en_core_web_lg")
        return self._nlp

    @property
    def embedding_provider(self) -> EmbeddingProvider:
        """Get the embedding provider, raising error if not configured."""
        if self._provider_error:
            raise self._provider_error
        return self._embedding_provider

    async def store(
        self, tenant: str, content: str, user_tags: list[str]
    ) -> tuple[Memory, list[Memory]]:
        """Store a memory and return it with splash memories.

        Returns:
            (stored_memory, splash_memories)
        """
        if _is_verbose_logging():
            logger.info(
                "store_memory_start",
                tenant=tenant,
                content_length=len(content),
                user_tag_count=len(user_tags),
                user_tags=user_tags,
            )

        # Create memory object
        try:
            memory = Memory(content=content)
            if _is_verbose_logging():
                logger.info(
                    "memory_object_created",
                    tenant=tenant,
                    memory_id=id(memory),  # Object ID for tracking
                )
        except Exception as e:
            logger.error(
                "memory_creation_failed",
                tenant=tenant,
                error=str(e),
                content_preview=content[:100] if content else "<empty>",
            )
            raise

        # Add user tags
        try:
            memory.add_tags(*user_tags)
            if _is_verbose_logging():
                final_user_tags = memory.get_tags()
                logger.info(
                    "user_tags_added",
                    tenant=tenant,
                    memory_id=id(memory),
                    original_tags=user_tags,
                    normalized_tags=final_user_tags,
                )
        except Exception as e:
            logger.error(
                "user_tags_failed",
                tenant=tenant,
                memory_id=id(memory),
                error=str(e),
                user_tags=user_tags,
            )
            raise

        # Extract features from content
        try:
            if _is_verbose_logging():
                logger.info(
                    "feature_extraction_start",
                    tenant=tenant,
                    memory_id=id(memory),
                )
            await self._extract_features(memory)
            if _is_verbose_logging():
                entities = memory.get_entities()
                actions = memory.get_actions()
                all_tags = memory.get_tags()
                logger.info(
                    "feature_extraction_complete",
                    tenant=tenant,
                    memory_id=id(memory),
                    entity_count=len(entities),
                    action_count=len(actions),
                    total_tag_count=len(all_tags),
                    entities=[e.text for e in entities],
                    actions=[a.lemma for a in actions],
                    final_tags=all_tags,
                )
        except Exception as e:
            logger.error(
                "feature_extraction_failed",
                tenant=tenant,
                memory_id=id(memory),
                error=str(e),
                content_preview=content[:200],
            )
            raise

        # Get embedding
        try:
            if _is_verbose_logging():
                logger.info(
                    "embedding_generation_start",
                    tenant=tenant,
                    memory_id=id(memory),
                )
            memory.embedding = await self._get_embedding(content)
            if _is_verbose_logging():
                logger.info(
                    "embedding_generation_complete",
                    tenant=tenant,
                    memory_id=id(memory),
                    embedding_shape=memory.embedding.shape if memory.embedding is not None else None,
                )
        except Exception as e:
            logger.error(
                "embedding_generation_failed",
                tenant=tenant,
                memory_id=id(memory),
                error=str(e),
                content_preview=content[:200],
            )
            raise

        # Store in database with metrics tracking
        try:
            if _is_verbose_logging():
                logger.info(
                    "database_store_start",
                    tenant=tenant,
                    memory_id=id(memory),
                )
            with database_operation_duration.labels(
                operation="store", tenant=tenant
            ).time():
                memory.id = await self._store_in_db(tenant, memory)
            if _is_verbose_logging():
                logger.info(
                    "database_store_complete",
                    tenant=tenant,
                    memory_object_id=id(memory),
                    database_memory_id=memory.id,
                )
        except Exception as e:
            logger.error(
                "database_store_failed",
                tenant=tenant,
                memory_id=id(memory),
                error=str(e),
            )
            raise

        # Get splash
        try:
            if _is_verbose_logging():
                logger.info(
                    "splash_generation_start",
                    tenant=tenant,
                    memory_id=memory.id,
                )
            splash = await self._get_splash(tenant, memory)
            if _is_verbose_logging():
                logger.info(
                    "splash_generation_complete",
                    tenant=tenant,
                    memory_id=memory.id,
                    splash_count=len(splash),
                    splash_ids=[s.id for s in splash],
                )
        except Exception as e:
            logger.error(
                "splash_generation_failed",
                tenant=tenant,
                memory_id=memory.id,
                error=str(e),
            )
            # Don't fail the entire operation for splash failures
            splash = []
            if _is_verbose_logging():
                logger.warning(
                    "splash_defaulted_to_empty",
                    tenant=tenant,
                    memory_id=memory.id,
                )

        # Update memory count gauge
        try:
            await self._update_memory_count(tenant)
            if _is_verbose_logging():
                logger.info(
                    "memory_count_updated",
                    tenant=tenant,
                    memory_id=memory.id,
                )
        except Exception as e:
            logger.warning(
                "memory_count_update_failed",
                tenant=tenant,
                memory_id=memory.id,
                error=str(e),
            )
            # Don't fail the operation for metrics failures

        if _is_verbose_logging():
            logger.info(
                "store_memory_complete",
                tenant=tenant,
                memory_id=memory.id,
                splash_count=len(splash),
                total_processing_success=True,
            )

        return memory, splash

    async def _extract_features(self, memory: Memory) -> None:
        """Extract entities, actions, and auto-tags from memory content."""
        # Run synchronous spaCy processing in thread pool
        await asyncio.to_thread(self._extract_features_sync, memory)

    def _extract_features_sync(self, memory: Memory) -> None:
        """Synchronous feature extraction - runs in thread pool only."""
        doc = self.nlp(memory.content)

        # Extract entities
        for ent in doc.ents:
            memory.add_entity(Entity(text=ent.text, type=ent.label_))

        # Extract actions (lemmatized verbs from all tenses)
        for token in doc:
            if token.pos_ in ["VERB", "AUX"]:
                # Include all verbs and auxiliaries
                # The Action class has is_past_tense_marker() to identify helpers
                memory.add_action(Action(lemma=token.lemma_))

        # Generate auto-tags (3-5 conservative, from entities/noun chunks/nouns)
        auto_tags = []

        # Get existing user tags to avoid duplicates
        existing_tags = set(memory.get_tags())

        # 1. Add entity-based tags (most reliable)
        entities = memory.get_entities()
        for ent in entities[:3]:  # Limit to 3 entity tags
            # Only add if it won't be a duplicate after normalization
            if ent.text and ent.text not in existing_tags:
                auto_tags.append(ent.text)

        # 2. Add noun chunk tags if we need more
        if len(auto_tags) < 5:
            for chunk in doc.noun_chunks:
                if len(auto_tags) >= 5:
                    break

                # Be conservative - skip pronouns, single stopwords, very short chunks
                if (
                    chunk.root.pos_ == "PRON"
                    or (len(chunk) == 1 and chunk.root.is_stop)
                    or len(chunk.text) < 3
                ):
                    continue

                # Skip if already in auto_tags or would duplicate user tag
                if chunk.text not in auto_tags and chunk.text not in existing_tags:
                    auto_tags.append(chunk.text)

        # 3. If still need more, look at significant individual nouns
        if len(auto_tags) < 3:  # Ensure at least 3 tags if possible
            for token in doc:
                if len(auto_tags) >= 5:
                    break

                # Only proper nouns or nouns that aren't stop words
                if (
                    token.pos_ in ["PROPN", "NOUN"]
                    and not token.is_stop
                    and len(token.text) > 2
                    and token.text not in auto_tags
                    and token.text not in existing_tags
                ):
                    auto_tags.append(token.text)

        # Add the auto-tags to the memory
        if auto_tags:
            memory.add_tags(*auto_tags)

    async def _get_embedding(self, content: str) -> np.ndarray:
        """Get embedding from configured provider."""
        if _is_verbose_logging():
            logger.info(
                "embedding_provider_call_start",
                content_length=len(content),
                content_preview=content[:100],
                provider_type=type(self.embedding_provider).__name__,
            )

        try:
            embedding = await self.embedding_provider.embed(content)

            if _is_verbose_logging():
                logger.info(
                    "embedding_provider_call_complete",
                    content_length=len(content),
                    embedding_shape=embedding.shape if embedding is not None else None,
                    embedding_dtype=str(embedding.dtype) if embedding is not None else None,
                )

            return embedding

        except Exception as e:
            logger.error(
                "embedding_provider_call_failed",
                content_length=len(content),
                content_preview=content[:200],
                provider_type=type(self.embedding_provider).__name__,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise

    async def _store_in_db(self, tenant: str, memory: Memory) -> int:
        """Store memory in database, return ID."""
        if _is_verbose_logging():
            logger.info(
                "db_connection_acquire_start",
                tenant=tenant,
                memory_object_id=id(memory),
            )

        async with self.db_pool.acquire_tenant(tenant) as conn:
            if _is_verbose_logging():
                logger.info(
                    "db_connection_acquired",
                    tenant=tenant,
                    memory_object_id=id(memory),
                    connection_info=str(conn)[:100],  # Truncated connection info
                )

            try:
                # Convert numpy array to list for storage
                embedding_list = (
                    memory.embedding.tolist() if memory.embedding is not None else None
                )
                if _is_verbose_logging():
                    logger.info(
                        "embedding_conversion_complete",
                        tenant=tenant,
                        memory_object_id=id(memory),
                        embedding_length=len(embedding_list) if embedding_list else 0,
                        has_embedding=embedding_list is not None,
                    )

                # Prepare metadata for JSON serialization
                # Convert sets to lists since sets aren't JSON serializable
                metadata_for_storage = memory.metadata.copy()
                if "tags" in metadata_for_storage and isinstance(
                    metadata_for_storage["tags"], set
                ):
                    metadata_for_storage["tags"] = sorted(metadata_for_storage["tags"])

                if _is_verbose_logging():
                    logger.info(
                        "metadata_preparation_complete",
                        tenant=tenant,
                        memory_object_id=id(memory),
                        metadata_keys=list(metadata_for_storage.keys()),
                        tag_count=len(metadata_for_storage.get("tags", [])),
                        entity_count=len(metadata_for_storage.get("entities", [])),
                        action_count=len(metadata_for_storage.get("actions", [])),
                    )

                # Store and get the generated ID
                if _is_verbose_logging():
                    logger.info(
                        "db_insert_start",
                        tenant=tenant,
                        memory_object_id=id(memory),
                        content_length=len(memory.content),
                    )

                row = await conn.fetchrow(
                    """
                    INSERT INTO memories (content, embedding, metadata)
                    VALUES ($1, $2, $3::jsonb)
                    RETURNING id
                    """,
                    memory.content,
                    embedding_list,
                    json.dumps(metadata_for_storage),  # Convert dict to JSON string
                )

                if row is None:
                    logger.error(
                        "db_insert_returned_null",
                        tenant=tenant,
                        memory_object_id=id(memory),
                    )
                    raise RuntimeError("Database insert returned no row")

                memory_id = row["id"]
                if _is_verbose_logging():
                    logger.info(
                        "db_insert_complete",
                        tenant=tenant,
                        memory_object_id=id(memory),
                        database_memory_id=memory_id,
                    )

                return memory_id

            except Exception as e:
                logger.error(
                    "db_insert_failed",
                    tenant=tenant,
                    memory_object_id=id(memory),
                    error=str(e),
                    error_type=type(e).__name__,
                    content_preview=memory.content[:100],
                )
                raise

    async def _get_splash(self, tenant: str, memory: Memory) -> list[Memory]:
        """Get memories in the similarity sweet spot (0.7-0.9).

        Returns up to 3 memories with similarity between 0.7 and 0.9.
        Empty list is valid if no memories fall in this range.
        """
        if memory.embedding is None:
            if _is_verbose_logging():
                logger.warning(
                    "splash_skipped_no_embedding",
                    tenant=tenant,
                    memory_id=memory.id,
                )
            return []

        if _is_verbose_logging():
            logger.info(
                "splash_query_start",
                tenant=tenant,
                memory_id=memory.id,
                embedding_length=len(memory.embedding),
            )

        async with self.db_pool.acquire_tenant(tenant) as conn:
            try:
                # pgvector uses <=> for cosine distance (0 = identical, 2 = opposite)
                # similarity = 1 - distance, so:
                # distance < 0.3 means similarity > 0.7
                # distance > 0.1 means similarity < 0.9
                rows = await conn.fetch(
                    """
                    SELECT id, content, embedding, metadata,
                           1 - (embedding <=> $1) as similarity
                    FROM memories
                    WHERE NOT forgotten
                    AND embedding IS NOT NULL
                    AND embedding <=> $1 < 0.3  -- similarity > 0.7
                    AND embedding <=> $1 > 0.1  -- similarity < 0.9
                    ORDER BY embedding <=> $1
                    LIMIT 3
                    """,
                    memory.embedding.tolist(),
                )

                if _is_verbose_logging():
                    logger.info(
                        "splash_query_complete",
                        tenant=tenant,
                        memory_id=memory.id,
                        candidate_count=len(rows),
                        similarities=[float(row["similarity"]) for row in rows] if rows else [],
                    )

                splash_memories = [self._row_to_memory(row) for row in rows]

                if _is_verbose_logging():
                    logger.info(
                        "splash_conversion_complete",
                        tenant=tenant,
                        memory_id=memory.id,
                        splash_memory_ids=[m.id for m in splash_memories],
                    )

                return splash_memories

            except Exception as e:
                logger.error(
                    "splash_query_failed",
                    tenant=tenant,
                    memory_id=memory.id,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

    async def _update_memory_count(self, tenant: str) -> None:
        """Update the memory count gauge for a tenant."""
        async with self.db_pool.acquire_tenant(tenant) as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM memories WHERE NOT forgotten"
            )
            current_memory_count.labels(tenant=tenant).set(count or 0)

    async def search(self, tenant: str, query: str, limit: int = 10) -> list[Memory]:
        """Unified search across text, features, and semantic similarity.

        Combines three search methods with weighted scoring:
        - Full-text search on content
        - Feature matching on tags, entities, actions
        - Semantic similarity via embeddings
        """
        # Handle empty query
        if not query or not query.strip():
            return []

        # Scoring weights - tunable in source for easy experimentation
        TEXT_WEIGHT = 0.4  # Exact/partial text matches  # noqa: N806
        FEATURE_WEIGHT = 0.2  # Tags/entities/actions  # noqa: N806
        SEMANTIC_WEIGHT = 0.4  # Semantic similarity  # noqa: N806

        # Get embedding for semantic search
        query_embedding = await self._get_embedding(query)

        # Normalize query for feature matching (lowercase, lemmatized)
        query_lower = query.lower()

        # Track search operation timing
        with database_operation_duration.labels(
            operation="search", tenant=tenant
        ).time():
            async with self.db_pool.acquire_tenant(tenant) as conn:
                rows = await conn.fetch(
                    """
                WITH text_search AS (
                    -- Full-text search using tsvector
                    SELECT id,
                           ts_rank(content_tsv, plainto_tsquery('english', $1)) as score
                    FROM memories
                    WHERE NOT forgotten
                    AND content_tsv @@ plainto_tsquery('english', $1)
                ),
                feature_search AS (
                    -- Feature matching on tags, entities, actions
                    SELECT id, 1.0 as score
                    FROM memories
                    WHERE NOT forgotten
                    AND (
                        -- Check if query matches any tag
                        EXISTS (
                            SELECT 1 FROM jsonb_array_elements_text(metadata->'tags') AS tag
                            WHERE lower(tag) = $2
                        )
                        -- Check if query matches any entity text
                        OR EXISTS (
                            SELECT 1 FROM jsonb_array_elements(metadata->'entities') AS entity
                            WHERE lower(entity->>'text') = $2
                        )
                        -- Check if query matches any action
                        OR EXISTS (
                            SELECT 1 FROM jsonb_array_elements_text(metadata->'actions') AS action
                            WHERE lower(action) = $2
                        )
                    )
                ),
                semantic_search AS (
                    -- Semantic similarity using embeddings
                    SELECT id,
                           1 - (embedding <=> $3::vector) as score
                    FROM memories
                    WHERE NOT forgotten
                    AND embedding IS NOT NULL
                    AND embedding <=> $3::vector < 0.5  -- similarity > 0.5
                ),
                combined_scores AS (
                    -- Combine all searches with weighted scoring
                    SELECT
                        COALESCE(t.id, f.id, s.id) as id,
                        (COALESCE(t.score, 0) * $4) +
                        (COALESCE(f.score, 0) * $5) +
                        (COALESCE(s.score, 0) * $6) as final_score
                    FROM text_search t
                    FULL OUTER JOIN feature_search f ON t.id = f.id
                    FULL OUTER JOIN semantic_search s ON COALESCE(t.id, f.id) = s.id
                )
                SELECT m.id, m.content, m.embedding, m.metadata, c.final_score
                FROM combined_scores c
                JOIN memories m ON c.id = m.id
                WHERE c.final_score > 0
                ORDER BY c.final_score DESC
                LIMIT $7
                """,
                    query,  # $1 - for text search
                    query_lower,  # $2 - for feature matching
                    query_embedding.tolist(),  # $3 - for semantic search
                    TEXT_WEIGHT,  # $4
                    FEATURE_WEIGHT,  # $5
                    SEMANTIC_WEIGHT,  # $6
                    limit,  # $7
                )

            return [self._row_to_memory(row) for row in rows]

    async def get_recent(
        self, tenant: str, since: DateTime, limit: int = 10
    ) -> list[Memory]:
        """Get recent memories since a given time."""
        with database_operation_duration.labels(
            operation="get_recent", tenant=tenant
        ).time():
            async with self.db_pool.acquire_tenant(tenant) as conn:
                rows = await conn.fetch(
                    """
                    SELECT id, content, embedding, metadata
                    FROM memories
                    WHERE NOT forgotten
                    AND (metadata->>'created_at')::timestamptz >= $1
                    ORDER BY (metadata->>'created_at')::timestamptz DESC
                    LIMIT $2
                    """,
                    since,  # asyncpg handles datetime serialization
                    limit,
                )

                return [self._row_to_memory(row) for row in rows]

    def _row_to_memory(self, row: dict) -> Memory:
        """Convert a database row to a Memory object."""
        # Convert embedding back to numpy array if present
        embedding = None
        if row["embedding"] is not None:
            embedding = np.array(row["embedding"])

        # Convert metadata, restoring sets from lists
        metadata = row["metadata"]
        # Handle case where metadata might be a string (from manual inserts)
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        else:
            # asyncpg automatically decodes JSONB to dict, so copy it
            metadata = metadata.copy()

        if "tags" in metadata and isinstance(metadata["tags"], list):
            metadata["tags"] = set(metadata["tags"])

        # Create memory with data from database
        memory = Memory(
            id=row["id"], content=row["content"], embedding=embedding, metadata=metadata
        )

        return memory
