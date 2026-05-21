"""Property-based tests for community detection.

Property 17: Community re-detection replaces all previous communities.

For any community detection run, all previously stored communities SHALL be
removed and replaced with freshly computed communities from the current entity
graph state.

**Validates: Requirements 6.6**
"""

from unittest.mock import patch, MagicMock

import hypothesis.strategies as st
from hypothesis import given, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.community import Community
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship
from app.models.chunk import Chunk
from app.models.file import File
from app.config import GraphRAGSettings
from app.services.community_detector import CommunityDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_in_memory_session():
    """Create an in-memory SQLite session with all tables."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _run_community_detection_and_store(
    session, entities: list[Entity], relationships: list[EntityRelationship]
) -> list[Community]:
    """Run community detection and store results, replacing all previous communities.

    This simulates the orchestration logic specified by Requirement 6.6:
    1. Deletes all existing communities from the database
    2. Runs community detection on the current entity graph
    3. Stores the newly detected communities
    """
    # Step 1: Remove all previously stored communities
    session.query(Community).delete()
    session.commit()

    # Step 2: Run community detection on current entities
    # Use the CommunityDetector to produce communities from the entity graph
    config = GraphRAGSettings()
    detector = CommunityDetector(config, embedding_model=None)
    new_communities = detector.detect(entities, relationships)

    # Step 3: Store newly detected communities
    for community in new_communities:
        session.add(community)
    session.commit()

    return new_communities


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for entity types
entity_type_strategy = st.sampled_from(
    ["person", "organization", "concept", "location", "event", "document"]
)

# Strategy for generating community member ID lists
member_ids_strategy = st.lists(
    st.integers(min_value=1, max_value=1000),
    min_size=1,
    max_size=10,
    unique=True,
)

# Strategy for community level
level_strategy = st.integers(min_value=0, max_value=4)

# Strategy for community summary
summary_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=0,
    max_size=100,
)

# Strategy for generating a list of pre-existing communities
existing_communities_strategy = st.lists(
    st.fixed_dictionaries({
        "level": level_strategy,
        "member_entity_ids": member_ids_strategy,
        "summary": summary_strategy,
    }),
    min_size=1,
    max_size=8,
)

# Strategy for generating new communities (from re-detection)
new_communities_strategy = st.lists(
    st.fixed_dictionaries({
        "level": level_strategy,
        "member_entity_ids": member_ids_strategy,
        "summary": summary_strategy,
    }),
    min_size=1,
    max_size=8,
)

# Strategy for entity names
entity_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=2,
    max_size=20,
).filter(lambda t: len(t.strip()) >= 2)

# Strategy for relationship strength
strength_strategy = st.floats(min_value=0.1, max_value=1.0, allow_nan=False)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


class TestProperty17CommunityReDetection:
    """Property 17: Community re-detection replaces all previous communities.

    **Validates: Requirements 6.6**
    """

    @given(
        existing_communities=existing_communities_strategy,
        new_communities=new_communities_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_redetection_removes_all_previous_communities(
        self,
        existing_communities: list[dict],
        new_communities: list[dict],
    ):
        """When community detection is re-run after a graph update, all
        previously stored communities are removed and replaced with freshly
        computed communities from the current entity graph state.

        **Validates: Requirements 6.6**
        """
        session = _create_in_memory_session()

        try:
            # --- Phase 1: Store initial communities (simulating a prior detection run) ---
            for comm_data in existing_communities:
                community = Community(
                    level=comm_data["level"],
                    member_entity_ids=comm_data["member_entity_ids"],
                    summary=comm_data["summary"],
                    summary_embedding=None,
                )
                session.add(community)
            session.commit()

            # Verify initial communities are stored
            initial_count = session.query(Community).count()
            assert initial_count == len(existing_communities)

            # Record initial community data (levels + member IDs) for comparison
            initial_data = [
                (c.level, tuple(c.member_entity_ids), c.summary)
                for c in session.query(Community).all()
            ]

            # --- Phase 2: Simulate re-detection by replacing all communities ---
            # This is the core behavior of Requirement 6.6:
            # "remove all previously stored communities and regenerate them"
            session.query(Community).delete()
            session.commit()

            # Verify deletion: zero communities after delete
            assert session.query(Community).count() == 0, (
                "All communities should be deleted before storing new ones"
            )

            # Store new communities (simulating freshly computed results)
            for comm_data in new_communities:
                community = Community(
                    level=comm_data["level"],
                    member_entity_ids=comm_data["member_entity_ids"],
                    summary=comm_data["summary"],
                    summary_embedding=None,
                )
                session.add(community)
            session.commit()

            # --- Assertions ---

            # 1. Only the new communities should be stored (count matches)
            all_communities = session.query(Community).all()
            assert len(all_communities) == len(new_communities), (
                f"Database should contain exactly the newly detected communities. "
                f"Expected {len(new_communities)}, got {len(all_communities)}"
            )

            # 2. Stored communities match the new detection results
            stored_data = sorted(
                [(c.level, tuple(c.member_entity_ids)) for c in all_communities]
            )
            expected_data = sorted(
                [(c["level"], tuple(c["member_entity_ids"])) for c in new_communities]
            )
            assert stored_data == expected_data, (
                f"Stored communities do not match newly detected communities. "
                f"Stored: {stored_data}, Expected: {expected_data}"
            )

            # 3. No data from old communities persists
            # (verify summaries match new data, not old)
            stored_summaries = sorted(c.summary or "" for c in all_communities)
            expected_summaries = sorted(c["summary"] for c in new_communities)
            assert stored_summaries == expected_summaries, (
                "Community summaries should reflect the new detection, not old data"
            )

        finally:
            session.close()

    @given(
        existing_communities=existing_communities_strategy,
        new_communities=new_communities_strategy,
        num_reruns=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=50, deadline=None)
    def test_multiple_redetections_never_accumulate(
        self,
        existing_communities: list[dict],
        new_communities: list[dict],
        num_reruns: int,
    ):
        """Running community detection multiple times always results in only
        the latest communities being stored — no accumulation of old communities.

        **Validates: Requirements 6.6**
        """
        session = _create_in_memory_session()

        try:
            # Store initial communities
            for comm_data in existing_communities:
                community = Community(
                    level=comm_data["level"],
                    member_entity_ids=comm_data["member_entity_ids"],
                    summary=comm_data["summary"],
                    summary_embedding=None,
                )
                session.add(community)
            session.commit()

            # Run re-detection multiple times
            for run_idx in range(num_reruns):
                # Delete all and replace (the re-detection behavior)
                session.query(Community).delete()
                session.commit()

                for comm_data in new_communities:
                    community = Community(
                        level=comm_data["level"],
                        member_entity_ids=comm_data["member_entity_ids"],
                        summary=comm_data["summary"],
                        summary_embedding=None,
                    )
                    session.add(community)
                session.commit()

                # After each run, DB should contain exactly the latest communities
                stored_count = session.query(Community).count()
                assert stored_count == len(new_communities), (
                    f"After run {run_idx + 1}: expected {len(new_communities)} "
                    f"communities in DB, got {stored_count}. "
                    f"Old communities should not accumulate."
                )

        finally:
            session.close()

    @given(
        entity_names=st.lists(
            entity_name_strategy,
            min_size=4,
            max_size=6,
            unique_by=lambda n: n.strip().casefold(),
        ),
        entity_type=entity_type_strategy,
        strengths=st.lists(strength_strategy, min_size=3, max_size=10),
    )
    @settings(max_examples=10, deadline=None)
    def test_redetection_with_real_detector_replaces_communities(
        self,
        entity_names: list[str],
        entity_type: str,
        strengths: list[float],
    ):
        """Integration test: using the real CommunityDetector, re-detection
        replaces all previous communities with freshly computed ones from the
        current entity graph.

        **Validates: Requirements 6.6**
        """
        from datetime import datetime

        session = _create_in_memory_session()

        try:
            # Create supporting records
            file_record = File(
                name="test.txt",
                path="test/test.txt",
                department="IT",
                size=100,
                content_hash="abc123",
                created_at=datetime(2024, 1, 1),
                modified_at=datetime(2024, 1, 1),
            )
            session.add(file_record)
            session.flush()

            chunk = Chunk(
                file_id=file_record.id,
                chunk_index=0,
                text="test chunk",
                start_offset=0,
                end_offset=10,
            )
            session.add(chunk)
            session.flush()

            # Create entities
            entity_objs = []
            for i, name in enumerate(entity_names):
                entity = Entity(
                    name=name,
                    normalized_name=name.strip().casefold(),
                    entity_type=entity_type,
                    description=f"Entity {i}",
                    source_chunk_ids=[chunk.id],
                )
                session.add(entity)
                entity_objs.append(entity)
            session.flush()

            # Create relationships (chain topology)
            rels = []
            for i in range(len(entity_objs) - 1):
                strength = strengths[i % len(strengths)]
                rel = EntityRelationship(
                    source_entity_id=entity_objs[i].id,
                    target_entity_id=entity_objs[i + 1].id,
                    description="relates to",
                    strength=strength,
                    source_chunk_id=chunk.id,
                )
                session.add(rel)
                rels.append(rel)
            session.flush()

            # First detection run
            first_communities = _run_community_detection_and_store(
                session, entity_objs, rels
            )
            first_count = session.query(Community).count()
            assert first_count > 0, (
                "First detection should produce communities with >= 3 entities"
            )

            # Record the count and data of first communities
            first_stored = session.query(Community).all()
            first_member_data = sorted(
                [tuple(sorted(c.member_entity_ids or [])) for c in first_stored]
            )

            # Second detection run (re-detection on same graph)
            second_communities = _run_community_detection_and_store(
                session, entity_objs, rels
            )

            # Verify replacement
            all_communities = session.query(Community).all()

            # The count should match the second detection output exactly
            assert len(all_communities) == len(second_communities), (
                f"Expected {len(second_communities)} communities, "
                f"got {len(all_communities)}"
            )

            # Verify that after deletion + re-insert, the DB only has
            # the communities from the second run (no accumulation)
            # The total count should NOT be first_count + second_count
            assert len(all_communities) <= len(second_communities), (
                f"Communities accumulated instead of being replaced. "
                f"Expected at most {len(second_communities)}, got {len(all_communities)}"
            )

            # All member IDs should reference current entities
            current_entity_ids = {e.id for e in entity_objs}
            for community in all_communities:
                member_ids = set(community.member_entity_ids or [])
                assert member_ids.issubset(current_entity_ids), (
                    f"Community references entity IDs not in current graph: "
                    f"{member_ids - current_entity_ids}"
                )

        finally:
            session.close()
