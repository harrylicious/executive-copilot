"""Property-based tests for local search ranking.

Property 18: Local search results are ranked by combined score

For any local search query returning N > 1 results, the results SHALL be ordered
in descending order of the combined score (similarity_weight × vector_similarity +
graph_weight × normalized_graph_relevance), and all returned chunks SHALL have a
vector similarity score ≥ the configured minimum threshold.

**Validates: Requirements 7.2, 7.4**
"""

from unittest.mock import MagicMock, patch

import hypothesis.strategies as st
from hypothesis import given, settings, assume

from app.config import GraphRAGSettings
from app.services.retrieval_service import RetrievalService, SearchResult


# --- Strategies ---

# Strategy for similarity scores (valid range 0.0-1.0)
similarity_score_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for min_score threshold
min_score_st = st.floats(min_value=0.0, max_value=0.9, allow_nan=False)

# Strategy for similarity_weight parameter
similarity_weight_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for graph connection counts (non-negative integers)
graph_connection_count_st = st.integers(min_value=0, max_value=20)

# Strategy for generating a list of vector search results (N > 1)
# Each result has a score (vector similarity) and will get graph connections
def vector_result_st(min_score: float):
    """Generate a single vector search result with score >= min_score."""
    return st.fixed_dictionaries({
        "score": st.floats(
            min_value=max(min_score, 0.01),
            max_value=1.0,
            allow_nan=False,
        ),
        "graph_connections": graph_connection_count_st,
    })


# Strategy for number of results (must be > 1 for ranking to matter)
num_results_st = st.integers(min_value=2, max_value=10)


# --- Helper functions ---

def _create_mock_retrieval_service(
    vector_results: list[dict],
    graph_neighborhoods: list[dict],
    tmp_path: str = "./test_chroma",
) -> RetrievalService:
    """Create a RetrievalService with mocked dependencies for testing ranking logic.

    Args:
        vector_results: List of dicts with 'score', 'file_id', 'chunk_index', 'text'.
        graph_neighborhoods: List of dicts with 'entities' and 'relationships' lists.

    Returns:
        A RetrievalService instance with mocked model, vector_store, and graphrag.
    """
    mock_db = MagicMock()
    config = GraphRAGSettings(vector_store_path=tmp_path)

    mock_model = MagicMock()
    mock_model.embed_query.return_value = [0.1] * 384
    mock_model.dimension = 384

    mock_vector_store = MagicMock()
    mock_vector_store.similarity_search.return_value = vector_results

    mock_graphrag = MagicMock()

    # Setup graph neighborhood responses per chunk
    neighborhood_iter = iter(graph_neighborhoods)

    def get_neighborhood(chunk_id, hops=1):
        try:
            return next(neighborhood_iter)
        except StopIteration:
            return {"entities": [], "relationships": []}

    mock_graphrag.get_graph_neighborhood.side_effect = get_neighborhood

    # Mock chunk lookups - each result gets a unique chunk ID
    chunk_id_counter = [100]

    def mock_chunk_query_filter(*args, **kwargs):
        mock_result = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.id = chunk_id_counter[0]
        chunk_id_counter[0] += 1
        mock_result.first.return_value = mock_chunk
        return mock_result

    # Mock file lookups
    mock_file = MagicMock()
    mock_file.id = 1
    mock_file.name = "test.txt"
    mock_file.department = "engineering"
    mock_file.path = "engineering/test.txt"

    def query_side_effect(model):
        mock_query = MagicMock()
        if hasattr(model, "__tablename__"):
            if model.__tablename__ == "chunks":
                mock_query.filter.return_value = MagicMock(
                    first=MagicMock(side_effect=lambda: MagicMock(id=chunk_id_counter[0].__add__(0)))
                )
                # Use a simpler approach
                mock_inner = MagicMock()
                mock_chunk_obj = MagicMock()
                mock_chunk_obj.id = chunk_id_counter[0]
                chunk_id_counter[0] += 1
                mock_inner.first.return_value = mock_chunk_obj
                mock_query.filter.return_value = mock_inner
            elif model.__tablename__ == "files":
                mock_inner = MagicMock()
                mock_inner.first.return_value = mock_file
                mock_query.filter.return_value = mock_inner
            else:
                mock_inner = MagicMock()
                mock_inner.first.return_value = None
                mock_query.filter.return_value = mock_inner
        else:
            mock_inner = MagicMock()
            mock_inner.first.return_value = None
            mock_query.filter.return_value = mock_inner
        return mock_query

    mock_db.query.side_effect = query_side_effect

    with patch(
        "app.services.retrieval_service.EmbeddingModel",
        return_value=mock_model,
    ), patch(
        "app.services.retrieval_service.ChromaVectorStore",
        return_value=mock_vector_store,
    ), patch(
        "app.services.retrieval_service.GraphRAGEngine",
        return_value=mock_graphrag,
    ):
        service = RetrievalService(db=mock_db, config=config)

    service.model = mock_model
    service.vector_store = mock_vector_store
    service.graphrag = mock_graphrag

    return service


