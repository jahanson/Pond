"""Tag domain model."""

import re


class Tag:
    """A tag that knows how to normalize itself."""

    # Class-level spaCy model (shared across all tags)
    _nlp = None

    def __init__(self, raw: str):
        """Create a tag from raw text."""
        self.raw = raw.strip()
        self._normalized: str | None = None

    @classmethod
    def _get_nlp(cls):
        """Lazy load spaCy model once for all tags."""
        if cls._nlp is None:
            import spacy

            # Only load what we need for lemmatization
            cls._nlp = spacy.load("en_core_web_lg", disable=["parser", "ner"])
        return cls._nlp

    @property
    def normalized(self) -> str:
        """Get the normalized form of this tag (cached)."""
        if self._normalized is None:
            self._normalized = self._normalize()
        return self._normalized

    def _normalize(self) -> str:
        """Normalize tag using spaCy lemmatization with alphabetization."""
        text = self.raw.lower()
        if not text:
            return ""

        # Process with spaCy
        doc = self._get_nlp()(text)

        # Get lemmas, excluding stopwords and punctuation
        lemmas = []
        for token in doc:
            if token.is_stop or token.is_punct:
                continue

            # Clean special characters
            lemma = re.sub(r"[^a-z0-9-]", "", token.lemma_.strip())
            if lemma:
                lemmas.append(lemma)

        # If no tokens remain, clean the original
        if not lemmas:
            cleaned = re.sub(r"[^a-z0-9-]", "", text)
            return cleaned.replace(" ", "-") if cleaned else text.replace(" ", "-")

        # Sort alphabetically and join
        return "-".join(sorted(lemmas))

    def __eq__(self, other) -> bool:
        """Tags are equal if they normalize to the same string."""
        if not isinstance(other, Tag):
            return False
        return self.normalized == other.normalized

    def __hash__(self) -> int:
        """Hash based on normalized form for use in sets."""
        return hash(self.normalized)

    def __repr__(self) -> str:
        return f"Tag({self.raw!r})"

    def __str__(self) -> str:
        return self.raw
