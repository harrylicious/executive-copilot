"""Unit tests for the ChromaVectorStore service."""

import tempfile

import pytest

from app.config import GraphRAGSettings
from app.services.document_chunker import ChunkResult
from app.services.vector_store import ChromaVectorStore


@pytest.fixture
def temp_chroma_path(tmp_path):
    """Provide a temporary directory for ChromaDB storage."""
    return str(tmp_path / "chroma_test_db")


@pytest.fixture
def config(temp_chroma_path):
    """Create a GraphRAGSettings with a temporary vector store path."""
    return GraphRAGSettings(vector_store_path=temp_chroma_path)


@pytest.fixture
def vector_store(config):
    """Create a ChromaVectorStore instance with temporary storage."""
    return ChromaVectorStore(config)


@pytest.fixture
def sample_chunks():
    """Create sample ChunkResult objects for testing."""
    return [
        ChunkResult(text="Hello world, this is chunk zero.", chunk_index=0, start_offset=0, end_offset=31),
        ChunkResult(text="This is the second chunk of text.", chunk_index=1, start_offset=25, end_offset=57),
        ChunkResult(text="Final chunk with some content.", chunk_index=2, start_offset=50, end_offset=80),
    ]


@pytest.fixture
def sample_embeddings():
    """Create sample embedding vectors (384-dim like all-MiniLM-L6-v2)."""
    import random

    random.seed(42)
    return [
        [random.uniform(-1, 1) for _ in range(384)],
        [random.uniform(-1, 1) for _ in range(384)],
        [random.uniform(-1, 1) for _ in range(384)],
    ]


class TestChromaVectorStoreInit:
    """Tests for ChromaVectorStore initialization."""

    def test_initializes_with_config(self, vector_store):
        """Should initialize ChromaDB client and collection."""
        assert vector_store.client is not None
        assert vector_store.collection is not None

    def test_collection_name_is_kb_chunks(self, vector_store):
        """Should create collection named 'kb_chunks'."""
        assert vector_store.collection.name == "kb_chunks"

    def test_collection_uses_cosine_space(self, vector_store):
        """Should configure collection with cosine similarity space."""
        metadata = vector_store.collection.metadata
        assert metadata.get("hnsw:space") == "cosine"


class TestUpsertChunks:
    """Tests for the upsert_chunks method."""

    def test_upserts_chunks_with_metadata(self, vector_store, sample_chunks, sample_embeddings):
        """Should store chunks with correct metadata."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        # Verify chunks are stored
        results = vector_store.collection.get(where={"file_id": 1})
        assert len(results["ids"]) == 3

    def test_stores_correct_metadata_fields(self, vector_store, sample_chunks, sample_embeddings):
        """Should store file_id, chunk_index, and department in metadata."""
        metadata = {"department": "sales"}
        vector_store.upsert_chunks(
            file_id=42,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.collection.get(
            where={"file_id": 42},
            include=["metadatas"],
        )
        for meta in results["metadatas"]:
            assert meta["file_id"] == 42
            assert meta["department"] == "sales"
            assert "chunk_index" in meta

    def test_stores_chunk_text_as_document(self, vector_store, sample_chunks, sample_embeddings):
        """Should store chunk text as the document content."""
        metadata = {"department": "hr"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.collection.get(
            where={"file_id": 1},
            include=["documents"],
        )
        texts = set(results["documents"])
        expected_texts = {c.text for c in sample_chunks}
        assert texts == expected_texts

    def test_replaces_existing_embeddings_on_upsert(self, vector_store, sample_chunks, sample_embeddings):
        """Should replace existing embeddings for the same file_id."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        # Upsert with different chunks
        new_chunks = [
            ChunkResult(text="New content here.", chunk_index=0, start_offset=0, end_offset=17),
        ]
        new_embeddings = [sample_embeddings[0]]
        vector_store.upsert_chunks(
            file_id=1,
            chunks=new_chunks,
            embeddings=new_embeddings,
            metadata=metadata,
        )

        results = vector_store.collection.get(where={"file_id": 1})
        assert len(results["ids"]) == 1

    def test_empty_chunks_does_nothing(self, vector_store, sample_embeddings):
        """Should handle empty chunks list gracefully."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=[],
            embeddings=[],
            metadata=metadata,
        )

        results = vector_store.collection.get(where={"file_id": 1})
        assert len(results["ids"]) == 0

    def test_generates_correct_ids(self, vector_store, sample_chunks, sample_embeddings):
        """Should generate IDs in format file_{id}_chunk_{index}."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=5,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.collection.get(where={"file_id": 5})
        expected_ids = {"file_5_chunk_0", "file_5_chunk_1", "file_5_chunk_2"}
        assert set(results["ids"]) == expected_ids


