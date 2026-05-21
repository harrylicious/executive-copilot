"""Property-based tests for retrieval response structure.

Property 22: Retrieval response contains all required structural fields

For any search response (local, global, or combined), the JSON SHALL contain
the top-level fields: chunks, entities, relationships, community_summaries,
source_attributions, and metadata (with query_time_ms, total_chunks_searched,
and retrieval_mode).

**Validates: Requirements 9.1, 9.4**
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import hypothesis.strategies as st
import numpy as np
from hypothesis import given, settings, assume

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.community import Community
from app.models.entity import Entity
from app.models.file import File
from app.services.retrieval_service import RetrievalService, SearchResult


# --- Required fields ---

REQUIRED_TOP_LEVEL_FIELDS = {
    "chunks",
    "entities",
    "relationships",
    "community_summaries",
    "source_attributions",
    "metadata",
}

REQUIRED_METADATA_FIELDS = {
    "query_time_ms",
    "total_chunks_searched",
    "retrieval_mode",
}

VALID_RETRIEVAL_MODES = {"local", "global", "combined"}


# --- Strategies ---

# Query text strategy: valid queries between 1 and 100 characters
query_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=1,
    max_size=100,
).filter(lambda s: s.strip())

# Strategy for top_k parameter
top_k_st = st.integers(min_value=1, max_value=10)

# Strategy for min_score threshold
min_score_st = st.floats(min_value=0.0, max_value=0.9, allow_nan=False)

# Strategy for similarity_weight
similarity_weight_st = st.floats(min_value=0.0, max_value=1.0, allow_nan=False)

# Strategy for num_communities parameter
num_communities_st = st.integers(min_value=1, max_value=10)

# Strategy for min_relevance threshold
min_relevance_st = st.floats(min_value=0.0, max_value=0.5, allow_nan=False)

# Strategy for max_tokens parameter
max_tokens_st = st.integers(min_value=1000, max_value=8000)

# Strategy for number of vector results to return (0 to 5)
num_vector_results_st = st.integers(min_value=0, max_value=5)

# Strategy for number of communities in the database (0 to 3)
num_db_communities_st = st.integers(min_value=0, max_value=3)

# Embedding seed strategy
embedding_seed_st = st.integers(min_value=0, max_value=2**32 - 1)


# --- Helpers ---


def _make_normalized_embedding(seed: int, dim: int = 384) -> list[float]:
    """Generate a normalized (unit-length) embedding vector from a seed."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-10:
        vec = np.ones(dim)
        norm = np.linalg.norm(vec)
    return (vec / norm).tolist()


def _setup_db(session, num_communities: int, num_files: int = 3):
    """Seed the database with files, chunks, entities, and communities."""
    for i in range(num_files):
        file = File(
            id=100 + i,
            name=f"doc_{i}.md",
            path=f"dept/doc_{i}.md",
            department="engineering",
            size=1000,
            tags=[],
            created_at=datetime(2024, 1, 1),
            modified_at=datetime(2024, 1, 1),
            content_hash=f"hash_{i}",
        )
        session.add(file)

        chunk = Chunk(
            id=200 + i,
            file_id=100 + i,
            chunk_index=0,
            text=f"Sample text for document {i} with some content.",
            start_offset=0,
            end_offset=40,
        )
        session.add(chunk)

        entity = Entity(
            id=300 + i,
            name=f"Entity_{i}",
            normalized_name=f"entity_{i}",
            entity_type="concept",
            description=f"Test entity {i}",
            source_chunk_ids=[200 + i],
        )
        session.add(entity)

    for i in range(num_communities):
        embedding = _make_normalized_embedding(seed=i + 50)
        community = Community(
            id=400 + i,
            level=0,
            member_entity_ids=[300 + (i % num_files)],
            summary=f"Community summary about topic {i}",
            summary_embedding=embedding,
        )
        session.add(community)

    session.commit()


def _create_service_for_local(
    session, query_embedding: list[float], vector_results: list[dict]
):
    """Create a RetrievalService with mocked deps for local search testing."""
    config = GraphRAGSettings(vector_store_path="./test_chroma_prop22")

    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel, patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ) as MockVectorStore, patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ) as MockGraphRAG:
        mock_model = MockModel.return_value
        mock_model.embed_query.return_value = query_embedding
        mock_model.dimension = 384

        mock_store = MockVectorStore.return_value
        mock_store.similarity_search.return_value = vector_results

        mock_graphrag = MockGraphRAG.return_value
        mock_graphrag.get_graph_neighborhood.return_value = {
            "entities": [],
            "relationships": [],
        }

        service = RetrievalService(db=session, config=config)
        service.model = mock_model
        service.vector_store = mock_store
        service.graphrag = mock_graphrag

    return service


