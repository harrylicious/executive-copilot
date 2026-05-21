"""Unit tests for the RetrievalService local_search implementation."""

import pytest
from unittest.mock import MagicMock, patch

from app.config import GraphRAGSettings
from app.services.retrieval_service import RetrievalService, SearchResult


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return MagicMock()


@pytest.fixture
def config(tmp_path):
    """Create a GraphRAGSettings with a temporary vector store path."""
    return GraphRAGSettings(vector_store_path=str(tmp_path / "chroma_test"))


@pytest.fixture
def mock_embedding_model():
    """Create a mock EmbeddingModel."""
    model = MagicMock()
    model.embed_query.return_value = [0.1] * 384
    model.dimension = 384
    return model


@pytest.fixture
def mock_vector_store():
    """Create a mock ChromaVectorStore."""
    store = MagicMock()
    store.similarity_search.return_value = []
    return store


@pytest.fixture
def mock_graphrag_engine():
    """Create a mock GraphRAGEngine."""
    engine = MagicMock()
    engine.get_graph_neighborhood.return_value = {
        "entities": [],
        "relationships": [],
    }
    return engine


@pytest.fixture
def retrieval_service(mock_db, config, mock_embedding_model, mock_vector_store, mock_graphrag_engine):
    """Create a RetrievalService with mocked dependencies."""
    with patch(
        "app.services.retrieval_service.EmbeddingModel",
        return_value=mock_embedding_model,
    ), patch(
        "app.services.retrieval_service.ChromaVectorStore",
        return_value=mock_vector_store,
    ), patch(
        "app.services.retrieval_service.GraphRAGEngine",
        return_value=mock_graphrag_engine,
    ):
        service = RetrievalService(db=mock_db, config=config)
    # Ensure mocks are set after construction
    service.model = mock_embedding_model
    service.vector_store = mock_vector_store
    service.graphrag = mock_graphrag_engine
    return service


class TestLocalSearchQueryValidation:
    """Tests for query validation in local_search."""

    def test_rejects_empty_query(self, retrieval_service):
        """Should raise ValueError for empty query string."""
        with pytest.raises(ValueError, match="must not be empty"):
            retrieval_service.local_search(query="")

    def test_rejects_whitespace_only_query(self, retrieval_service):
        """Should raise ValueError for whitespace-only query."""
        with pytest.raises(ValueError, match="must not be empty"):
            retrieval_service.local_search(query="   ")

    def test_rejects_query_exceeding_1000_chars(self, retrieval_service):
        """Should raise ValueError for query exceeding 1000 characters."""
        long_query = "a" * 1001
        with pytest.raises(ValueError, match="exceeds 1000 characters"):
            retrieval_service.local_search(query=long_query)

    def test_accepts_query_at_1000_chars(self, retrieval_service):
        """Should accept query at exactly 1000 characters."""
        query = "a" * 1000
        result = retrieval_service.local_search(query=query)
        assert isinstance(result, SearchResult)

    def test_accepts_single_character_query(self, retrieval_service):
        """Should accept a single character query."""
        result = retrieval_service.local_search(query="x")
        assert isinstance(result, SearchResult)


class TestLocalSearchEmptyResults:
    """Tests for local_search when no results meet threshold."""

    def test_returns_empty_result_when_no_matches(self, retrieval_service):
        """Should return empty SearchResult when vector store returns nothing."""
        retrieval_service.vector_store.similarity_search.return_value = []

        result = retrieval_service.local_search(query="test query")

        assert result.chunks == []
        assert result.entities == []
        assert result.relationships == []
        assert result.community_summaries == []
        assert result.source_attributions == []

    def test_metadata_present_on_empty_results(self, retrieval_service):
        """Should include metadata even when results are empty."""
        retrieval_service.vector_store.similarity_search.return_value = []

        result = retrieval_service.local_search(query="test query")

        assert "query_time_ms" in result.metadata
        assert "total_chunks_searched" in result.metadata
        assert result.metadata["retrieval_mode"] == "local"
        assert result.metadata["total_chunks_searched"] == 0


