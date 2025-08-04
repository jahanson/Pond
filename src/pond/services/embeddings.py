"""Embedding service for all types of embeddings - vectors, tags, etc."""
import re
from typing import Protocol

import numpy as np


class TagEmbedder(Protocol):
    """Protocol for tag embedding strategies."""

    def embed(self, tag: str) -> str:
        """Embed a single tag into string space."""
        ...


class VectorEmbedder(Protocol):
    """Protocol for vector embedding strategies."""

    async def embed(self, content: str) -> np.ndarray:
        """Embed content into vector space."""
        ...


class EmbeddingService:
    """Unified service for all embedding needs."""

    def __init__(
        self,
        tag_embedder: TagEmbedder | None = None,
        vector_embedder: VectorEmbedder | None = None,
    ):
        """Initialize with embedding strategies.

        Args:
            tag_embedder: Strategy for embedding tags (default: SpacyTagEmbedder)
            vector_embedder: Strategy for embedding content (default: None, will use OllamaEmbedder when implemented)
        """
        self.tag_embedder = tag_embedder or SpacyTagEmbedder()
        self.vector_embedder = vector_embedder  # Will default to OllamaEmbedder later

    def embed_tag(self, tag: str) -> str:
        """Embed a tag into normalized string space.

        This is a one-way transformation that preserves similarity:
        - "children's stories" → "child-story"
        - "stories for children" → "child-story"
        """
        return self.tag_embedder.embed(tag)

    def embed_tags(self, tags: list[str]) -> list[str]:
        """Embed multiple tags, deduplicating in embedding space.

        Tags that embed to the same string are deduplicated.
        Order is preserved for the first occurrence.
        """
        seen = set()
        embedded = []
        for tag in tags:
            if tag and isinstance(tag, str):
                embedded_tag = self.embed_tag(tag)
                if embedded_tag and embedded_tag not in seen:
                    embedded.append(embedded_tag)
                    seen.add(embedded_tag)
        return embedded

    async def embed_content(self, content: str) -> np.ndarray:
        """Embed content into vector space for semantic search.

        Returns a high-dimensional vector suitable for similarity calculations.
        """
        if not self.vector_embedder:
            raise NotImplementedError("Vector embedding not yet implemented")
        return await self.vector_embedder.embed(content)


class SpacyTagEmbedder:
    """Tag embedder using spaCy lemmatization with alphabetization."""

    def __init__(self):
        """Initialize spaCy model."""
        # Lazy import to avoid loading spaCy until needed
        self._nlp = None

    @property
    def nlp(self):
        """Lazy load spaCy model."""
        if self._nlp is None:
            import spacy
            self._nlp = spacy.load("en_core_web_lg")
        return self._nlp

    def embed(self, tag: str) -> str:
        """Embed tag using spaCy lemmatization with alphabetization.

        Process:
        - Lowercase
        - Remove stopwords and punctuation
        - Lemmatize remaining tokens
        - Sort alphabetically
        - Join with hyphens

        This creates collisions for semantically equivalent tags:
        - "machine learning" → "learn-machine"
        - "learning machine" → "learn-machine"
        """
        tag = tag.strip().lower()
        if not tag:
            return ""

        # Process with spaCy
        doc = self.nlp(tag)

        # Get lemmas, excluding stopwords, punctuation, and cleaning special chars
        lemmas = []
        for token in doc:
            # Skip stopwords and punctuation
            if token.is_stop or token.is_punct:
                continue

            # Get lemma and clean it
            lemma = token.lemma_.strip()

            # Remove special characters, keep only alphanumeric and hyphens
            lemma = re.sub(r'[^a-z0-9-]', '', lemma)

            if lemma:
                lemmas.append(lemma)

        # If no tokens remain after filtering, use original cleaned tag
        if not lemmas:
            cleaned = re.sub(r'[^a-z0-9-]', '', tag)
            return cleaned.replace(" ", "-") if cleaned else tag.replace(" ", "-")

        # Sort alphabetically and join
        return "-".join(sorted(lemmas))


class SimpleTagEmbedder:
    """Simple embedder for testing or when spaCy unavailable."""

    def embed(self, tag: str) -> str:
        """Basic embedding: lowercase and spaces to hyphens."""
        return tag.strip().lower().replace(" ", "-")
