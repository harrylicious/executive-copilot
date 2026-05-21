"""Property-based tests for global search relevance scores.

Property 20: Global search relevance scores are valid cosine similarities

For any global search result, the relevance score SHALL be the cosine similarity
between the query embedding and the community summary embedding, and SHALL be in
the range [0.0, 1.0].

**Validates: Requirements 8.4**
"""

from datetime import datetime
from unittest.mock import patch

import hypothesis.strategies as st
import numpy as np
import pytest
from hypothesis import given, settings, assume, HealthCheck
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.community import Community
from app.models.entity import Entity
from app.models.file import File
from app.services.retrieval_service import RetrievalService


# --- Strategies ---

# Use integer seeds to generate normalized embeddings deterministically.
# This avoids Hypothesis health check issues with large 384-dim float lists.
embedding_seed_st = st.integers(min_value=0, max_value=2**32 - 1)

# Strategy for number of communities (1-5 for reasonable test speed)
num_communities_st = st.integers(min_value=1, max_value=5)

# Strategy for min_relevance threshold
min_relevance_st = st.floats(min_value=0.0, max_value=0.3, allow_nan=False)

# Strategy for num_communities parameter to global_search
num_communities_param_st = st.integers(min_value=1, max_value=20)


def _make_normalized_embedding(seed: int, dim: int = 384) -> list[float]:
    """Generate a normalized (unit-length) embedding vector from a seed."""
    rng = np.random.default_rng(seed)
    vec = rng.standard_normal(dim)
    norm = np.linalg.norm(vec)
    if norm < 1e-10:
        vec = np.ones(dim)
        norm = np.linalg.norm(vec)
    return (vec / norm).tolist()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors, clamped to [0.0, 1.0].

    This is the reference implementation used to verify the service's computation.
    """
    a = np.array(vec_a, dtype=np.float64)
    b = np.array(vec_b, dtype=np.float64)

    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    similarity = float(dot_product / (norm_a * norm_b))
    return max(0.0, min(1.0, similarity))


def _setup_db_with_communities(
    session, community_embeddings: list[list[float]]
) -> None:
    """Seed the database with communities and their supporting entities/files."""
    for i, emb in enumerate(community_embeddings):
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
            text=f"Sample text {i}",
            start_offset=0,
            end_offset=13,
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

        community = Community(
            id=400 + i,
            level=0,
            member_entity_ids=[300 + i],
            summary=f"Community summary about topic {i}",
            summary_embedding=emb,
        )
        session.add(community)

    session.commit()


def _create_service_with_mocked_deps(session, query_embedding: list[float]):
    """Create a RetrievalService with mocked embedding model and vector store."""
    config = GraphRAGSettings(vector_store_path="./test_chroma_prop20")

    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel, patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ), patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ):
        mock_model_instance = MockModel.return_value
        mock_model_instance.embed_query.return_value = query_embedding
        mock_model_instance.dimension = 384

        service = RetrievalService(db=session, config=config)
        service.model = mock_model_instance

    return service


# --- Property Tests ---


class TestProperty20GlobalSearchRelevanceScores:
    """Property 20: Global search relevance scores are valid cosine similarities.

    **Validates: Requirements 8.4**
    """

    @given(
        query_seed=embedding_seed_st,
        community_seeds=st.lists(
            embedding_seed_st,
            min_size=1,
            max_size=5,
        ),
        min_relevance=st.floats(min_value=0.0, max_value=0.3, allow_nan=False),
        num_communities_param=num_communities_param_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_relevance_scores_are_cosine_similarities(
        self,
        query_seed: int,
        community_seeds: list[int],
        min_relevance: float,
        num_communities_param: int,
    ):
        """For any global search result, the relevance score SHALL be the cosine
        similarity between the query embedding and the community summary embedding.

        **Validates: Requirements 8.4**
        """
        # Generate embeddings from seeds
        query_embedding = _make_normalized_embedding(query_seed)
        community_embeddings = [
            _make_normalized_embedding(s) for s in community_seeds
        ]

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db_with_communities(session, community_embeddings)
            service = _create_service_with_mocked_deps(session, query_embedding)

            # Execute global search
            result = service.global_search(
                query="test query",
                num_communities=num_communities_param,
                min_relevance=min_relevance,
            )

            # Verify: each returned relevance score matches the expected cosine similarity
            for community_result in result.community_summaries:
                score = community_result["relevance_score"]

                # Find the matching community embedding
                community_id = community_result["community_id"]
                idx = community_id - 400
                expected_embedding = community_embeddings[idx]

                # Compute expected cosine similarity
                expected_score = cosine_similarity(query_embedding, expected_embedding)

                # The service rounds to 6 decimal places
                assert abs(score - round(expected_score, 6)) < 1e-5, (
                    f"Relevance score mismatch for community {community_id}: "
                    f"got {score}, expected {round(expected_score, 6)} "
                    f"(raw cosine: {expected_score})"
                )

        finally:
            session.close()

    @given(
        query_seed=embedding_seed_st,
        community_seeds=st.lists(
            embedding_seed_st,
            min_size=1,
            max_size=5,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_relevance_scores_in_valid_range(
        self,
        query_seed: int,
        community_seeds: list[int],
    ):
        """For any global search result, the relevance score SHALL be in the
        range [0.0, 1.0].

        **Validates: Requirements 8.4**
        """
        # Generate embeddings from seeds
        query_embedding = _make_normalized_embedding(query_seed)
        community_embeddings = [
            _make_normalized_embedding(s) for s in community_seeds
        ]

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db_with_communities(session, community_embeddings)
            service = _create_service_with_mocked_deps(session, query_embedding)

            # Execute global search with min_relevance=0.0 to get all results
            result = service.global_search(
                query="test query",
                num_communities=20,
                min_relevance=0.0,
            )

            # Verify: all relevance scores are in [0.0, 1.0]
            for community_result in result.community_summaries:
                score = community_result["relevance_score"]
                assert 0.0 <= score <= 1.0, (
                    f"Relevance score {score} is outside valid range [0.0, 1.0] "
                    f"for community {community_result['community_id']}"
                )

        finally:
            session.close()

    @given(
        query_seed=embedding_seed_st,
        community_seeds=st.lists(
            embedding_seed_st,
            min_size=2,
            max_size=5,
        ),
    )
    @settings(max_examples=50, deadline=None)
    def test_relevance_scores_match_cosine_similarity_ordering(
        self,
        query_seed: int,
        community_seeds: list[int],
    ):
        """The ordering of relevance scores SHALL match the ordering of cosine
        similarities between the query and community summary embeddings.

        **Validates: Requirements 8.4**
        """
        # Generate embeddings from seeds
        query_embedding = _make_normalized_embedding(query_seed)
        community_embeddings = [
            _make_normalized_embedding(s) for s in community_seeds
        ]

        # Set up in-memory database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        try:
            _setup_db_with_communities(session, community_embeddings)
            service = _create_service_with_mocked_deps(session, query_embedding)

            # Execute global search with min_relevance=0.0 to get all results
            result = service.global_search(
                query="test query",
                num_communities=20,
                min_relevance=0.0,
            )

            # Verify: results are in descending order of relevance score
            if len(result.community_summaries) > 1:
                scores = [c["relevance_score"] for c in result.community_summaries]
                for i in range(len(scores) - 1):
                    assert scores[i] >= scores[i + 1], (
                        f"Results not in descending order: "
                        f"score[{i}]={scores[i]} < score[{i+1}]={scores[i+1]}. "
                        f"All scores: {scores}"
                    )

        finally:
            session.close()
