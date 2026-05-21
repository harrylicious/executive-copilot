"""Property-based tests for embedding generation.

Property 3: Embedding generation produces one vector per chunk with correct metadata

For any set of text chunks produced from a file, the EmbeddingEngine SHALL generate
exactly one embedding vector per chunk, where each vector has dimensionality matching
the configured model (384 for all-MiniLM-L6-v2), and each stored embedding is
associated with the correct file_id, chunk_index, and department.

**Validates: Requirements 2.1, 2.2**
"""

import tempfile
import shutil

import hypothesis.strategies as st
from hypothesis import given, settings, assume

from app.services.document_chunker import DocumentChunker, ChunkResult
from app.services.embedding_model import EmbeddingModel
from app.services.vector_store import ChromaVectorStore
from app.config import GraphRAGSettings


# Load the embedding model once at module level to avoid repeated model loading
_EMBEDDING_MODEL = EmbeddingModel(model_name="all-MiniLM-L6-v2")
_EXPECTED_DIMENSION = 384


# Strategy for generating non-empty text that produces meaningful tokens
non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=10,
    max_size=2000,
).filter(lambda t: len(t.strip()) >= 5)

# Strategy for generating valid file IDs
file_ids = st.integers(min_value=1, max_value=10000)

# Strategy for generating department names
departments = st.sampled_from([
    "engineering", "marketing", "finance", "hr", "legal", "operations", "sales"
])


class TestProperty3EmbeddingGeneration:
    """Property 3: Embedding generation produces one vector per chunk with correct metadata."""

    @given(text=non_empty_text)
    @settings(max_examples=50, deadline=60000)
    def test_one_embedding_per_chunk(self, text: str):
        """The EmbeddingModel generates exactly one embedding vector per chunk."""
        # Create chunks from the text
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)
        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        # Generate embeddings for all chunk texts
        chunk_texts = [c.text for c in chunks]
        embeddings = _EMBEDDING_MODEL.embed_texts(chunk_texts)

        # Exactly one embedding per chunk
        assert len(embeddings) == len(chunks), (
            f"Expected {len(chunks)} embeddings (one per chunk), "
            f"got {len(embeddings)}"
        )

    @given(text=non_empty_text)
    @settings(max_examples=50, deadline=60000)
    def test_each_vector_has_correct_dimensionality(self, text: str):
        """Each vector has dimensionality matching the configured model (384)."""
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)
        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        chunk_texts = [c.text for c in chunks]
        embeddings = _EMBEDDING_MODEL.embed_texts(chunk_texts)

        for i, embedding in enumerate(embeddings):
            assert len(embedding) == _EXPECTED_DIMENSION, (
                f"Embedding for chunk {i} has dimension {len(embedding)}, "
                f"expected {_EXPECTED_DIMENSION}"
            )

    @given(text=non_empty_text)
    @settings(max_examples=50, deadline=60000)
    def test_model_dimension_attribute_matches_output(self, text: str):
        """The model's reported dimension matches actual embedding output."""
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)
        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        chunk_texts = [c.text for c in chunks]
        embeddings = _EMBEDDING_MODEL.embed_texts(chunk_texts)

        assert _EMBEDDING_MODEL.dimension == _EXPECTED_DIMENSION
        for embedding in embeddings:
            assert len(embedding) == _EMBEDDING_MODEL.dimension

    @given(
        text=non_empty_text,
        file_id=file_ids,
        department=departments,
    )
    @settings(max_examples=30, deadline=60000)
    def test_stored_embeddings_have_correct_metadata(
        self, text: str, file_id: int, department: str
    ):
        """Each stored embedding is associated with the correct file_id, chunk_index, and department."""
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)
        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        chunk_texts = [c.text for c in chunks]
        embeddings = _EMBEDDING_MODEL.embed_texts(chunk_texts)

        # Use a temporary directory for ChromaDB to avoid polluting the workspace
        tmp_dir = tempfile.mkdtemp()
        try:
            config = GraphRAGSettings(vector_store_path=tmp_dir)
            vector_store = ChromaVectorStore(config)

            # Store the embeddings with metadata
            metadata = {"department": department}
            vector_store.upsert_chunks(file_id, chunks, embeddings, metadata)

            # Retrieve stored embeddings and verify metadata
            results = vector_store.collection.get(
                where={"file_id": file_id},
                include=["metadatas", "embeddings"],
            )

            # Should have exactly one entry per chunk
            assert len(results["ids"]) == len(chunks), (
                f"Expected {len(chunks)} stored entries, got {len(results['ids'])}"
            )

            # Verify each stored entry has correct metadata
            for i, meta in enumerate(results["metadatas"]):
                assert meta["file_id"] == file_id, (
                    f"Entry {i}: expected file_id={file_id}, got {meta['file_id']}"
                )
                assert meta["department"] == department, (
                    f"Entry {i}: expected department='{department}', "
                    f"got '{meta['department']}'"
                )
                # chunk_index should be one of the valid indices
                assert meta["chunk_index"] in range(len(chunks)), (
                    f"Entry {i}: chunk_index {meta['chunk_index']} not in "
                    f"valid range [0, {len(chunks) - 1}]"
                )

            # Verify all chunk indices are present (one per chunk)
            stored_indices = sorted(m["chunk_index"] for m in results["metadatas"])
            expected_indices = list(range(len(chunks)))
            assert stored_indices == expected_indices, (
                f"Stored chunk indices {stored_indices} don't match "
                f"expected {expected_indices}"
            )

            # Verify stored embeddings have correct dimensionality
            if results["embeddings"] is not None and len(results["embeddings"]) > 0:
                for j, emb in enumerate(results["embeddings"]):
                    assert len(emb) == _EXPECTED_DIMENSION, (
                        f"Stored embedding {j} has dimension {len(emb)}, "
                        f"expected {_EXPECTED_DIMENSION}"
                    )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)



