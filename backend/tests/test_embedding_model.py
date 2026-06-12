"""Unit tests for the EmbeddingModel service."""

import pytest

from app.services.embedding_model import EmbeddingModel


@pytest.fixture(scope="module")
def model():
    """Create an EmbeddingModel with default settings (module-scoped for performance)."""
    return EmbeddingModel()


class TestEmbeddingModelInit:
    """Tests for EmbeddingModel initialization."""

    def test_default_model_name(self, model):
        """Should initialize with default model name."""
        assert model.model_name == "all-MiniLM-L6-v2"

    def test_dimension_is_positive_integer(self, model):
        """Should expose a positive integer dimension."""
        assert isinstance(model.dimension, int)
        assert model.dimension > 0

    def test_dimension_matches_expected(self, model):
        """all-MiniLM-L6-v2 produces 384-dimensional embeddings."""
        assert model.dimension == 384

    def test_invalid_model_raises_runtime_error(self):
        """Should raise RuntimeError for an invalid model name."""
        with pytest.raises(RuntimeError, match="Failed to load embedding model"):
            EmbeddingModel(model_name="nonexistent-model-xyz-12345")


class TestEmbedTexts:
    """Tests for batch embedding generation."""

    def test_returns_one_embedding_per_text(self, model):
        """Should return exactly one embedding per input text."""
        texts = ["hello world", "foo bar", "test sentence"]
        result = model.embed_texts(texts)
        assert len(result) == 3

    def test_each_embedding_has_correct_dimension(self, model):
        """Each embedding should have the model's dimension."""
        texts = ["hello world", "another text"]
        result = model.embed_texts(texts)
        for embedding in result:
            assert len(embedding) == model.dimension

    def test_embeddings_are_lists_of_floats(self, model):
        """Each embedding should be a list of floats."""
        texts = ["test"]
        result = model.embed_texts(texts)
        assert isinstance(result[0], list)
        assert all(isinstance(v, float) for v in result[0])

    def test_empty_input_returns_empty_list(self, model):
        """Should return empty list for empty input."""
        result = model.embed_texts([])
        assert result == []

    def test_single_text_returns_single_embedding(self, model):
        """Should handle a single text input."""
        result = model.embed_texts(["single text"])
        assert len(result) == 1
        assert len(result[0]) == model.dimension

    def test_different_texts_produce_different_embeddings(self, model):
        """Semantically different texts should produce different embeddings."""
        texts = ["The cat sat on the mat", "Quantum physics is complex"]
        result = model.embed_texts(texts)
        assert result[0] != result[1]


class TestEmbedQuery:
    """Tests for single query embedding generation."""

    def test_returns_embedding_with_correct_dimension(self, model):
        """Should return an embedding with the model's dimension."""
        result = model.embed_query("test query")
        assert len(result) == model.dimension

    def test_returns_list_of_floats(self, model):
        """Should return a list of floats."""
        result = model.embed_query("test query")
        assert isinstance(result, list)
        assert all(isinstance(v, float) for v in result)

    def test_consistent_with_embed_texts(self, model):
        """embed_query should produce the same result as embed_texts for the same input."""
        query = "hello world"
        single_result = model.embed_query(query)
        batch_result = model.embed_texts([query])[0]
        # Allow small floating point differences
        for a, b in zip(single_result, batch_result):
            assert abs(a - b) < 1e-6
