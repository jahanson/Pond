"""Memory repository for database operations."""

from __future__ import annotations

import json
import logging

import numpy as np
from pendulum import DateTime

from pond.infrastructure.database import DatabasePool
from pond.services.embeddings import (
    EmbeddingNotConfigured,
    EmbeddingProvider,
    get_embedding_provider,
)

from .entities import Action, Entity
from .memory import Memory

logger = logging.getLogger(__name__)


class MemoryRepository:
    """Repository for storing and retrieving memories."""

    def __init__(
        self,
        db_pool: DatabasePool,
        tenant: str,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        """Initialize with database pool and tenant name."""
        self.db_pool = db_pool
        self.tenant = tenant
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
        self, content: str, user_tags: list[str]
    ) -> tuple[Memory, list[Memory]]:
        """Store a memory and return it with splash memories.

        Returns:
            (stored_memory, splash_memories)
        """
        # Create memory object
        memory = Memory(content=content)

        # Add user tags
        memory.add_tags(*user_tags)

        # Extract features from content
        self._extract_features(memory)

        # Get embedding
        memory.embedding = await self._get_embedding(content)

        # Store in database
        memory.id = await self._store_in_db(memory)

        # Get splash
        splash = await self._get_splash(memory)

        return memory, splash

    def _extract_features(self, memory: Memory) -> None:
        """Extract entities, actions, and auto-tags from memory content."""
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
        return await self.embedding_provider.embed(content)

    async def _store_in_db(self, memory: Memory) -> int:
        """Store memory in database, return ID."""
        async with self.db_pool.acquire_tenant(self.tenant) as conn:
            # Convert numpy array to list for storage
            embedding_list = (
                memory.embedding.tolist() if memory.embedding is not None else None
            )

            # Prepare metadata for JSON serialization
            # Convert sets to lists since sets aren't JSON serializable
            metadata_for_storage = memory.metadata.copy()
            if "tags" in metadata_for_storage and isinstance(
                metadata_for_storage["tags"], set
            ):
                metadata_for_storage["tags"] = sorted(metadata_for_storage["tags"])

            # Store and get the generated ID
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
            return row["id"]

    async def _get_splash(self, memory: Memory) -> list[Memory]:
        """Get memories in the similarity sweet spot (0.7-0.9).

        Returns up to 3 memories with similarity between 0.7 and 0.9.
        Empty list is valid if no memories fall in this range.
        """
        if memory.embedding is None:
            return []

        async with self.db_pool.acquire_tenant(self.tenant) as conn:
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

            return [self._row_to_memory(row) for row in rows]

    async def search(self, query: str, limit: int = 10) -> list[Memory]:
        """Search for memories by semantic similarity."""
        # Get embedding for the query
        query_embedding = await self._get_embedding(query)

        async with self.db_pool.acquire_tenant(self.tenant) as conn:
            rows = await conn.fetch(
                """
                SELECT id, content, embedding, metadata,
                       1 - (embedding <=> $1) as similarity
                FROM memories
                WHERE NOT forgotten
                AND embedding IS NOT NULL
                ORDER BY embedding <=> $1
                LIMIT $2
                """,
                query_embedding.tolist(),
                limit,
            )

            return [self._row_to_memory(row) for row in rows]

    async def get_recent(self, since: DateTime, limit: int = 10) -> list[Memory]:
        """Get recent memories since a given time."""
        async with self.db_pool.acquire_tenant(self.tenant) as conn:
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
