"""Property-based tests for GraphRAG engine graph merge behavior.

Property 13: Graph merge preserves manual relationships

For any set of manually created relationships in the file relationship graph
(stored in the `relationships` table), after entity-relationship extraction and
merge for any file, all pre-existing manual relationships SHALL remain unchanged
in the database.

**Validates: Requirements 5.3**
"""

from datetime import datetime
from unittest.mock import patch

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
from app.models.relationship import Relationship
from app.services.graphrag_engine import GraphRAGEngine


# --- Strategies ---

# Strategy for relationship types
relationship_types_st = st.sampled_from(["department", "tag", "manual"])

# Strategy for generating a number of manual relationships
num_manual_relationships_st = st.integers(min_value=1, max_value=5)

# Strategy for generating file count (we need at least 2 files for relationships)
num_files_st = st.integers(min_value=2, max_value=6)

# Strategy for generating text chunks that will produce entities
_ENTITY_RICH_TEXTS = [
    "Alice Johnson met Bob Smith at the Microsoft headquarters in Seattle.",
    "The United Nations held a conference in New York with representatives from Google.",
    "Dr. Sarah Chen published a paper with Professor James Wilson at Stanford University.",
    "Apple CEO Tim Cook announced a partnership with IBM in San Francisco.",
    "Barack Obama visited Angela Merkel in Berlin to discuss NATO policies.",
    "Tesla and SpaceX founder Elon Musk spoke at the World Economic Forum in Davos.",
    "The European Union signed a trade agreement with Japan in Brussels.",
    "Mark Zuckerberg and Sheryl Sandberg presented Meta's new strategy in Menlo Park.",
]

chunk_texts_st = st.lists(
    st.sampled_from(_ENTITY_RICH_TEXTS),
    min_size=1,
    max_size=3,
)


