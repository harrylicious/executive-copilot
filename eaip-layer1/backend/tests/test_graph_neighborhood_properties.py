"""Property-based tests for graph neighborhood enrichment.

Property 19: Graph neighborhood enrichment includes exactly 1-hop neighbors

For any retrieved chunk, the enriched graph neighborhood SHALL include all entities
directly referenced by that chunk and all entities connected to those entities by
exactly one relationship edge, but SHALL NOT include entities requiring 2+ hops.

**Validates: Requirements 7.3**
"""

from datetime import datetime

import hypothesis.strategies as st
from hypothesis import given, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship
from app.models.file import File
from app.services.graphrag_engine import GraphRAGEngine


# --- Strategies ---

# Strategy for number of seed entities (directly referenced by the chunk)
num_seed_entities_st = st.integers(min_value=1, max_value=5)

# Strategy for number of 1-hop neighbor entities (connected by one edge)
num_one_hop_entities_st = st.integers(min_value=0, max_value=5)

# Strategy for number of 2-hop entities (should NOT appear in results)
num_two_hop_entities_st = st.integers(min_value=1, max_value=4)

# Strategy for relationship strength
strength_st = st.floats(min_value=0.1, max_value=1.0, allow_nan=False)


# --- Helpers ---


def _create_test_db():
    """Create a fresh in-memory SQLite database with all tables."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


def _create_file(session) -> File:
    """Create a test file record."""
    now = datetime.utcnow()
    f = File(
        name="test_file.txt",
        path="dept/test_file.txt",
        department="TestDept",
        size=1000,
        content_hash="hash_test",
        created_at=now,
        modified_at=now,
    )
    session.add(f)
    session.flush()
    return f


def _create_chunk(session, file_id: int, chunk_index: int = 0) -> Chunk:
    """Create a test chunk record."""
    chunk = Chunk(
        file_id=file_id,
        chunk_index=chunk_index,
        text=f"Test chunk text {chunk_index}",
        start_offset=0,
        end_offset=100,
    )
    session.add(chunk)
    session.flush()
    return chunk


def _create_entity(
    session, name: str, entity_type: str, source_chunk_ids: list[int]
) -> Entity:
    """Create a test entity record."""
    entity = Entity(
        name=name,
        normalized_name=name.casefold().strip(),
        entity_type=entity_type,
        description=f"Description for {name}",
        source_chunk_ids=source_chunk_ids,
    )
    session.add(entity)
    session.flush()
    return entity


def _create_relationship(
    session,
    source_entity_id: int,
    target_entity_id: int,
    source_chunk_id: int,
    strength: float = 0.5,
) -> EntityRelationship:
    """Create a test entity relationship record."""
    rel = EntityRelationship(
        source_entity_id=source_entity_id,
        target_entity_id=target_entity_id,
        description=f"Relationship {source_entity_id} -> {target_entity_id}",
        strength=strength,
        source_chunk_id=source_chunk_id,
    )
    session.add(rel)
    session.flush()
    return rel


# --- Property Tests ---


class TestProperty19GraphNeighborhoodEnrichment:
    """Property 19: Graph neighborhood enrichment includes exactly 1-hop neighbors.

    **Validates: Requirements 7.3**
    """

    @given(
        num_seed=num_seed_entities_st,
        num_one_hop=num_one_hop_entities_st,
        num_two_hop=num_two_hop_entities_st,
        strength=strength_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_neighborhood_includes_seed_entities_and_one_hop_neighbors(
        self,
        num_seed: int,
        num_one_hop: int,
        num_two_hop: int,
        strength: float,
    ):
        """The enriched graph neighborhood SHALL include all entities directly
        referenced by the chunk (seed entities) and all entities connected to
        those seed entities by exactly one relationship edge (1-hop neighbors).

        **Validates: Requirements 7.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create file and target chunk
            file = _create_file(session)
            target_chunk = _create_chunk(session, file.id, chunk_index=0)
            # Create an auxiliary chunk for relationships not tied to target
            aux_chunk = _create_chunk(session, file.id, chunk_index=1)
            session.commit()

            # Create seed entities (directly reference the target chunk)
            seed_entities = []
            for i in range(num_seed):
                entity = _create_entity(
                    session,
                    name=f"Seed_Entity_{i}",
                    entity_type="concept",
                    source_chunk_ids=[target_chunk.id],
                )
                seed_entities.append(entity)
            session.commit()

            # Create 1-hop neighbor entities (NOT directly referencing target chunk)
            one_hop_entities = []
            for i in range(num_one_hop):
                entity = _create_entity(
                    session,
                    name=f"OneHop_Entity_{i}",
                    entity_type="person",
                    source_chunk_ids=[aux_chunk.id],
                )
                one_hop_entities.append(entity)
            session.commit()

            # Create 2-hop entities (connected to 1-hop entities, not to seeds)
            two_hop_entities = []
            for i in range(num_two_hop):
                entity = _create_entity(
                    session,
                    name=f"TwoHop_Entity_{i}",
                    entity_type="location",
                    source_chunk_ids=[aux_chunk.id],
                )
                two_hop_entities.append(entity)
            session.commit()

            # Create relationships: seed -> 1-hop (one edge from seed entities)
            for i, one_hop_entity in enumerate(one_hop_entities):
                seed_idx = i % num_seed
                _create_relationship(
                    session,
                    source_entity_id=seed_entities[seed_idx].id,
                    target_entity_id=one_hop_entity.id,
                    source_chunk_id=target_chunk.id,
                    strength=strength,
                )

            # Create relationships: 1-hop -> 2-hop (second edge, requires 2 hops)
            if one_hop_entities:
                for i, two_hop_entity in enumerate(two_hop_entities):
                    one_hop_idx = i % len(one_hop_entities)
                    _create_relationship(
                        session,
                        source_entity_id=one_hop_entities[one_hop_idx].id,
                        target_entity_id=two_hop_entity.id,
                        source_chunk_id=aux_chunk.id,
                        strength=strength,
                    )
            session.commit()

            # Act: get graph neighborhood with hops=1
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(db=session, config=config)
            neighborhood = graphrag.get_graph_neighborhood(
                chunk_id=target_chunk.id, hops=1
            )

            # Collect returned entity IDs
            returned_entity_ids = {e["id"] for e in neighborhood["entities"]}

            # Assert: ALL seed entities are included
            seed_entity_ids = {e.id for e in seed_entities}
            for seed_id in seed_entity_ids:
                assert seed_id in returned_entity_ids, (
                    f"Seed entity {seed_id} directly referenced by chunk "
                    f"is missing from neighborhood. "
                    f"Returned: {returned_entity_ids}, Expected seeds: {seed_entity_ids}"
                )

            # Assert: ALL 1-hop neighbor entities are included
            one_hop_entity_ids = {e.id for e in one_hop_entities}
            for one_hop_id in one_hop_entity_ids:
                assert one_hop_id in returned_entity_ids, (
                    f"1-hop neighbor entity {one_hop_id} connected by one edge "
                    f"is missing from neighborhood. "
                    f"Returned: {returned_entity_ids}, "
                    f"Expected 1-hop: {one_hop_entity_ids}"
                )

            # Assert: NO 2-hop entities are included
            two_hop_entity_ids = {e.id for e in two_hop_entities}
            for two_hop_id in two_hop_entity_ids:
                assert two_hop_id not in returned_entity_ids, (
                    f"2-hop entity {two_hop_id} requiring 2+ hops "
                    f"should NOT be in 1-hop neighborhood. "
                    f"Returned: {returned_entity_ids}, "
                    f"2-hop entities: {two_hop_entity_ids}"
                )

        finally:
            session.close()
            engine.dispose()

    @given(
        num_seed=num_seed_entities_st,
        num_one_hop=st.integers(min_value=1, max_value=4),
        strength=strength_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_neighborhood_includes_relationships_connecting_seed_to_one_hop(
        self,
        num_seed: int,
        num_one_hop: int,
        strength: float,
    ):
        """The enriched graph neighborhood SHALL include all relationships
        that connect seed entities to their 1-hop neighbors.

        **Validates: Requirements 7.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup
            file = _create_file(session)
            target_chunk = _create_chunk(session, file.id, chunk_index=0)
            aux_chunk = _create_chunk(session, file.id, chunk_index=1)
            session.commit()

            # Create seed entities
            seed_entities = []
            for i in range(num_seed):
                entity = _create_entity(
                    session,
                    name=f"Seed_{i}",
                    entity_type="concept",
                    source_chunk_ids=[target_chunk.id],
                )
                seed_entities.append(entity)
            session.commit()

            # Create 1-hop entities
            one_hop_entities = []
            for i in range(num_one_hop):
                entity = _create_entity(
                    session,
                    name=f"Neighbor_{i}",
                    entity_type="organization",
                    source_chunk_ids=[aux_chunk.id],
                )
                one_hop_entities.append(entity)
            session.commit()

            # Create relationships between seeds and 1-hop neighbors
            created_rel_ids = set()
            for i, one_hop_entity in enumerate(one_hop_entities):
                seed_idx = i % num_seed
                rel = _create_relationship(
                    session,
                    source_entity_id=seed_entities[seed_idx].id,
                    target_entity_id=one_hop_entity.id,
                    source_chunk_id=target_chunk.id,
                    strength=strength,
                )
                created_rel_ids.add(rel.id)
            session.commit()

            # Act
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(db=session, config=config)
            neighborhood = graphrag.get_graph_neighborhood(
                chunk_id=target_chunk.id, hops=1
            )

            # Assert: all relationships connecting seeds to 1-hop are included
            returned_rel_ids = {r["id"] for r in neighborhood["relationships"]}
            for rel_id in created_rel_ids:
                assert rel_id in returned_rel_ids, (
                    f"Relationship {rel_id} connecting seed to 1-hop neighbor "
                    f"is missing from neighborhood relationships. "
                    f"Returned: {returned_rel_ids}, Expected: {created_rel_ids}"
                )

        finally:
            session.close()
            engine.dispose()

    @given(
        num_seed=num_seed_entities_st,
        num_two_hop=num_two_hop_entities_st,
        strength=strength_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_neighborhood_excludes_entities_requiring_two_or_more_hops(
        self,
        num_seed: int,
        num_two_hop: int,
        strength: float,
    ):
        """The enriched graph neighborhood SHALL NOT include entities requiring
        2+ hops from the seed entities.

        This test creates a chain: seed -> hop1 -> hop2 -> hop3
        and verifies that only seed and hop1 entities appear in the 1-hop
        neighborhood.

        **Validates: Requirements 7.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup
            file = _create_file(session)
            target_chunk = _create_chunk(session, file.id, chunk_index=0)
            aux_chunk = _create_chunk(session, file.id, chunk_index=1)
            session.commit()

            # Create a chain of entities: seed -> hop1 -> hop2 -> ... -> hopN
            # Only seed references the target chunk
            seed = _create_entity(
                session,
                name="Chain_Seed",
                entity_type="concept",
                source_chunk_ids=[target_chunk.id],
            )
            session.commit()

            # Create hop1 entity (1 hop from seed)
            hop1 = _create_entity(
                session,
                name="Chain_Hop1",
                entity_type="person",
                source_chunk_ids=[aux_chunk.id],
            )
            session.commit()

            # Create relationship: seed -> hop1
            _create_relationship(
                session,
                source_entity_id=seed.id,
                target_entity_id=hop1.id,
                source_chunk_id=target_chunk.id,
                strength=strength,
            )
            session.commit()

            # Create multiple 2+ hop entities in a chain from hop1
            far_entities = []
            prev_entity = hop1
            for i in range(num_two_hop):
                far_entity = _create_entity(
                    session,
                    name=f"Chain_Hop{i + 2}",
                    entity_type="location",
                    source_chunk_ids=[aux_chunk.id],
                )
                far_entities.append(far_entity)
                session.commit()

                # Link previous -> current (extends the chain)
                _create_relationship(
                    session,
                    source_entity_id=prev_entity.id,
                    target_entity_id=far_entity.id,
                    source_chunk_id=aux_chunk.id,
                    strength=strength,
                )
                session.commit()
                prev_entity = far_entity

            # Act
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(db=session, config=config)
            neighborhood = graphrag.get_graph_neighborhood(
                chunk_id=target_chunk.id, hops=1
            )

            returned_entity_ids = {e["id"] for e in neighborhood["entities"]}

            # Assert: seed and hop1 are included
            assert seed.id in returned_entity_ids, (
                f"Seed entity {seed.id} missing from neighborhood"
            )
            assert hop1.id in returned_entity_ids, (
                f"1-hop entity {hop1.id} missing from neighborhood"
            )

            # Assert: all 2+ hop entities are excluded
            for far_entity in far_entities:
                assert far_entity.id not in returned_entity_ids, (
                    f"Entity {far_entity.id} ('{far_entity.name}') requiring "
                    f"2+ hops should NOT be in 1-hop neighborhood. "
                    f"Returned entity IDs: {returned_entity_ids}"
                )

        finally:
            session.close()
            engine.dispose()

    @given(
        num_seed=num_seed_entities_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_neighborhood_with_no_relationships_returns_only_seed_entities(
        self,
        num_seed: int,
    ):
        """When seed entities have no relationships, the neighborhood SHALL
        contain only the seed entities and no relationships.

        **Validates: Requirements 7.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup
            file = _create_file(session)
            target_chunk = _create_chunk(session, file.id, chunk_index=0)
            session.commit()

            # Create seed entities with no relationships
            seed_entities = []
            for i in range(num_seed):
                entity = _create_entity(
                    session,
                    name=f"Isolated_Entity_{i}",
                    entity_type="concept",
                    source_chunk_ids=[target_chunk.id],
                )
                seed_entities.append(entity)
            session.commit()

            # Act
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(db=session, config=config)
            neighborhood = graphrag.get_graph_neighborhood(
                chunk_id=target_chunk.id, hops=1
            )

            returned_entity_ids = {e["id"] for e in neighborhood["entities"]}
            seed_entity_ids = {e.id for e in seed_entities}

            # Assert: only seed entities are returned
            assert returned_entity_ids == seed_entity_ids, (
                f"Expected only seed entities {seed_entity_ids}, "
                f"got {returned_entity_ids}"
            )

            # Assert: no relationships returned
            assert len(neighborhood["relationships"]) == 0, (
                f"Expected 0 relationships for isolated entities, "
                f"got {len(neighborhood['relationships'])}"
            )

        finally:
            session.close()
            engine.dispose()

    @given(
        num_seed=num_seed_entities_st,
        num_one_hop=st.integers(min_value=1, max_value=4),
        num_two_hop=num_two_hop_entities_st,
        strength=strength_st,
    )
    @settings(max_examples=50, deadline=None)
    def test_neighborhood_boundary_is_exactly_one_hop(
        self,
        num_seed: int,
        num_one_hop: int,
        num_two_hop: int,
        strength: float,
    ):
        """The neighborhood boundary is exactly 1 hop: the returned entity set
        SHALL equal the union of seed entities and their direct neighbors,
        and SHALL NOT contain any entity that is only reachable via 2+ edges.

        **Validates: Requirements 7.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup
            file = _create_file(session)
            target_chunk = _create_chunk(session, file.id, chunk_index=0)
            aux_chunk = _create_chunk(session, file.id, chunk_index=1)
            session.commit()

            # Create seed entities
            seed_entities = []
            for i in range(num_seed):
                entity = _create_entity(
                    session,
                    name=f"Seed_{i}",
                    entity_type="concept",
                    source_chunk_ids=[target_chunk.id],
                )
                seed_entities.append(entity)
            session.commit()

            # Create 1-hop entities
            one_hop_entities = []
            for i in range(num_one_hop):
                entity = _create_entity(
                    session,
                    name=f"OneHop_{i}",
                    entity_type="person",
                    source_chunk_ids=[aux_chunk.id],
                )
                one_hop_entities.append(entity)
            session.commit()

            # Create 2-hop entities (only reachable from 1-hop, not from seeds)
            two_hop_entities = []
            for i in range(num_two_hop):
                entity = _create_entity(
                    session,
                    name=f"TwoHop_{i}",
                    entity_type="location",
                    source_chunk_ids=[aux_chunk.id],
                )
                two_hop_entities.append(entity)
            session.commit()

            # Relationships: seed -> 1-hop
            for i, one_hop_entity in enumerate(one_hop_entities):
                seed_idx = i % num_seed
                _create_relationship(
                    session,
                    source_entity_id=seed_entities[seed_idx].id,
                    target_entity_id=one_hop_entity.id,
                    source_chunk_id=target_chunk.id,
                    strength=strength,
                )

            # Relationships: 1-hop -> 2-hop (second edge)
            for i, two_hop_entity in enumerate(two_hop_entities):
                one_hop_idx = i % num_one_hop
                _create_relationship(
                    session,
                    source_entity_id=one_hop_entities[one_hop_idx].id,
                    target_entity_id=two_hop_entity.id,
                    source_chunk_id=aux_chunk.id,
                    strength=strength,
                )
            session.commit()

            # Act
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(db=session, config=config)
            neighborhood = graphrag.get_graph_neighborhood(
                chunk_id=target_chunk.id, hops=1
            )

            returned_entity_ids = {e["id"] for e in neighborhood["entities"]}

            # Expected: exactly seeds + 1-hop neighbors
            expected_entity_ids = (
                {e.id for e in seed_entities} | {e.id for e in one_hop_entities}
            )

            assert returned_entity_ids == expected_entity_ids, (
                f"Neighborhood boundary mismatch.\n"
                f"Expected (seeds + 1-hop): {expected_entity_ids}\n"
                f"Got: {returned_entity_ids}\n"
                f"Missing: {expected_entity_ids - returned_entity_ids}\n"
                f"Extra (2-hop leaked): {returned_entity_ids - expected_entity_ids}"
            )

        finally:
            session.close()
            engine.dispose()