def _create_service_for_global(session, query_embedding: list[float]):
    """Create a RetrievalService with mocked deps for global search testing."""
    config = GraphRAGSettings(vector_store_path="./test_chroma_prop22")

    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel, patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ), patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ):
        mock_model = MockModel.return_value
        mock_model.embed_query.return_value = query_embedding
        mock_model.dimension = 384

        service = RetrievalService(db=session, config=config)
        service.model = mock_model

    return service


def _create_service_for_combined(
    session, query_embedding: list[float], vector_results: list[dict]
):
    """Create a RetrievalService with mocked deps for combined search testing."""
    config = GraphRAGSettings(vector_store_path="./test_chroma_prop22")

    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel, patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ) as MockVectorStore, patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ) as MockGraphRAG:
        mock_model = MockModel.return_value
        mock_model.embed_query.return_value = query_embedding
        mock_model.dimension = 384

        mock_store = MockVectorStore.return_value
        mock_store.similarity_search.return_value = vector_results

        mock_graphrag = MockGraphRAG.return_value
        mock_graphrag.get_graph_neighborhood.return_value = {
            "entities": [],
            "relationships": [],
        }

        service = RetrievalService(db=session, config=config)
        service.model = mock_model
        service.vector_store = mock_store
        service.graphrag = mock_graphrag

    return service


def _assert_response_structure(result: SearchResult, expected_mode: str):
    """Assert that a SearchResult has all required structural fields."""
    # Check top-level fields exist and are lists (except metadata which is dict)
    assert isinstance(result.chunks, list), (
        f"chunks should be a list, got {type(result.chunks)}"
    )
    assert isinstance(result.entities, list), (
        f"entities should be a list, got {type(result.entities)}"
    )
    assert isinstance(result.relationships, list), (
        f"relationships should be a list, got {type(result.relationships)}"
    )
    assert isinstance(result.community_summaries, list), (
        f"community_summaries should be a list, got {type(result.community_summaries)}"
    )
    assert isinstance(result.source_attributions, list), (
        f"source_attributions should be a list, got {type(result.source_attributions)}"
    )
    assert isinstance(result.metadata, dict), (
        f"metadata should be a dict, got {type(result.metadata)}"
    )

    # Check required metadata fields
    for field in REQUIRED_METADATA_FIELDS:
        assert field in result.metadata, (
            f"metadata missing required field '{field}'. "
            f"Present fields: {list(result.metadata.keys())}"
        )

    # Check metadata field types
    assert isinstance(result.metadata["query_time_ms"], (int, float)), (
        f"query_time_ms should be numeric, got {type(result.metadata['query_time_ms'])}"
    )
    assert isinstance(result.metadata["total_chunks_searched"], int), (
        f"total_chunks_searched should be int, got "
        f"{type(result.metadata['total_chunks_searched'])}"
    )
    assert result.metadata["retrieval_mode"] in VALID_RETRIEVAL_MODES, (
        f"retrieval_mode should be one of {VALID_RETRIEVAL_MODES}, "
        f"got '{result.metadata['retrieval_mode']}'"
    )

    # Check the retrieval mode matches expected
    assert result.metadata["retrieval_mode"] == expected_mode, (
        f"Expected retrieval_mode '{expected_mode}', "
        f"got '{result.metadata['retrieval_mode']}'"
    )

    # Check query_time_ms is non-negative
    assert result.metadata["query_time_ms"] >= 0, (
        f"query_time_ms should be non-negative, got {result.metadata['query_time_ms']}"
    )

    # Check total_chunks_searched is non-negative
    assert result.metadata["total_chunks_searched"] >= 0, (
        f"total_chunks_searched should be non-negative, "
        f"got {result.metadata['total_chunks_searched']}"
    )


# --- Property Tests ---


