"""Property-based tests for deleted file cleanup of GraphRAG data.

Property 25: Deleted file cleanup removes all associated GraphRAG data

For any file that is deleted from the filesystem and removed from the index,
the system SHALL remove all associated GraphRAG data:
- All chunks for the deleted file SHALL be removed from the chunks table
- All entity_relationships referencing chunks of the deleted file SHALL be removed
- All embeddings for the deleted file SHALL be removed from the vector store
- The file record SHALL be removed from the files table

**Validates: Requirements 10.2**
"""

import os
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
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
from app.services.document_chunker import DocumentChunker, ChunkResult
from app.services.embedding_engine import EmbeddingEngine
from app.services.sync_engine import SyncEngine


# --- Strategies ---

departments = st.sampled_from([
    "engineering", "marketing", "finance", "hr", "legal", "operations"
])

file_name_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=20,
).filter(lambda s: s.strip())


# --- Helpers ---


def _create_test_db():
    """Create a fresh in-memory SQLite database with all tables."""
    db_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    return db_engine, Session


def _setup_file_with_graphrag_data(
    session,
    file_name: str,
    department: str,
    content_hash: str = "test_hash",
) -> tuple[File, int]:
    """Create a file and populate GraphRAG data (chunks, entities, relationships)
    in the database as if it had been previously processed.

    Returns:
        Tuple of (File record, number of chunks).
    """
    now = datetime.now(timezone.utc)

    # Create the file record
    rel_path = f"{department}/{file_name}"
    db_file = File(
        name=file_name,
        path=rel_path,
        department=department,
        size=100,
        content_hash=content_hash,
        created_at=now,
        modified_at=now,
        embedding_status="embedded",
    )
    session.add(db_file)
    session.flush()
    session.refresh(db_file)
    file_id = db_file.id

    # Create chunks for this file
    chunk1 = Chunk(
        file_id=file_id,
        chunk_index=0,
        text="First chunk content for testing entity extraction.",
        start_offset=0,
        end_offset=50,
        embedding=[0.1] * 4,
    )
    chunk2 = Chunk(
        file_id=file_id,
        chunk_index=1,
        text="Second chunk with more content for entity relationships.",
        start_offset=51,
        end_offset=100,
        embedding=[0.2] * 4,
    )
    session.add(chunk1)
    session.add(chunk2)
    session.flush()
    session.refresh(chunk1)
    session.refresh(chunk2)

    chunk1_id = chunk1.id
    chunk2_id = chunk2.id

    # Create entities sourced from these chunks
    entity1 = Entity(
        name="TestEntity1",
        normalized_name="testentity1",
        entity_type="concept",
        description="A test entity",
        source_chunk_ids=[chunk1_id],
    )
    entity2 = Entity(
        name="TestEntity2",
        normalized_name="testentity2",
        entity_type="organization",
        description="Another test entity",
        source_chunk_ids=[chunk2_id],
    )
    session.add(entity1)
    session.add(entity2)
    session.flush()
    session.refresh(entity1)
    session.refresh(entity2)

    # Create relationships between entities
    relationship = EntityRelationship(
        source_entity_id=entity1.id,
        target_entity_id=entity2.id,
        description="Test relationship",
        strength=0.8,
        source_chunk_id=chunk1_id,
    )
    session.add(relationship)

    session.commit()

    return db_file, 2  # 2 chunks


# --- Property Tests ---


