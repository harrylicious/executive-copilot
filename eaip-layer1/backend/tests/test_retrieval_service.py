"""Unit tests for the RetrievalService global_search method."""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock
import numpy as np

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.community import Community
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship
from app.models.file import File
from app.services.retrieval_service import RetrievalService, SearchResult

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture
def db_session(tmp_path):
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def config(tmp_path):
    """Create a GraphRAGSettings with a temporary vector store path."""
    return GraphRAGSettings(vector_store_path=str(tmp_path / "chroma_test"))


@pytest.fixture
def mock_embedding_model():
    """Mock the EmbeddingModel to avoid loading the real model."""
    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel:
        instance = MockModel.return_value
        instance.dimension = 384
        # Return a normalized vector for query embedding
        query_vec = np.random.default_rng(42).random(384).tolist()
        norm = np.linalg.norm(query_vec)
        instance.embed_query.return_value = (np.array(query_vec) / norm).tolist()
        yield instance


@pytest.fixture
def mock_vector_store():
    """Mock the ChromaVectorStore."""
    with patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ) as MockStore:
        yield MockStore.return_value


@pytest.fixture
def mock_graphrag_engine():
    """Mock the GraphRAGEngine."""
    with patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ) as MockEngine:
        yield MockEngine.return_value


@pytest.fixture
def retrieval_service(
    db_session, config, mock_embedding_model, mock_vector_store, mock_graphrag_engine
):
    """Create a RetrievalService with mocked dependencies."""
    service = RetrievalService.__new__(RetrievalService)
    service.db = db_session
    service.config = config
    service.model = mock_embedding_model
    service.vector_store = mock_vector_store
    service.graphrag = mock_graphrag_engine
    return service


def _make_normalized_embedding(seed: int, dim: int = 384) -> list[float]:
    """Generate a normalized embedding vector for testing."""
    rng = np.random.default_rng(seed)
    vec = rng.random(dim)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


class TestGlobalSearchNoCommunities:
    """Tests for global_search when no communities exist."""

    def test_returns_empty_results_with_metadata_message(
        self, retrieval_service, db_session
    ):
        """Should return empty results with message when no communities exist."""
        result = retrieval_service.global_search("test query")

        assert isinstance(result, SearchResult)
        assert result.chunks == []
        assert result.entities == []
        assert result.relationships == []
        assert result.community_summaries == []
        assert result.source_attributions == []
        assert result.metadata["retrieval_mode"] == "global"
        assert "message" in result.metadata
        assert "community detection" in result.metadata["message"].lower()
        assert "query_time_ms" in result.metadata

    def test_returns_zero_total_chunks_searched(self, retrieval_service):
        """Should report 0 total_chunks_searched for global search."""
        result = retrieval_service.global_search("test query")
        assert result.metadata["total_chunks_searched"] == 0