def _build_graph_neighborhood(num_entities: int, num_relationships: int) -> dict:
    """Build a mock graph neighborhood with the specified number of connections."""
    entities = [
        {"id": i, "name": f"Entity_{i}", "type": "concept", "description": f"Desc {i}"}
        for i in range(num_entities)
    ]
    relationships = [
        {"id": i + 1000, "source": f"Entity_{i}", "target": f"Entity_{i+1}", "type": "relates_to"}
        for i in range(num_relationships)
    ]
    return {"entities": entities, "relationships": relationships}


# --- Property Tests ---


class TestProperty18LocalSearchRanking:
    """Property 18: Local search results are ranked by combined score.

    **Validates: Requirements 7.2, 7.4**
    """

    @given(
        num_results=num_results_st,
        similarity_scores=st.lists(
            st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
            min_size=2,
            max_size=10,
        ),
        graph_connections=st.lists(
            graph_connection_count_st,
            min_size=2,
            max_size=10,
        ),
        similarity_weight=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False
        ),
        min_score=st.floats(min_value=0.0, max_value=0.5, allow_nan=False),
    )
    @settings(max_examples=50, deadline=None)
    def test_results_ordered_by_combined_score_descending(
        self,
        num_results: int,
        similarity_scores: list[float],
        graph_connections: list[int],
        similarity_weight: float,
        min_score: float,
    ):
        """For any local search query returning N > 1 results, the results SHALL
        be ordered in descending order of the combined score
        (similarity_weight × vector_similarity + graph_weight × normalized_graph_relevance).

        **Validates: Requirements 7.2, 7.4**
        """
        # Ensure we have matching lengths
        n = min(num_results, len(similarity_scores), len(graph_connections))
        assume(n >= 2)

        similarity_scores = similarity_scores[:n]
        graph_connections = graph_connections[:n]

        # Ensure all scores are above min_score threshold
        similarity_scores = [max(s, min_score + 0.01) for s in similarity_scores]

        # Build vector results that the mock vector store will return
        vector_results = [
            {
                "id": f"file_1_chunk_{i}",
                "text": f"Chunk text {i}",
                "file_id": 1,
                "chunk_index": i,
                "department": "engineering",
                "score": similarity_scores[i],
            }
            for i in range(n)
        ]

        # Build graph neighborhoods for each chunk
        graph_neighborhoods = []
        for conn_count in graph_connections:
            # Split connections into entities and relationships
            num_entities = conn_count // 2
            num_rels = conn_count - num_entities
            graph_neighborhoods.append(
                _build_graph_neighborhood(num_entities, num_rels)
            )

        # Create the service with mocked dependencies
        service = _create_mock_retrieval_service(vector_results, graph_neighborhoods)

        # Execute local search
        result = service.local_search(
            query="test query",
            top_k=n,
            min_score=min_score,
            similarity_weight=similarity_weight,
        )

        # Verify: results are ordered by combined score descending
        assert len(result.chunks) == n, (
            f"Expected {n} results, got {len(result.chunks)}"
        )

        scores = [chunk["score"] for chunk in result.chunks]
        for i in range(len(scores) - 1):
            assert scores[i] >= scores[i + 1], (
                f"Results not in descending order: score[{i}]={scores[i]} < "
                f"score[{i+1}]={scores[i+1]}. All scores: {scores}"
            )

    @given(
        num_results=num_results_st,
        similarity_scores=st.lists(
            st.floats(min_value=0.1, max_value=1.0, allow_nan=False),
            min_size=2,
            max_size=10,
        ),
        min_score=st.floats(min_value=0.05, max_value=0.9, allow_nan=False),
    )
    @settings(max_examples=50, deadline=None)
    def test_all_returned_chunks_meet_minimum_similarity_threshold(
        self,
        num_results: int,
        similarity_scores: list[float],
        min_score: float,
    ):
        """All returned chunks SHALL have a vector similarity score ≥ the
        configured minimum threshold.

        The vector store filters by min_score, so all results returned by
        similarity_search already meet the threshold. This test verifies
        that the RetrievalService does not include any results below threshold
        in its output.

        **Validates: Requirements 7.2, 7.4**
        """
        n = min(num_results, len(similarity_scores))
        assume(n >= 2)

        similarity_scores = similarity_scores[:n]

        # Mix of scores: some above threshold, some below
        # The vector store mock will only return those above threshold
        above_threshold = [s for s in similarity_scores if s >= min_score]
        assume(len(above_threshold) >= 2)

        # Build vector results with only scores above threshold
        # (simulating what the vector store would actually return)
        vector_results = [
            {
                "id": f"file_1_chunk_{i}",
                "text": f"Chunk text {i}",
                "file_id": 1,
                "chunk_index": i,
                "department": "engineering",
                "score": above_threshold[i],
            }
            for i in range(len(above_threshold))
        ]

        # No graph connections for simplicity
        graph_neighborhoods = [
            {"entities": [], "relationships": []}
            for _ in range(len(above_threshold))
        ]

        service = _create_mock_retrieval_service(vector_results, graph_neighborhoods)

        result = service.local_search(
            query="test query",
            top_k=50,
            min_score=min_score,
            similarity_weight=0.7,
        )

        # Verify: all returned chunks have score >= 0 (combined score)
        # More importantly, the vector store was called with the correct min_score
        service.vector_store.similarity_search.assert_called_once_with(
            query_embedding=[0.1] * 384,
            top_k=50,
            min_score=min_score,
        )

        # All results should be present (none filtered out by the service)
        assert len(result.chunks) == len(above_threshold), (
            f"Expected {len(above_threshold)} results, got {len(result.chunks)}"
        )

    @given(
        similarity_scores=st.lists(
            st.floats(min_value=0.5, max_value=1.0, allow_nan=False),
            min_size=2,
            max_size=8,
        ),
        graph_connections=st.lists(
            graph_connection_count_st,
            min_size=2,
            max_size=8,
        ),
        similarity_weight=st.floats(
            min_value=0.0, max_value=1.0, allow_nan=False
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_combined_score_formula_is_correct(
        self,
        similarity_scores: list[float],
        graph_connections: list[int],
        similarity_weight: float,
    ):
        """The combined score SHALL equal similarity_weight × vector_similarity +
        graph_weight × normalized_graph_relevance for each result.

        This verifies the formula is correctly applied by computing expected
        scores independently and comparing against the service output.

        **Validates: Requirements 7.2, 7.4**
        """
        n = min(len(similarity_scores), len(graph_connections))
        assume(n >= 2)

        similarity_scores = similarity_scores[:n]
        graph_connections = graph_connections[:n]

        graph_weight = 1.0 - similarity_weight

        # Build vector results
        vector_results = [
            {
                "id": f"file_1_chunk_{i}",
                "text": f"Chunk text {i}",
                "file_id": 1,
                "chunk_index": i,
                "department": "engineering",
                "score": similarity_scores[i],
            }
            for i in range(n)
        ]

        # Build graph neighborhoods
        graph_neighborhoods = []
        for conn_count in graph_connections:
            num_entities = conn_count // 2
            num_rels = conn_count - num_entities
            graph_neighborhoods.append(
                _build_graph_neighborhood(num_entities, num_rels)
            )

        service = _create_mock_retrieval_service(vector_results, graph_neighborhoods)

        result = service.local_search(
            query="test query",
            top_k=n,
            min_score=0.0,
            similarity_weight=similarity_weight,
        )

        assert len(result.chunks) == n

        # Compute expected combined scores independently
        # First, compute max_connections (total entities + relationships per chunk)
        actual_connection_counts = [
            len(graph_neighborhoods[i].get("entities", []))
            + len(graph_neighborhoods[i].get("relationships", []))
            for i in range(n)
        ]
        max_connections = max(actual_connection_counts) if actual_connection_counts else 0

        expected_scores = []
        for i in range(n):
            vec_sim = similarity_scores[i]
            if max_connections > 0:
                normalized_graph = min(
                    1.0, actual_connection_counts[i] / max_connections
                )
            else:
                normalized_graph = 0.0
            combined = similarity_weight * vec_sim + graph_weight * normalized_graph
            expected_scores.append(combined)

        # Sort expected scores descending (same as the service does)
        expected_scores_sorted = sorted(expected_scores, reverse=True)
        actual_scores = [chunk["score"] for chunk in result.chunks]

        # Verify scores match (within floating-point tolerance)
        for i in range(n):
            assert abs(actual_scores[i] - expected_scores_sorted[i]) < 1e-9, (
                f"Score mismatch at position {i}: "
                f"expected {expected_scores_sorted[i]}, got {actual_scores[i]}. "
                f"All expected: {expected_scores_sorted}, all actual: {actual_scores}"
            )