class TestLocalSearchWithResults:
    """Tests for local_search with vector store results."""

    def test_generates_query_embedding(self, retrieval_service):
        """Should call embed_query with the query text."""
        retrieval_service.local_search(query="test query")

        retrieval_service.model.embed_query.assert_called_once_with("test query")

    def test_calls_similarity_search_with_params(self, retrieval_service):
        """Should pass correct parameters to similarity_search."""
        retrieval_service.local_search(
            query="test query", top_k=10, min_score=0.6
        )

        retrieval_service.vector_store.similarity_search.assert_called_once_with(
            query_embedding=[0.1] * 384,
            top_k=10,
            min_score=0.6,
        )

    def test_enriches_results_with_graph_neighborhood(self, retrieval_service, mock_db):
        """Should call get_graph_neighborhood for each result chunk."""
        # Setup: vector store returns one result
        retrieval_service.vector_store.similarity_search.return_value = [
            {
                "id": "file_1_chunk_0",
                "text": "Some text",
                "file_id": 1,
                "chunk_index": 0,
                "department": "engineering",
                "score": 0.8,
            }
        ]

        # Mock the chunk query
        mock_chunk = MagicMock()
        mock_chunk.id = 100
        mock_chunk.file_id = 1
        mock_chunk.chunk_index = 0

        # Mock file query for metadata
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.txt"
        mock_file.department = "engineering"
        mock_file.path = "engineering/test.txt"

        # Setup query chain
        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, "__tablename__") and model.__tablename__ == "chunks":
                mock_query.filter.return_value.first.return_value = mock_chunk
            elif hasattr(model, "__tablename__") and model.__tablename__ == "files":
                mock_query.filter.return_value.first.return_value = mock_file
            else:
                mock_query.filter.return_value.first.return_value = mock_chunk
            return mock_query

        mock_db.query.side_effect = query_side_effect

        retrieval_service.local_search(query="test query")

        retrieval_service.graphrag.get_graph_neighborhood.assert_called_once_with(
            chunk_id=100, hops=1
        )

    def test_includes_file_metadata_in_results(self, retrieval_service, mock_db):
        """Should include source file name, department, and path."""
        retrieval_service.vector_store.similarity_search.return_value = [
            {
                "id": "file_1_chunk_0",
                "text": "Some text",
                "file_id": 1,
                "chunk_index": 0,
                "department": "engineering",
                "score": 0.8,
            }
        ]

        # Mock chunk lookup
        mock_chunk = MagicMock()
        mock_chunk.id = 100
        mock_chunk.file_id = 1
        mock_chunk.chunk_index = 0

        # Mock file lookup
        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "report.docx"
        mock_file.department = "engineering"
        mock_file.path = "engineering/report.docx"

        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, "__tablename__") and model.__tablename__ == "chunks":
                mock_query.filter.return_value.first.return_value = mock_chunk
            elif hasattr(model, "__tablename__") and model.__tablename__ == "files":
                mock_query.filter.return_value.first.return_value = mock_file
            else:
                mock_query.filter.return_value.first.return_value = mock_chunk
            return mock_query

        mock_db.query.side_effect = query_side_effect

        result = retrieval_service.local_search(query="test query")

        assert len(result.chunks) == 1
        assert result.chunks[0]["file_name"] == "report.docx"
        assert result.chunks[0]["department"] == "engineering"
        assert result.chunks[0]["file_path"] == "engineering/report.docx"

    def test_results_ranked_by_combined_score_descending(self, retrieval_service, mock_db):
        """Should rank results by combined score in descending order."""
        retrieval_service.vector_store.similarity_search.return_value = [
            {
                "id": "file_1_chunk_0",
                "text": "Low similarity",
                "file_id": 1,
                "chunk_index": 0,
                "department": "eng",
                "score": 0.5,
            },
            {
                "id": "file_1_chunk_1",
                "text": "High similarity",
                "file_id": 1,
                "chunk_index": 1,
                "department": "eng",
                "score": 0.9,
            },
        ]

        # Mock chunk lookups - no graph connections
        mock_chunk = MagicMock()
        mock_chunk.id = 100

        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.txt"
        mock_file.department = "eng"
        mock_file.path = "eng/test.txt"

        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, "__tablename__") and model.__tablename__ == "chunks":
                mock_query.filter.return_value.first.return_value = mock_chunk
            elif hasattr(model, "__tablename__") and model.__tablename__ == "files":
                mock_query.filter.return_value.first.return_value = mock_file
            else:
                mock_query.filter.return_value.first.return_value = mock_chunk
            return mock_query

        mock_db.query.side_effect = query_side_effect

        result = retrieval_service.local_search(query="test query")

        assert len(result.chunks) == 2
        scores = [c["score"] for c in result.chunks]
        assert scores == sorted(scores, reverse=True)

    def test_source_attributions_deduplicated_by_file(self, retrieval_service, mock_db):
        """Should include each file only once in source_attributions."""
        retrieval_service.vector_store.similarity_search.return_value = [
            {
                "id": "file_1_chunk_0",
                "text": "Chunk 0",
                "file_id": 1,
                "chunk_index": 0,
                "department": "eng",
                "score": 0.8,
            },
            {
                "id": "file_1_chunk_1",
                "text": "Chunk 1",
                "file_id": 1,
                "chunk_index": 1,
                "department": "eng",
                "score": 0.7,
            },
        ]

        mock_chunk = MagicMock()
        mock_chunk.id = 100

        mock_file = MagicMock()
        mock_file.id = 1
        mock_file.name = "test.txt"
        mock_file.department = "eng"
        mock_file.path = "eng/test.txt"

        def query_side_effect(model):
            mock_query = MagicMock()
            if hasattr(model, "__tablename__") and model.__tablename__ == "chunks":
                mock_query.filter.return_value.first.return_value = mock_chunk
            elif hasattr(model, "__tablename__") and model.__tablename__ == "files":
                mock_query.filter.return_value.first.return_value = mock_file
            else:
                mock_query.filter.return_value.first.return_value = mock_chunk
            return mock_query

        mock_db.query.side_effect = query_side_effect

        result = retrieval_service.local_search(query="test query")

        assert len(result.source_attributions) == 1
        assert result.source_attributions[0]["file_id"] == 1

    def test_metadata_includes_retrieval_mode_local(self, retrieval_service):
        """Should set retrieval_mode to 'local' in metadata."""
        result = retrieval_service.local_search(query="test query")
        assert result.metadata["retrieval_mode"] == "local"

    def test_metadata_includes_query_time_ms(self, retrieval_service):
        """Should include query_time_ms in metadata."""
        result = retrieval_service.local_search(query="test query")
        assert "query_time_ms" in result.metadata
        assert isinstance(result.metadata["query_time_ms"], int)
        assert result.metadata["query_time_ms"] >= 0