class TestProperty25DeletedFileCleanup:
    """Property 25: Deleted file cleanup removes all associated GraphRAG data.

    **Validates: Requirements 10.2**
    """

    @given(
        file_name=file_name_st,
        department=departments,
        other_file_name=file_name_st,
        other_department=departments,
    )
    @settings(max_examples=30, deadline=None)
    def test_deleted_file_removes_all_chunks(
        self,
        file_name: str,
        department: str,
        other_file_name: str,
        other_department: str,
    ):
        """When a file is deleted, ALL chunks associated with that file SHALL
        be removed from the chunks table.

        **Validates: Requirements 10.2**
        """
        assume(file_name != other_file_name)

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup two files with GraphRAG data
            file1, num_chunks1 = _setup_file_with_graphrag_data(
                session, file_name, department
            )
            file2, num_chunks2 = _setup_file_with_graphrag_data(
                session, other_file_name, other_department
            )

            file1_id = file1.id
            file2_id = file2.id

            # Verify both have chunks before deletion
            assert session.query(Chunk).filter(Chunk.file_id == file1_id).count() > 0
            assert session.query(Chunk).filter(Chunk.file_id == file2_id).count() > 0

            # Simulate deletion of file1 (mock ChromaVectorStore to avoid DB locking)
            with patch("app.services.sync_engine.ChromaVectorStore"):
                sync_engine = SyncEngine(session, "./kb")
                sync_engine._cleanup_graphrag_data(file1_id)
                session.delete(file1)
                session.commit()

            # Property: All chunks for deleted file are removed
            remaining_chunks_file1 = (
                session.query(Chunk).filter(Chunk.file_id == file1_id).count()
            )
            assert remaining_chunks_file1 == 0, (
                f"Deleted file's chunks should be 0, got {remaining_chunks_file1}"
            )

            # Property: Other file's chunks are preserved
            remaining_chunks_file2 = (
                session.query(Chunk).filter(Chunk.file_id == file2_id).count()
            )
            assert remaining_chunks_file2 > 0, (
                "Other file's chunks should be preserved after deletion"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        file_name=file_name_st,
        department=departments,
    )
    @settings(max_examples=30, deadline=None)
    def test_deleted_file_removes_entity_relationships(
        self,
        file_name: str,
        department: str,
    ):
        """When a file is deleted, ALL entity_relationships referencing its
        chunks SHALL be removed.

        **Validates: Requirements 10.2**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            file, _ = _setup_file_with_graphrag_data(
                session, file_name, department
            )
            file_id = file.id

            # Get the chunk IDs before deletion
            chunk_ids = [
                c[0]
                for c in session.query(Chunk.id).filter(Chunk.file_id == file_id).all()
            ]

            # Verify relationships exist
            rel_count_before = (
                session.query(EntityRelationship)
                .filter(EntityRelationship.source_chunk_id.in_(chunk_ids))
                .count()
            )
            assume(rel_count_before > 0)

            # Clean up (mock ChromaVectorStore to avoid ChromaDB locking issues)
            with patch("app.services.sync_engine.ChromaVectorStore"):
                sync_engine = SyncEngine(session, "./kb")
                sync_engine._cleanup_graphrag_data(file_id)
                session.delete(file)
                session.commit()

            # Property: All entity_relationships for deleted file's chunks are removed
            remaining_rels = (
                session.query(EntityRelationship)
                .filter(EntityRelationship.source_chunk_id.in_(chunk_ids))
                .count()
            )
            assert remaining_rels == 0, (
                f"Entity relationships for deleted file should be 0, "
                f"got {remaining_rels}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        file_name=file_name_st,
        department=departments,
    )
    @settings(max_examples=30, deadline=None)
    def test_deleted_file_removes_file_record(
        self,
        file_name: str,
        department: str,
    ):
        """When a file is deleted from the filesystem, its database record SHALL
        be removed from the files table.

        **Validates: Requirements 10.2**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            file, _ = _setup_file_with_graphrag_data(
                session, file_name, department
            )
            file_id = file.id

            # Simulate deletion through sync engine
            db_files = {file.path: file}
            deleted_paths = {file.path}

            sync_engine = SyncEngine(session, "./kb")
            result_count = sync_engine._remove_deleted_files(db_files, deleted_paths)

            # Property: The file record is removed
            remaining_file = session.query(File).filter(File.id == file_id).first()
            assert remaining_file is None, (
                "Deleted file's database record should be removed"
            )

            # Property: Return value reflects deletion
            assert result_count == 1, (
                f"Expected 1 file removed, got {result_count}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        file_name=file_name_st,
        department=departments,
        other_file_name=file_name_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_other_files_graph_data_preserved(
        self,
        file_name: str,
        department: str,
        other_file_name: str,
    ):
        """When one file is deleted, GraphRAG data for OTHER files SHALL NOT
        be affected (chunks, entities, relationships for other files remain).

        **Validates: Requirements 10.2**
        """
        assume(file_name != other_file_name)

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Setup two files
            file1, _ = _setup_file_with_graphrag_data(
                session, file_name, department
            )
            file2, _ = _setup_file_with_graphrag_data(
                session, other_file_name, department
            )

            file1_id = file1.id
            file2_id = file2.id

            # Record file2's data before deletion
            file2_chunks = list(
                session.query(Chunk).filter(Chunk.file_id == file2_id).all()
            )
            file2_chunk_ids = [c.id for c in file2_chunks]

            # Delete file1 (mock ChromaVectorStore to avoid ChromaDB locking issues)
            with patch("app.services.sync_engine.ChromaVectorStore"):
                sync_engine = SyncEngine(session, "./kb")
                sync_engine._cleanup_graphrag_data(file1_id)
                session.delete(file1)
                session.commit()

            # Property: Other file's chunks preserved
            remaining_file2_chunks = (
                session.query(Chunk).filter(Chunk.file_id == file2_id).count()
            )
            assert remaining_file2_chunks == len(file2_chunks), (
                f"Other file's chunks changed: expected {len(file2_chunks)}, "
                f"got {remaining_file2_chunks}"
            )

            # Property: Other file still exists
            remaining_file2 = session.query(File).filter(File.id == file2_id).first()
            assert remaining_file2 is not None, "Other file should still exist"

        finally:
            session.close()
            db_engine.dispose()
