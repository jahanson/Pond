"""Performance tests for critical path operations.

Only testing the operations that:
1. Run on every request (hot path)
2. Could realistically regress
3. We control (not external services)
"""

import time

import pytest

from pond.domain import Memory, MemoryRepository, Tag


class TestCriticalPathPerformance:
    """Performance tests for operations that matter."""

    @pytest.fixture(scope="class")
    def warmed_repository(self):
        """Repository with pre-warmed spaCy model."""
        repo = MemoryRepository(pool=None, tenant="test")
        # Warm up the model
        warmup = Memory(content="Warmup text")
        repo._extract_features(warmup)
        return repo

    def test_feature_extraction_performance(self, warmed_repository):
        """Feature extraction should be fast for typical content."""
        # Typical memory content length
        content = (
            "Just learned that Python's walrus operator := can simplify list comprehensions. "
            "Really useful for avoiding duplicate computations in filtering and mapping operations."
        )

        memory = Memory(content=content)

        start = time.perf_counter()
        warmed_repository._extract_features(memory)
        duration = time.perf_counter() - start

        # Generous but will catch major regressions
        assert duration < 0.1, f"Feature extraction took {duration * 1000:.1f}ms"

    def test_tag_normalization_performance(self):
        """Tag normalization should be fast even for complex tags."""
        # Tags might come from user input frequently
        complex_tags = [
            "machine learning algorithms",
            "rock 'n' roll music",
            "object-oriented programming",
            "real-time data processing",
        ]

        start = time.perf_counter()
        for tag_text in complex_tags:
            tag = Tag(tag_text)
            _ = tag.normalized
        duration = time.perf_counter() - start

        # Should normalize 4 tags in under 100ms total
        assert duration < 0.1, f"Tag normalization took {duration * 1000:.1f}ms"

    def test_memory_validation_performance(self):
        """Memory validation should be essentially instant."""
        # This runs on every memory creation
        content = "x" * 5000  # Large but valid content

        start = time.perf_counter()
        memory = Memory(content=content)
        duration = time.perf_counter() - start

        # Validation should be microseconds, not milliseconds
        assert duration < 0.001, f"Memory validation took {duration * 1000:.1f}ms"


# Optional: Mark slow tests so they can be skipped during rapid development
@pytest.mark.slow
class TestSlowOperations:
    """Tests for operations we expect to be slow."""

    def test_model_load_time(self):
        """Document how long model loading takes."""
        repo = MemoryRepository(pool=None, tenant="test")

        start = time.perf_counter()
        _ = repo.nlp
        duration = time.perf_counter() - start

        # Just document it, don't fail
        print(f"\nspaCy model load time: {duration:.2f}s")
        # But do set a reasonable upper bound
        assert duration < 10.0, "Model loading unreasonably slow"