class TestComputeCombinedScore:
    """Tests for _compute_combined_score method."""

    def test_default_weights(self, retrieval_service):
        """Should use 0.7 similarity weight and 0.3 graph weight by default."""
        score = retrieval_service._compute_combined_score(
            similarity=1.0, graph_relevance=0.0
        )
        assert abs(score - 0.7) < 1e-9

    def test_equal_weights(self, retrieval_service):
        """Should compute average when weights are equal."""
        score = retrieval_service._compute_combined_score(
            similarity=0.8, graph_relevance=0.6, sim_weight=0.5
        )
        assert abs(score - 0.7) < 1e-9

    def test_full_similarity_weight(self, retrieval_service):
        """Should return similarity when sim_weight is 1.0."""
        score = retrieval_service._compute_combined_score(
            similarity=0.9, graph_relevance=0.5, sim_weight=1.0
        )
        assert abs(score - 0.9) < 1e-9

    def test_full_graph_weight(self, retrieval_service):
        """Should return graph_relevance when sim_weight is 0.0."""
        score = retrieval_service._compute_combined_score(
            similarity=0.9, graph_relevance=0.5, sim_weight=0.0
        )
        assert abs(score - 0.5) < 1e-9

    def test_weighted_sum_formula(self, retrieval_service):
        """Should compute sim_weight * similarity + (1-sim_weight) * graph_relevance."""
        score = retrieval_service._compute_combined_score(
            similarity=0.8, graph_relevance=0.4, sim_weight=0.7
        )
        expected = 0.7 * 0.8 + 0.3 * 0.4
        assert abs(score - expected) < 1e-9


class TestNormalizeGraphRelevance:
    """Tests for _normalize_graph_relevance method."""

    def test_zero_max_connections_returns_zero(self, retrieval_service):
        """Should return 0.0 when max_connections is 0."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=5, max_connections=0
        )
        assert result == 0.0

    def test_negative_max_connections_returns_zero(self, retrieval_service):
        """Should return 0.0 when max_connections is negative."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=5, max_connections=-1
        )
        assert result == 0.0

    def test_normalizes_to_ratio(self, retrieval_service):
        """Should return connection_count / max_connections."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=3, max_connections=10
        )
        assert abs(result - 0.3) < 1e-9

    def test_max_connections_equals_count_returns_one(self, retrieval_service):
        """Should return 1.0 when connection_count equals max_connections."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=10, max_connections=10
        )
        assert result == 1.0

    def test_zero_connections_returns_zero(self, retrieval_service):
        """Should return 0.0 when connection_count is 0."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=0, max_connections=10
        )
        assert result == 0.0

    def test_capped_at_one(self, retrieval_service):
        """Should cap result at 1.0 even if count exceeds max."""
        result = retrieval_service._normalize_graph_relevance(
            connection_count=15, max_connections=10
        )
        assert result == 1.0


class TestSearchResultDataclass:
    """Tests for the SearchResult dataclass."""

    def test_default_empty_fields(self):
        """Should initialize with empty lists and dict by default."""
        result = SearchResult()
        assert result.chunks == []
        assert result.entities == []
        assert result.relationships == []
        assert result.community_summaries == []
        assert result.source_attributions == []
        assert result.metadata == {}

    def test_custom_initialization(self):
        """Should accept custom values for all fields."""
        result = SearchResult(
            chunks=[{"text": "hello"}],
            entities=[{"name": "Entity1"}],
            relationships=[{"source": "A", "target": "B"}],
            community_summaries=[{"summary": "test"}],
            source_attributions=[{"file_id": 1}],
            metadata={"query_time_ms": 42},
        )
        assert len(result.chunks) == 1
        assert len(result.entities) == 1
        assert result.metadata["query_time_ms"] == 42
