"""Property-based tests for embedding status state transitions.

Property 24: Embedding status state transitions are correct

For any file in the knowledge base, the embedding_status SHALL follow the
defined state machine:
- None (never embedded): transitions to "pending" when file is added/modified by sync
- "pending": transitions to "embedded" after successful embedding
- "embedded": transitions to "pending" when file is modified (hash changes)
- "embedded": transitions to "removal_failed" when cleanup fails during deletion

**Validates: Requirements 10.1, 10.5**
"""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import hypothesis.strategies as st
import pytest
from hypothesis import given, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.file import File
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

content_st = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=10,
    max_size=500,
).filter(lambda t: len(t.strip()) >= 5)


# --- Helpers ---


def _create_test_db():
    """Create a fresh in-memory SQLite database with all tables."""
    db_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    return db_engine, Session


def _create_file_in_db(
    session,
    name: str = "test.txt",
    path: str = "dept/test.txt",
    department: str = "engineering",
    content_hash: str = "hash1",
    embedding_status: str | None = None,
) -> File:
    """Create a File record in the database."""
    now = datetime.now(timezone.utc)
    f = File(
        name=name,
        path=path,
        department=department,
        size=100,
        content_hash=content_hash,
        created_at=now,
        modified_at=now,
        embedding_status=embedding_status,
    )
    session.add(f)
    session.commit()
    session.refresh(f)
    return f


# --- Property Tests ---