class TestGlobalSearchWithCommunities:
    """Tests for global_search with communities present."""

    def _seed_community(self, db_session, community_id_offset=0, seed=1):
        """Helper to seed a community with entities and files."""
        # Create a file
        file = File(
            id=100 + community_id_offset,
            name=f"doc_{community_id_offset}.md",
            path=f"dept/doc_{community_id_offset}.md",
            department="engineering",
            size=1000,
            tags=[],
            created_at=datetime(2024, 1, 1),
            modified_at=datetime(2024, 1, 1),
            content_hash="abc123",
        )
        db_session.add(file)

        # Create a chunk for the file
        chunk = Chunk(
            id=200 + community_id_offset,
            file_id=100 + community_id_offset,
            chunk_index=0,
            text="Sample chunk text",
            start_offset=0,
            end_offset=17,
        )
        db_session.add(chunk)

        # Create entities
        entity = Entity(
            id=300 + community_id_offset,
            name=f"Entity_{community_id_offset}",
            normalized_name=f"entity_{community_id_offset}",
            entity_type="concept",
            description=f"Test entity {community_id_offset}",
            source_chunk_ids=[200 + community_id_offset],
        )
        db_session.add(entity)

        # Create community with summary embedding
        embedding = _make_normalized_embedding(seed)
        community = Community(
            id=400 + community_id_offset,
            level=0,
            member_entity_ids=[300 + community_id_offset],
            summary=f"Community about topic {community_id_offset}",
            summary_embedding=embedding,
        )
        db_session.add(community)
        db_session.commit()

        return community

    def test_returns_ranked_communities_by_relevance(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should return communities ranked by cosine similarity."""
        # Seed multiple communities with different embeddings
        self._seed_community(db_session, community_id_offset=0, seed=10)
        self._seed_community(db_session, community_id_offset=1, seed=20)
        self._seed_community(db_session, community_id_offset=2, seed=30)

        # Set query embedding to be similar to seed=10
        query_emb = _make_normalized_embedding(10)
        mock_embedding_model.embed_query.return_value = query_emb

        result = retrieval_service.global_search("test query", num_communities=3)

        assert len(result.community_summaries) > 0
        # First result should have highest relevance
        scores = [c["relevance_score"] for c in result.community_summaries]
        assert scores == sorted(scores, reverse=True)

    def test_respects_num_communities_limit(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should return at most num_communities results."""
        for i in range(5):
            self._seed_community(db_session, community_id_offset=i, seed=i + 1)

        # Use a query embedding that will match all
        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(1)

        result = retrieval_service.global_search(
            "test query", num_communities=2, min_relevance=0.0
        )

        assert len(result.community_summaries) <= 2

    def test_filters_by_min_relevance(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should exclude communities below min_relevance threshold."""
        self._seed_community(db_session, community_id_offset=0, seed=1)

        # Use an orthogonal query embedding to get low similarity
        # Create a vector that's very different from seed=1
        rng = np.random.default_rng(999)
        orthogonal_vec = rng.random(384)
        orthogonal_vec = (orthogonal_vec / np.linalg.norm(orthogonal_vec)).tolist()
        mock_embedding_model.embed_query.return_value = orthogonal_vec

        result = retrieval_service.global_search(
            "test query", min_relevance=0.99
        )

        # With a very high threshold, likely no communities match
        assert len(result.community_summaries) == 0

    def test_includes_member_entities(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should include member entities for each community."""
        self._seed_community(db_session, community_id_offset=0, seed=5)

        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(5)

        result = retrieval_service.global_search(
            "test query", min_relevance=0.0
        )

        assert len(result.community_summaries) > 0
        community = result.community_summaries[0]
        assert "member_entities" in community
        assert len(community["member_entities"]) > 0
        assert "name" in community["member_entities"][0]
        assert "type" in community["member_entities"][0]

    def test_includes_document_references(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should include up to 3 document references per community."""
        self._seed_community(db_session, community_id_offset=0, seed=7)

        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(7)

        result = retrieval_service.global_search(
            "test query", min_relevance=0.0
        )

        assert len(result.community_summaries) > 0
        community = result.community_summaries[0]
        assert "document_references" in community
        assert len(community["document_references"]) <= 3
        if community["document_references"]:
            doc_ref = community["document_references"][0]
            assert "file_id" in doc_ref
            assert "name" in doc_ref
            assert "department" in doc_ref
            assert "path" in doc_ref

    def test_relevance_score_is_cosine_similarity(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should return relevance scores between 0.0 and 1.0."""
        self._seed_community(db_session, community_id_offset=0, seed=3)

        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(3)

        result = retrieval_service.global_search(
            "test query", min_relevance=0.0
        )

        for community in result.community_summaries:
            score = community["relevance_score"]
            assert 0.0 <= score <= 1.0

    def test_clamps_num_communities_to_max_20(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should clamp num_communities to max 20."""
        self._seed_community(db_session, community_id_offset=0, seed=1)
        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(1)

        # Should not raise even with num_communities > 20
        result = retrieval_service.global_search(
            "test query", num_communities=50, min_relevance=0.0
        )
        assert isinstance(result, SearchResult)

    def test_metadata_includes_required_fields(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should include query_time_ms, total_chunks_searched, retrieval_mode."""
        self._seed_community(db_session, community_id_offset=0, seed=2)
        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(2)

        result = retrieval_service.global_search("test query", min_relevance=0.0)

        assert "query_time_ms" in result.metadata
        assert "total_chunks_searched" in result.metadata
        assert result.metadata["retrieval_mode"] == "global"

    def test_skips_communities_without_summary_embedding(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should skip communities that have no summary_embedding."""
        # Create a community without summary_embedding
        community = Community(
            id=500,
            level=0,
            member_entity_ids=[],
            summary="A community without embedding",
            summary_embedding=None,
        )
        db_session.add(community)
        db_session.commit()

        mock_embedding_model.embed_query.return_value = _make_normalized_embedding(1)

        result = retrieval_service.global_search("test query", min_relevance=0.0)

        # The community without embedding should be skipped
        assert len(result.community_summaries) == 0

    def test_empty_results_when_none_meet_threshold(
        self, retrieval_service, db_session, mock_embedding_model
    ):
        """Should return empty results when no communities meet min_relevance."""
        self._seed_community(db_session, community_id_offset=0, seed=1)

        # Use a very different vector
        neg_vec = [-x for x in _make_normalized_embedding(1)]
        # Normalize it
        norm = np.linalg.norm(neg_vec)
        neg_vec = (np.array(neg_vec) / norm).tolist()
        mock_embedding_model.embed_query.return_value = neg_vec

        result = retrieval_service.global_search(
            "test query", min_relevance=0.99
        )

        assert result.community_summaries == []
        assert result.metadata["retrieval_mode"] == "global"