class TestProperty22ResponseStructure:
    """Property 22: Retrieval response contains all required structural fields.

    **Validates: Requirements 9.1, 9.4**
    """

    @given(
        query=query_st,
        num_results=num_vector_results_st,
        top_k=top_k_st,
        min_score=min_score_st,
        similarity_weight=similarity_weight_st,
        embedding_seed=embedding_seed_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_local_search_response_has_required_fields(
        self,
        query: str,
        num_results: int,
        top_k: int,
        min_score: float,
        similarity_weight: float,
        embedding_seed: int,
    ):
        """For any local search response, the result SHALL contain all required
        top-level fields (chunks, entities, relationships, community_summaries,
        source_attributions, metadata) and metadata SHALL contain query_time_ms,
        total_chunks_searched, and retrieval_mode='local'.

        **Validates: Requirements 9.1, 9.4**
        """
        query_embedding = _make_normalized_embedding(embedding_seed)

        # Build mock vector results
        vector_results = [
            {
                "id": f"file_1_chunk_{i}",
                "text": f"Chunk text {i}",
                "file_id": 1,
                "chunk_index": i,
                "department": "engineering",
                "score": 0.8 - (i * 0.05),
            }
            for i in range(num_results)
        ]

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db(session, num_communities=0, num_files=3)
            service = _create_service_for_local(
                session, query_embedding, vector_results
            )

            result = service.local_search(
                query=query,
                top_k=top_k,
                min_score=min_score,
                similarity_weight=similarity_weight,
            )

            _assert_response_structure(result, expected_mode="local")

        finally:
            session.close()

    @given(
        query=query_st,
        num_communities=num_db_communities_st,
        num_communities_param=num_communities_st,
        min_relevance=min_relevance_st,
        embedding_seed=embedding_seed_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_global_search_response_has_required_fields(
        self,
        query: str,
        num_communities: int,
        num_communities_param: int,
        min_relevance: float,
        embedding_seed: int,
    ):
        """For any global search response, the result SHALL contain all required
        top-level fields (chunks, entities, relationships, community_summaries,
        source_attributions, metadata) and metadata SHALL contain query_time_ms,
        total_chunks_searched, and retrieval_mode='global'.

        **Validates: Requirements 9.1, 9.4**
        """
        query_embedding = _make_normalized_embedding(embedding_seed)

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db(session, num_communities=num_communities, num_files=3)
            service = _create_service_for_global(session, query_embedding)

            result = service.global_search(
                query=query,
                num_communities=num_communities_param,
                min_relevance=min_relevance,
            )

            _assert_response_structure(result, expected_mode="global")

        finally:
            session.close()

    @given(
        query=query_st,
        num_results=num_vector_results_st,
        num_communities=num_db_communities_st,
        max_tokens=max_tokens_st,
        top_k=top_k_st,
        num_communities_param=num_communities_st,
        min_score=min_score_st,
        min_relevance=min_relevance_st,
        similarity_weight=similarity_weight_st,
        embedding_seed=embedding_seed_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_combined_search_response_has_required_fields(
        self,
        query: str,
        num_results: int,
        num_communities: int,
        max_tokens: int,
        top_k: int,
        num_communities_param: int,
        min_score: float,
        min_relevance: float,
        similarity_weight: float,
        embedding_seed: int,
    ):
        """For any combined search response, the result SHALL contain all required
        top-level fields (chunks, entities, relationships, community_summaries,
        source_attributions, metadata) and metadata SHALL contain query_time_ms,
        total_chunks_searched, and retrieval_mode='combined'.

        **Validates: Requirements 9.1, 9.4**
        """
        query_embedding = _make_normalized_embedding(embedding_seed)

        # Build mock vector results
        vector_results = [
            {
                "id": f"file_1_chunk_{i}",
                "text": f"Chunk text {i}",
                "file_id": 1,
                "chunk_index": i,
                "department": "engineering",
                "score": 0.8 - (i * 0.05),
            }
            for i in range(num_results)
        ]

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db(session, num_communities=num_communities, num_files=3)
            service = _create_service_for_combined(
                session, query_embedding, vector_results
            )

            result = service.combined_search(
                query=query,
                max_tokens=max_tokens,
                top_k=top_k,
                num_communities=num_communities_param,
                min_score=min_score,
                min_relevance=min_relevance,
                similarity_weight=similarity_weight,
            )

            _assert_response_structure(result, expected_mode="combined")

        finally:
            session.close()

    @given(
        query=query_st,
        embedding_seed=embedding_seed_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_empty_results_still_have_required_structure(
        self,
        query: str,
        embedding_seed: int,
    ):
        """When no results are found, the response SHALL still contain all
        required structural fields with empty lists and valid metadata.

        **Validates: Requirements 9.1, 9.4**
        """
        query_embedding = _make_normalized_embedding(embedding_seed)

        # Set up in-memory database with no data
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            # Local search with no vector results
            service_local = _create_service_for_local(
                session, query_embedding, vector_results=[]
            )
            result_local = service_local.local_search(query=query)
            _assert_response_structure(result_local, expected_mode="local")
            assert result_local.chunks == []

            # Global search with no communities
            service_global = _create_service_for_global(session, query_embedding)
            result_global = service_global.global_search(query=query)
            _assert_response_structure(result_global, expected_mode="global")
            assert result_global.community_summaries == []

            # Combined search with no results
            service_combined = _create_service_for_combined(
                session, query_embedding, vector_results=[]
            )
            result_combined = service_combined.combined_search(query=query)
            _assert_response_structure(result_combined, expected_mode="combined")
            assert result_combined.chunks == []
            assert result_combined.community_summaries == []

        finally:
            session.close()