class TestProperty24EmbeddingStatusTransitions:
    """Property 24: Embedding status state transitions are correct.

    **Validates: Requirements 10.1, 10.5**
    """

    @given(
        name=file_name_st,
        department=departments,
    )
    @settings(max_examples=50, deadline=None)
    def test_new_file_gets_pending_status(
        self, name: str, department: str
    ):
        """When a new file is added via sync, its embedding_status SHALL be "pending".

        **Validates: Requirements 10.1, 10.5**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Create a sync engine with a mock filesystem
            with patch.object(
                SyncEngine, "_scan_filesystem"
            ) as mock_scan:
                rel_path = f"{department}/{name}"
                mock_scan.return_value = {
                    rel_path: {
                        "name": name,
                        "path": rel_path,
                        "department": department,
                        "size": 100,
                        "modified_at": datetime.now(timezone.utc),
                        "created_at": datetime.now(timezone.utc),
                        "content_hash": "test_hash_123",
                    }
                }

                sync_engine = SyncEngine(session, "./kb")
                sync_engine.execute_sync()

            # Verify the new file has embedding_status = "pending"
            files = session.query(File).all()
            assert len(files) == 1
            assert files[0].embedding_status == "pending", (
                f"New file should have embedding_status='pending', "
                f"got '{files[0].embedding_status}'"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        name=file_name_st,
        department=departments,
        old_hash=st.text(alphabet="abcdef0123456789", min_size=8, max_size=16),
        new_hash=st.text(alphabet="abcdef0123456789", min_size=8, max_size=16),
    )
    @settings(max_examples=50, deadline=None)
    def test_modified_file_gets_pending_status(
        self, name: str, department: str, old_hash: str, new_hash: str
    ):
        """When a file is modified (hash changes), its embedding_status SHALL
        transition from "embedded" to "pending".

        **Validates: Requirements 10.1, 10.5**
        """
        assume(old_hash != new_hash)

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            rel_path = f"{department}/{name}"

            # Create a file that was previously embedded
            existing_file = _create_file_in_db(
                session,
                name=name,
                path=rel_path,
                department=department,
                content_hash=old_hash,
                embedding_status="embedded",
            )
            existing_file_id = existing_file.id

            # Run sync with the new hash (simulating modified content)
            with patch.object(
                SyncEngine, "_scan_filesystem"
            ) as mock_scan:
                mock_scan.return_value = {
                    rel_path: {
                        "name": name,
                        "path": rel_path,
                        "department": department,
                        "size": 200,
                        "modified_at": datetime.now(timezone.utc),
                        "created_at": datetime.now(timezone.utc),
                        "content_hash": new_hash,
                    }
                }

                sync_engine = SyncEngine(session, "./kb")
                sync_engine.execute_sync()

            # Verify embedding_status transitioned to "pending"
            updated_file = session.query(File).filter(File.id == existing_file_id).first()
            assert updated_file is not None
            assert updated_file.embedding_status == "pending", (
                f"Modified file should transition from 'embedded' to 'pending', "
                f"got '{updated_file.embedding_status}'"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        name=file_name_st,
        department=departments,
        content=content_st,
    )
    @settings(max_examples=20, deadline=60000)
    def test_successful_embedding_sets_embedded_status(
        self, name: str, department: str, content: str
    ):
        """After successful embedding, the file's embedding_status SHALL be "embedded".

        **Validates: Requirements 10.5**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Create a file with "pending" status
            now = datetime.now(timezone.utc)
            db_file = File(
                name=name,
                path=f"{department}/{name}",
                department=department,
                size=len(content),
                content_hash="test_hash",
                created_at=now,
                modified_at=now,
                embedding_status="pending",
            )
            session.add(db_file)
            session.commit()
            session.refresh(db_file)
            file_id = db_file.id

            # Write content to a temp file
            import tempfile
            import shutil

            tmp_dir = tempfile.mkdtemp()
            try:
                file_path = Path(tmp_dir) / name
                file_path.write_text(content, encoding="utf-8")
                db_file.path = str(file_path)
                session.commit()

                # Run embedding
                config = GraphRAGSettings(
                    chunk_size=256,
                    chunk_overlap=20,
                    vector_store_path=str(Path(tmp_dir) / "chroma_db"),
                )

                with patch(
                    "app.services.embedding_engine.GraphRAGEngine"
                ) as MockGraphRAG:
                    MockGraphRAG.return_value.extract_entities_and_relationships.return_value = None

                    engine = EmbeddingEngine(db=session, config=config)
                    result = engine.run_single(file_id)

                # Verify embedding_status is "embedded"
                session.refresh(db_file)
                assert db_file.embedding_status == "embedded", (
                    f"After successful embedding, status should be 'embedded', "
                    f"got '{db_file.embedding_status}'"
                )

                # Verify chunks were created
                chunks = session.query(Chunk).filter(Chunk.file_id == file_id).all()
                if content.strip() and len(content) > 50:
                    assert len(chunks) > 0, (
                        "Successful embedding should create chunks for non-empty content"
                    )

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        finally:
            session.close()
            db_engine.dispose()

    @given(
        department=departments,
    )
    @settings(max_examples=30, deadline=None)
    def test_deletion_cleanup_failure_sets_removal_failed(
        self, department: str
    ):
        """When cleanup fails during file deletion, the embedding_status SHALL
        be set to "removal_failed".

        **Validates: Requirements 10.2**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Create an embedded file
            now = datetime.now(timezone.utc)
            db_file = File(
                name="test.txt",
                path=f"{department}/test.txt",
                department=department,
                size=100,
                content_hash="hash123",
                created_at=now,
                modified_at=now,
                embedding_status="embedded",
            )
            session.add(db_file)
            session.commit()
            session.refresh(db_file)
            file_id = db_file.id

            # Simulate deletion where cleanup raises an exception
            db_files = {db_file.path: db_file}
            deleted_paths = {db_file.path}

            # Override _cleanup_graphrag_data to fail
            sync_engine = SyncEngine(session, "./kb")
            original_cleanup = sync_engine._cleanup_graphrag_data

            def failing_cleanup(fid):
                raise RuntimeError("Simulated cleanup failure")

            sync_engine._cleanup_graphrag_data = failing_cleanup

            result_count = sync_engine._remove_deleted_files(db_files, deleted_paths)

            # Verify the file's status is "removal_failed"
            session.refresh(db_file)
            assert db_file.embedding_status == "removal_failed", (
                f"After cleanup failure, status should be 'removal_failed', "
                f"got '{db_file.embedding_status}'"
            )

            # Verify the file was NOT deleted
            remaining = session.query(File).filter(File.id == file_id).first()
            assert remaining is not None, (
                "File should not be deleted when cleanup fails"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        name=file_name_st,
        department=departments,
    )
    @settings(max_examples=30, deadline=None)
    def test_unmodified_embedded_file_keeps_embedded_status(
        self, name: str, department: str
    ):
        """When a file's content_hash has not changed, the sync operation SHALL
        preserve the existing "embedded" status.

        **Validates: Requirements 10.1**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            rel_path = f"{department}/{name}"
            common_hash = "unchanged_hash_value"

            # Create an embedded file
            existing_file = _create_file_in_db(
                session,
                name=name,
                path=rel_path,
                department=department,
                content_hash=common_hash,
                embedding_status="embedded",
            )
            existing_file_id = existing_file.id

            # Run sync with the same hash (no modification)
            with patch.object(
                SyncEngine, "_scan_filesystem"
            ) as mock_scan:
                mock_scan.return_value = {
                    rel_path: {
                        "name": name,
                        "path": rel_path,
                        "department": department,
                        "size": 100,
                        "modified_at": datetime.now(timezone.utc),
                        "created_at": datetime.now(timezone.utc),
                        "content_hash": common_hash,
                    }
                }

                sync_engine = SyncEngine(session, "./kb")
                sync_engine.execute_sync()

            # Verify embedding_status remains "embedded"
            updated_file = session.query(File).filter(File.id == existing_file_id).first()
            assert updated_file is not None
            assert updated_file.embedding_status == "embedded", (
                f"Unmodified file should keep 'embedded' status, "
                f"got '{updated_file.embedding_status}'"
            )

        finally:
            session.close()
            db_engine.dispose()