class TestDeleteByFile:
    """Tests for the delete_by_file method."""

    def test_deletes_all_chunks_for_file(self, vector_store, sample_chunks, sample_embeddings):
        """Should remove all embeddings for the specified file_id."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        vector_store.delete_by_file(file_id=1)

        results = vector_store.collection.get(where={"file_id": 1})
        assert len(results["ids"]) == 0

    def test_does_not_affect_other_files(self, vector_store, sample_chunks, sample_embeddings):
        """Should only delete embeddings for the specified file_id."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )
        vector_store.upsert_chunks(
            file_id=2,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        vector_store.delete_by_file(file_id=1)

        # File 1 should be gone
        results_1 = vector_store.collection.get(where={"file_id": 1})
        assert len(results_1["ids"]) == 0

        # File 2 should remain
        results_2 = vector_store.collection.get(where={"file_id": 2})
        assert len(results_2["ids"]) == 3

    def test_delete_nonexistent_file_does_not_error(self, vector_store):
        """Should handle deletion of non-existent file_id gracefully."""
        # Should not raise
        vector_store.delete_by_file(file_id=999)


class TestSimilaritySearch:
    """Tests for the similarity_search method."""

    def test_returns_similar_chunks(self, vector_store, sample_chunks, sample_embeddings):
        """Should return chunks similar to the query embedding."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        # Search with the first embedding (should find itself as most similar)
        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=3,
            min_score=0.0,
        )

        assert len(results) > 0
        # The most similar should be the exact match
        assert results[0]["score"] > 0.9

    def test_respects_top_k_limit(self, vector_store, sample_chunks, sample_embeddings):
        """Should return at most top_k results."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=1,
            min_score=0.0,
        )

        assert len(results) <= 1

    def test_filters_by_min_score(self, vector_store, sample_chunks, sample_embeddings):
        """Should exclude results below min_score threshold."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        # Use a very high min_score to filter most results
        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=10,
            min_score=0.99,
        )

        # Only the exact match (or very close) should pass
        for result in results:
            assert result["score"] >= 0.99

    def test_applies_metadata_filters(self, vector_store, sample_chunks, sample_embeddings):
        """Should filter results by metadata when filters are provided."""
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata={"department": "engineering"},
        )
        vector_store.upsert_chunks(
            file_id=2,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata={"department": "sales"},
        )

        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=10,
            min_score=0.0,
            filters={"department": "sales"},
        )

        for result in results:
            assert result["department"] == "sales"

    def test_results_sorted_by_score_descending(self, vector_store, sample_chunks, sample_embeddings):
        """Should return results sorted by score in descending order."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=10,
            min_score=0.0,
        )

        if len(results) > 1:
            scores = [r["score"] for r in results]
            assert scores == sorted(scores, reverse=True)

    def test_result_contains_required_fields(self, vector_store, sample_chunks, sample_embeddings):
        """Should return results with all required fields."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=3,
            min_score=0.0,
        )

        assert len(results) > 0
        required_fields = {"id", "text", "file_id", "chunk_index", "department", "score"}
        for result in results:
            assert set(result.keys()) == required_fields

    def test_empty_collection_returns_empty_list(self, vector_store, sample_embeddings):
        """Should return empty list when no embeddings are stored."""
        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=5,
            min_score=0.0,
        )

        assert results == []

    def test_score_is_between_zero_and_one(self, vector_store, sample_chunks, sample_embeddings):
        """Should return scores in the range [0.0, 1.0]."""
        metadata = {"department": "engineering"}
        vector_store.upsert_chunks(
            file_id=1,
            chunks=sample_chunks,
            embeddings=sample_embeddings,
            metadata=metadata,
        )

        results = vector_store.similarity_search(
            query_embedding=sample_embeddings[0],
            top_k=10,
            min_score=0.0,
        )

        for result in results:
            assert 0.0 <= result["score"] <= 1.0