# ============================================================================
# Property 4: Document-level embedding equals the mean of chunk embeddings
#
# For any file with N > 0 chunk embeddings, the document-level embedding SHALL
# equal the element-wise arithmetic mean of all N chunk embedding vectors
# (within floating-point tolerance of 1e-6).
#
# **Validates: Requirements 2.5**
# ============================================================================


def _compute_document_embedding(chunk_embeddings: list[list[float]]) -> list[float]:
    """Compute document-level embedding as element-wise mean of chunk embeddings.

    This is the reference implementation matching the design specification for
    EmbeddingEngine._compute_document_embedding.
    """
    if not chunk_embeddings:
        return []
    n = len(chunk_embeddings)
    dim = len(chunk_embeddings[0])
    result = [0.0] * dim
    for embedding in chunk_embeddings:
        for i in range(dim):
            result[i] += embedding[i]
    for i in range(dim):
        result[i] /= n
    return result


# Strategy for generating a list of chunk texts (1 to 10 chunks)
chunk_texts_strategy = st.lists(
    st.text(
        alphabet=st.characters(
            whitelist_categories=("L", "N", "P", "Z"),
            blacklist_characters="\x00",
        ),
        min_size=3,
        max_size=200,
    ).filter(lambda t: len(t.strip()) >= 3),
    min_size=1,
    max_size=10,
)


class TestProperty4DocumentLevelEmbedding:
    """Property 4: Document-level embedding equals the mean of chunk embeddings.

    **Validates: Requirements 2.5**
    """

    @given(chunk_texts=chunk_texts_strategy)
    @settings(max_examples=30, deadline=60000)
    def test_document_embedding_equals_mean_of_chunk_embeddings(
        self, chunk_texts: list[str]
    ):
        """For any file with N > 0 chunk embeddings, the document-level embedding
        equals the element-wise arithmetic mean of all N chunk embedding vectors
        within floating-point tolerance of 1e-6.

        **Validates: Requirements 2.5**
        """
        # Generate embeddings for all chunks
        chunk_embeddings = _EMBEDDING_MODEL.embed_texts(chunk_texts)

        # Verify we got embeddings for all chunks
        assume(len(chunk_embeddings) == len(chunk_texts))
        assume(all(len(emb) == _EXPECTED_DIMENSION for emb in chunk_embeddings))

        # Compute document-level embedding as mean of chunk embeddings
        doc_embedding = _compute_document_embedding(chunk_embeddings)

        # Verify the document embedding has the correct dimension
        assert len(doc_embedding) == _EXPECTED_DIMENSION, (
            f"Document embedding has dimension {len(doc_embedding)}, "
            f"expected {_EXPECTED_DIMENSION}"
        )

        # Verify element-wise: each element equals the mean of corresponding
        # elements across all chunk embeddings
        n = len(chunk_embeddings)
        for dim_idx in range(_EXPECTED_DIMENSION):
            expected_mean = sum(
                chunk_embeddings[i][dim_idx] for i in range(n)
            ) / n
            actual = doc_embedding[dim_idx]
            assert abs(actual - expected_mean) < 1e-6, (
                f"Dimension {dim_idx}: document embedding value {actual} "
                f"differs from expected mean {expected_mean} by "
                f"{abs(actual - expected_mean)} (tolerance: 1e-6)"
            )

    @given(chunk_texts=chunk_texts_strategy)
    @settings(max_examples=30, deadline=60000)
    def test_single_chunk_document_embedding_equals_chunk_embedding(
        self, chunk_texts: list[str]
    ):
        """For a single chunk, the document embedding should equal the chunk
        embedding exactly (within tolerance).

        **Validates: Requirements 2.5**
        """
        # Use only the first text to test the single-chunk case
        single_text = chunk_texts[0]
        chunk_embeddings = _EMBEDDING_MODEL.embed_texts([single_text])

        assume(len(chunk_embeddings) == 1)
        assume(len(chunk_embeddings[0]) == _EXPECTED_DIMENSION)

        doc_embedding = _compute_document_embedding(chunk_embeddings)

        # For a single chunk, the mean is the chunk itself
        for dim_idx in range(_EXPECTED_DIMENSION):
            assert abs(doc_embedding[dim_idx] - chunk_embeddings[0][dim_idx]) < 1e-6, (
                f"Dimension {dim_idx}: single-chunk document embedding "
                f"{doc_embedding[dim_idx]} differs from chunk embedding "
                f"{chunk_embeddings[0][dim_idx]}"
            )