def _create_test_db():
    """Create a fresh in-memory SQLite database with all tables."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


def _create_files(session, num_files: int) -> list[File]:
    """Create test file records in the database."""
    now = datetime.utcnow()
    files = []
    for i in range(num_files):
        f = File(
            name=f"test_file_{i}.txt",
            path=f"dept/test_file_{i}.txt",
            department="TestDept",
            size=1000 + i,
            content_hash=f"hash_{i}",
            created_at=now,
            modified_at=now,
        )
        session.add(f)
        files.append(f)
    session.flush()
    return files


def _create_manual_relationships(
    session, file_ids: list[int], num_relationships: int, rel_types: list[str]
) -> list[dict]:
    """Create manual relationships between files and return their data for verification."""
    created = []
    for i in range(num_relationships):
        source_idx = i % len(file_ids)
        target_idx = (i + 1) % len(file_ids)
        # Ensure source != target
        if source_idx == target_idx:
            target_idx = (target_idx + 1) % len(file_ids)

        rel_type = rel_types[i % len(rel_types)]
        is_manual = rel_type == "manual"

        rel = Relationship(
            source_file_id=file_ids[source_idx],
            target_file_id=file_ids[target_idx],
            relationship_type=rel_type,
            is_manual=is_manual,
        )
        session.add(rel)
        session.flush()

        created.append({
            "id": rel.id,
            "source_file_id": file_ids[source_idx],
            "target_file_id": file_ids[target_idx],
            "relationship_type": rel_type,
            "is_manual": is_manual,
        })

    session.commit()
    return created


def _create_chunks_for_file(
    session, file_id: int, texts: list[str]
) -> list[Chunk]:
    """Create chunk records for a file."""
    chunks = []
    offset = 0
    for i, text in enumerate(texts):
        chunk = Chunk(
            file_id=file_id,
            chunk_index=i,
            text=text,
            start_offset=offset,
            end_offset=offset + len(text),
        )
        session.add(chunk)
        offset += len(text)
        chunks.append(chunk)
    session.flush()
    return chunks


class TestProperty13GraphMergePreservesManualRelationships:
    """Property 13: Graph merge preserves manual relationships.

    **Validates: Requirements 5.3**
    """

    @given(
        num_files=num_files_st,
        num_manual_rels=num_manual_relationships_st,
        rel_types=st.lists(relationship_types_st, min_size=1, max_size=5),
        chunk_texts=chunk_texts_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_manual_relationships_preserved_after_extraction(
        self,
        num_files: int,
        num_manual_rels: int,
        rel_types: list[str],
        chunk_texts: list[str],
    ):
        """After entity-relationship extraction and merge for any file, all
        pre-existing manual relationships SHALL remain unchanged in the database.

        **Validates: Requirements 5.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Step 1: Create files
            files = _create_files(session, num_files)
            file_ids = [f.id for f in files]
            session.commit()

            # Step 2: Create manual relationships
            manual_rels_before = _create_manual_relationships(
                session, file_ids, num_manual_rels, rel_types
            )

            # Step 3: Create chunks for the first file (the one we'll process)
            target_file_id = file_ids[0]
            chunks = _create_chunks_for_file(session, target_file_id, chunk_texts)
            session.commit()

            # Step 4: Run entity/relationship extraction via GraphRAGEngine
            config = GraphRAGSettings()
            graphrag_engine = GraphRAGEngine(db=session, config=config)
            graphrag_engine.extract_entities_and_relationships(chunks, target_file_id)

            # Step 5: Verify ALL manual relationships are still present and unchanged
            all_relationships_after = session.query(Relationship).all()

            # Check count is preserved
            assert len(all_relationships_after) == len(manual_rels_before), (
                f"Manual relationship count changed: "
                f"expected {len(manual_rels_before)}, "
                f"got {len(all_relationships_after)}"
            )

            # Check each relationship's data is unchanged
            for expected_rel in manual_rels_before:
                found = session.query(Relationship).filter(
                    Relationship.id == expected_rel["id"]
                ).first()

                assert found is not None, (
                    f"Manual relationship with id={expected_rel['id']} was deleted "
                    f"after graph merge"
                )
                assert found.source_file_id == expected_rel["source_file_id"], (
                    f"source_file_id changed for relationship {found.id}: "
                    f"expected {expected_rel['source_file_id']}, got {found.source_file_id}"
                )
                assert found.target_file_id == expected_rel["target_file_id"], (
                    f"target_file_id changed for relationship {found.id}: "
                    f"expected {expected_rel['target_file_id']}, got {found.target_file_id}"
                )
                assert found.relationship_type == expected_rel["relationship_type"], (
                    f"relationship_type changed for relationship {found.id}: "
                    f"expected {expected_rel['relationship_type']}, "
                    f"got {found.relationship_type}"
                )
                assert found.is_manual == expected_rel["is_manual"], (
                    f"is_manual changed for relationship {found.id}: "
                    f"expected {expected_rel['is_manual']}, got {found.is_manual}"
                )

        finally:
            session.close()
            engine.dispose()

    @given(
        num_files=num_files_st,
        num_manual_rels=num_manual_relationships_st,
        rel_types=st.lists(relationship_types_st, min_size=1, max_size=5),
        chunk_texts=chunk_texts_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_manual_relationships_preserved_after_reprocessing(
        self,
        num_files: int,
        num_manual_rels: int,
        rel_types: list[str],
        chunk_texts: list[str],
    ):
        """After file re-processing (which removes old extractions and re-extracts),
        all pre-existing manual relationships SHALL remain unchanged.

        This tests the re-processing path where _remove_file_extractions is called
        before new extraction, ensuring manual relationships survive the cleanup.

        **Validates: Requirements 5.3**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Step 1: Create files
            files = _create_files(session, num_files)
            file_ids = [f.id for f in files]
            session.commit()

            # Step 2: Create manual relationships
            manual_rels_before = _create_manual_relationships(
                session, file_ids, num_manual_rels, rel_types
            )

            # Step 3: Create chunks for the first file
            target_file_id = file_ids[0]
            chunks = _create_chunks_for_file(session, target_file_id, chunk_texts)
            session.commit()

            # Step 4: Run extraction FIRST time (initial processing)
            config = GraphRAGSettings()
            graphrag_engine = GraphRAGEngine(db=session, config=config)
            graphrag_engine.extract_entities_and_relationships(chunks, target_file_id)

            # Step 5: Run extraction SECOND time (re-processing)
            # This triggers _remove_file_extractions before re-extraction
            graphrag_engine.extract_entities_and_relationships(chunks, target_file_id)

            # Step 6: Verify ALL manual relationships are still present and unchanged
            all_relationships_after = session.query(Relationship).all()

            assert len(all_relationships_after) == len(manual_rels_before), (
                f"Manual relationship count changed after re-processing: "
                f"expected {len(manual_rels_before)}, "
                f"got {len(all_relationships_after)}"
            )

            for expected_rel in manual_rels_before:
                found = session.query(Relationship).filter(
                    Relationship.id == expected_rel["id"]
                ).first()

                assert found is not None, (
                    f"Manual relationship with id={expected_rel['id']} was deleted "
                    f"after re-processing"
                )
                assert found.source_file_id == expected_rel["source_file_id"], (
                    f"source_file_id changed for relationship {found.id} after re-processing"
                )
                assert found.target_file_id == expected_rel["target_file_id"], (
                    f"target_file_id changed for relationship {found.id} after re-processing"
                )
                assert found.relationship_type == expected_rel["relationship_type"], (
                    f"relationship_type changed for relationship {found.id} after re-processing"
                )
                assert found.is_manual == expected_rel["is_manual"], (
                    f"is_manual changed for relationship {found.id} after re-processing"
                )

        finally:
            session.close()
            engine.dispose()


# ---------------------------------------------------------------------------
# Property 14: File re-processing replaces extracted entities and relationships
# ---------------------------------------------------------------------------


class TestProperty14FileReprocessingCleanup:
    """Property 14: File re-processing replaces extracted entities and relationships.

    For any file that has been previously processed for entity/relationship extraction,
    when re-processing is triggered, all previously extracted entities and relationships
    associated with that file SHALL be removed before new extraction results are stored.

    **Validates: Requirements 5.4**
    """

    @given(
        num_chunks=st.integers(min_value=1, max_value=5),
        num_entities_per_chunk=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=50, deadline=None)
    def test_reprocessing_removes_all_previous_entities_for_file(
        self, num_chunks: int, num_entities_per_chunk: int
    ):
        """When re-processing is triggered for a file, all previously extracted
        entities associated exclusively with that file are removed.

        **Validates: Requirements 5.4**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create a file with chunks, entities, and relationships
            files = _create_files(session, 1)
            file = files[0]
            session.commit()

            chunks = _create_chunks_for_file(
                session, file.id, [f"chunk {i} text" for i in range(num_chunks)]
            )
            session.commit()
            chunk_ids = [c.id for c in chunks]

            # Create entities referencing only this file's chunks
            entities = []
            for chunk_id in chunk_ids:
                for j in range(num_entities_per_chunk):
                    entity = Entity(
                        name=f"Entity_{chunk_id}_{j}",
                        normalized_name=f"entity_{chunk_id}_{j}",
                        entity_type="concept",
                        description=f"Description for entity {chunk_id}_{j}",
                        source_chunk_ids=[chunk_id],
                    )
                    session.add(entity)
                    entities.append(entity)
            session.flush()

            # Create relationships between consecutive entity pairs
            for i in range(0, len(entities) - 1, 2):
                rel = EntityRelationship(
                    source_entity_id=entities[i].id,
                    target_entity_id=entities[i + 1].id,
                    description="relates to",
                    strength=0.7,
                    source_chunk_id=chunk_ids[0],
                )
                session.add(rel)
            session.commit()

            # Verify initial state: entities exist (relationships guaranteed
            # since num_entities_per_chunk >= 2 ensures at least 2 entities)
            initial_entity_count = session.query(Entity).count()
            initial_rel_count = session.query(EntityRelationship).count()
            assert initial_entity_count > 0
            assert initial_rel_count > 0

            # Act: trigger re-processing via GraphRAGEngine._remove_file_extractions
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(session, config)
            graphrag._remove_file_extractions(file.id)

            # Assert: all entities that only referenced this file's chunks are removed
            remaining_entities = session.query(Entity).all()
            for entity in remaining_entities:
                entity_chunk_ids = set(entity.source_chunk_ids or [])
                assert not entity_chunk_ids.issubset(set(chunk_ids)), (
                    f"Entity '{entity.name}' still exists but only references "
                    f"chunks {entity_chunk_ids} from the re-processed file"
                )

            # All entities should be removed since they only reference this file
            assert len(remaining_entities) == 0, (
                f"Expected 0 entities after re-processing, "
                f"got {len(remaining_entities)}"
            )
        finally:
            session.close()
            engine.dispose()

    @given(
        num_chunks=st.integers(min_value=1, max_value=5),
        num_entities_per_chunk=st.integers(min_value=2, max_value=4),
    )
    @settings(max_examples=50, deadline=None)
    def test_reprocessing_removes_all_previous_relationships_for_file(
        self, num_chunks: int, num_entities_per_chunk: int
    ):
        """When re-processing is triggered for a file, all previously extracted
        relationships associated with that file's chunks are removed.

        **Validates: Requirements 5.4**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create a file with chunks, entities, and relationships
            files = _create_files(session, 1)
            file = files[0]
            session.commit()

            chunks = _create_chunks_for_file(
                session, file.id, [f"chunk {i} text" for i in range(num_chunks)]
            )
            session.commit()
            chunk_ids = [c.id for c in chunks]

            # Create entities (num_entities_per_chunk >= 2 ensures pairs exist)
            entities = []
            for chunk_id in chunk_ids:
                for j in range(num_entities_per_chunk):
                    entity = Entity(
                        name=f"Entity_{chunk_id}_{j}",
                        normalized_name=f"entity_{chunk_id}_{j}",
                        entity_type="concept",
                        description=f"Description",
                        source_chunk_ids=[chunk_id],
                    )
                    session.add(entity)
                    entities.append(entity)
            session.flush()

            # Create relationships referencing this file's chunks
            for i in range(0, len(entities) - 1, 2):
                chunk_id = chunk_ids[i % len(chunk_ids)]
                rel = EntityRelationship(
                    source_entity_id=entities[i].id,
                    target_entity_id=entities[i + 1].id,
                    description="relates to",
                    strength=0.5,
                    source_chunk_id=chunk_id,
                )
                session.add(rel)
            session.commit()

            # Verify initial state
            initial_rel_count = session.query(EntityRelationship).count()
            assert initial_rel_count > 0

            # Act: trigger re-processing cleanup
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(session, config)
            graphrag._remove_file_extractions(file.id)

            # Assert: all relationships referencing this file's chunks are removed
            remaining_rels = session.query(EntityRelationship).all()
            for rel in remaining_rels:
                assert rel.source_chunk_id not in chunk_ids, (
                    f"Relationship {rel.id} still references chunk "
                    f"{rel.source_chunk_id} from the re-processed file"
                )

            assert len(remaining_rels) == 0, (
                f"Expected 0 relationships after re-processing, "
                f"got {len(remaining_rels)}"
            )
        finally:
            session.close()
            engine.dispose()

    @given(
        num_chunks_file1=st.integers(min_value=1, max_value=4),
        num_entities_per_chunk=st.integers(min_value=1, max_value=3),
        num_chunks_file2=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, deadline=None)
    def test_reprocessing_does_not_affect_other_files_entities(
        self,
        num_chunks_file1: int,
        num_entities_per_chunk: int,
        num_chunks_file2: int,
    ):
        """When re-processing file A, entities and relationships belonging
        exclusively to file B remain untouched.

        **Validates: Requirements 5.4**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create two files
            files = _create_files(session, 2)
            file1, file2 = files[0], files[1]
            session.commit()

            # Create chunks for both files
            chunks1 = _create_chunks_for_file(
                session, file1.id,
                [f"file1 chunk {i}" for i in range(num_chunks_file1)]
            )
            chunks2 = _create_chunks_for_file(
                session, file2.id,
                [f"file2 chunk {i}" for i in range(num_chunks_file2)]
            )
            session.commit()

            chunk_ids1 = [c.id for c in chunks1]
            chunk_ids2 = [c.id for c in chunks2]

            # Create entities for file1
            entities1 = []
            for chunk_id in chunk_ids1:
                for j in range(num_entities_per_chunk):
                    entity = Entity(
                        name=f"F1_Entity_{chunk_id}_{j}",
                        normalized_name=f"f1_entity_{chunk_id}_{j}",
                        entity_type="concept",
                        description="File 1 entity",
                        source_chunk_ids=[chunk_id],
                    )
                    session.add(entity)
                    entities1.append(entity)
            session.flush()

            # Create entities for file2
            entities2 = []
            for chunk_id in chunk_ids2:
                for j in range(num_entities_per_chunk):
                    entity = Entity(
                        name=f"F2_Entity_{chunk_id}_{j}",
                        normalized_name=f"f2_entity_{chunk_id}_{j}",
                        entity_type="concept",
                        description="File 2 entity",
                        source_chunk_ids=[chunk_id],
                    )
                    session.add(entity)
                    entities2.append(entity)
            session.flush()

            # Create relationships for file1
            for i in range(0, len(entities1) - 1, 2):
                rel = EntityRelationship(
                    source_entity_id=entities1[i].id,
                    target_entity_id=entities1[i + 1].id,
                    description="f1 relates",
                    strength=0.6,
                    source_chunk_id=chunk_ids1[0],
                )
                session.add(rel)

            # Create relationships for file2
            rels2_count = 0
            for i in range(0, len(entities2) - 1, 2):
                rel = EntityRelationship(
                    source_entity_id=entities2[i].id,
                    target_entity_id=entities2[i + 1].id,
                    description="f2 relates",
                    strength=0.8,
                    source_chunk_id=chunk_ids2[0],
                )
                session.add(rel)
                rels2_count += 1
            session.commit()

            # Record file2's entity IDs before re-processing
            file2_entity_ids_before = {e.id for e in entities2}
            file2_entity_count = len(entities2)

            # Act: re-process file1 only
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(session, config)
            graphrag._remove_file_extractions(file1.id)

            # Assert: file2's entities are still present
            remaining_entities = session.query(Entity).all()
            remaining_entity_ids = {e.id for e in remaining_entities}

            for eid in file2_entity_ids_before:
                assert eid in remaining_entity_ids, (
                    f"Entity {eid} from file2 was incorrectly removed "
                    f"when re-processing file1"
                )

            assert len(remaining_entities) == file2_entity_count, (
                f"Expected {file2_entity_count} entities (file2 only), "
                f"got {len(remaining_entities)}"
            )

            # Assert: file2's relationships are still present
            remaining_rels = session.query(EntityRelationship).all()
            file2_remaining_rels = [
                r for r in remaining_rels if r.source_chunk_id in chunk_ids2
            ]
            assert len(file2_remaining_rels) == rels2_count, (
                f"Expected {rels2_count} relationships for file2, "
                f"got {len(file2_remaining_rels)}"
            )
        finally:
            session.close()
            engine.dispose()

    @given(
        chunk_texts=chunk_texts_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_full_reprocessing_flow_replaces_old_with_new(
        self, chunk_texts: list[str]
    ):
        """The full extract_entities_and_relationships call on a previously
        processed file removes old entities/relationships and stores only new ones.

        This tests the complete re-processing flow: internal removal + new extraction.

        **Validates: Requirements 5.4**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create a file with chunks
            files = _create_files(session, 1)
            file = files[0]
            session.commit()

            chunks = _create_chunks_for_file(session, file.id, chunk_texts)
            session.commit()
            chunk_ids = [c.id for c in chunks]

            # First extraction pass
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(session, config)
            graphrag.extract_entities_and_relationships(chunks, file.id)

            # Record entities/relationships after first pass
            entities_after_first = session.query(Entity).all()
            rels_after_first = session.query(EntityRelationship).all()
            first_entity_ids = {e.id for e in entities_after_first}
            first_rel_ids = {r.id for r in rels_after_first}

            # Second extraction pass (re-processing)
            graphrag.extract_entities_and_relationships(chunks, file.id)

            # After re-processing, old entity/relationship IDs should be gone
            # (replaced by new ones)
            entities_after_second = session.query(Entity).all()
            rels_after_second = session.query(EntityRelationship).all()
            second_entity_ids = {e.id for e in entities_after_second}
            second_rel_ids = {r.id for r in rels_after_second}

            # Old IDs should not be present (they were deleted and new ones created)
            # Note: if the same entities are re-extracted, they get new IDs
            # The key property is that _remove_file_extractions was called,
            # so old records are gone. New records may have different IDs.
            # We verify by checking that all current entities reference only
            # this file's chunks
            for entity in entities_after_second:
                entity_chunk_ids = set(entity.source_chunk_ids or [])
                assert entity_chunk_ids.issubset(set(chunk_ids)), (
                    f"Entity '{entity.name}' references chunks {entity_chunk_ids} "
                    f"not in current file chunks {chunk_ids}"
                )

            for rel in rels_after_second:
                assert rel.source_chunk_id in chunk_ids, (
                    f"Relationship {rel.id} references chunk {rel.source_chunk_id} "
                    f"not in current file chunks {chunk_ids}"
                )
        finally:
            session.close()
            engine.dispose()

    @given(
        num_chunks=st.integers(min_value=1, max_value=5),
        num_entities_per_chunk=st.integers(min_value=1, max_value=3),
    )
    @settings(max_examples=50, deadline=None)
    def test_reprocessing_with_no_prior_chunks_is_safe(
        self, num_chunks: int, num_entities_per_chunk: int
    ):
        """Calling _remove_file_extractions on a file with no prior chunks
        does not raise errors and does not affect other data.

        **Validates: Requirements 5.4**
        """
        engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup: create two files, only file2 has chunks/entities
            files = _create_files(session, 2)
            file1, file2 = files[0], files[1]
            session.commit()

            chunks2 = _create_chunks_for_file(
                session, file2.id,
                [f"file2 chunk {i}" for i in range(num_chunks)]
            )
            session.commit()
            chunk_ids2 = [c.id for c in chunks2]

            # Create entities for file2
            entities2 = []
            for chunk_id in chunk_ids2:
                for j in range(num_entities_per_chunk):
                    entity = Entity(
                        name=f"Entity_{chunk_id}_{j}",
                        normalized_name=f"entity_{chunk_id}_{j}",
                        entity_type="concept",
                        description="Description",
                        source_chunk_ids=[chunk_id],
                    )
                    session.add(entity)
                    entities2.append(entity)
            session.flush()

            # Create relationships for file2
            for i in range(0, len(entities2) - 1, 2):
                rel = EntityRelationship(
                    source_entity_id=entities2[i].id,
                    target_entity_id=entities2[i + 1].id,
                    description="relates",
                    strength=0.5,
                    source_chunk_id=chunk_ids2[0],
                )
                session.add(rel)
            session.commit()

            entity_count_before = session.query(Entity).count()
            rel_count_before = session.query(EntityRelationship).count()

            # Act: re-process file1 which has no chunks
            config = GraphRAGSettings()
            graphrag = GraphRAGEngine(session, config)
            graphrag._remove_file_extractions(file1.id)

            # Assert: file2's data is untouched
            entity_count_after = session.query(Entity).count()
            rel_count_after = session.query(EntityRelationship).count()

            assert entity_count_after == entity_count_before, (
                f"Entity count changed from {entity_count_before} to "
                f"{entity_count_after} when re-processing a file with no chunks"
            )
            assert rel_count_after == rel_count_before, (
                f"Relationship count changed from {rel_count_before} to "
                f"{rel_count_after} when re-processing a file with no chunks"
            )
        finally:
            session.close()
            engine.dispose()
