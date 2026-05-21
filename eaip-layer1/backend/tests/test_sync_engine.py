"""Unit tests for the SyncEngine service."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.sync_log import SyncLog
from app.services.sync_engine import SyncEngine, SyncResult


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def kb_dir(tmp_path):
    """Create a temporary knowledge_base directory."""
    kb = tmp_path / "knowledge_base"
    kb.mkdir()
    return kb


def _create_file(kb_dir: Path, rel_path: str, content: str = "hello") -> Path:
    """Helper to create a file in the knowledge base."""
    file_path = kb_dir / rel_path.replace("/", "\\")
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    return file_path


class TestSyncEngineNewFiles:
    """Tests for detecting and adding new files."""

    def test_sync_empty_filesystem(self, db_session, kb_dir):
        """Sync with no files on disk should produce zero changes."""
        engine = SyncEngine(db_session, str(kb_dir))
        result = engine.execute_sync()

        assert result.files_added == 0
        assert result.files_updated == 0
        assert result.files_removed == 0
        assert result.status == "success"

    def test_sync_adds_new_files(self, db_session, kb_dir):
        """Sync should detect and add files that exist on disk but not in DB."""
        _create_file(kb_dir, "Finance/Budgets/report.md", "# Budget Report")
        _create_file(kb_dir, "HR/Policies/policy.txt", "Remote work policy")

        engine = SyncEngine(db_session, str(kb_dir))
        result = engine.execute_sync()

        assert result.files_added == 2
        assert result.files_updated == 0
        assert result.files_removed == 0
        assert result.status == "success"

        # Verify records in DB
        files = db_session.query(File).all()
        assert len(files) == 2
        paths = {f.path for f in files}
        assert "Finance/Budgets/report.md" in paths
        assert "HR/Policies/policy.txt" in paths

    def test_sync_extracts_department_from_path(self, db_session, kb_dir):
        """Department should be extracted from the first path segment."""
        _create_file(kb_dir, "Supply_Chain/Logistics/routes.md", "# Routes")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        file_record = db_session.query(File).first()
        assert file_record.department == "Supply_Chain"


class TestSyncEngineModifiedFiles:
    """Tests for detecting and updating modified files."""

    def test_sync_detects_modified_files(self, db_session, kb_dir):
        """Sync should detect files whose content hash has changed."""
        file_path = _create_file(kb_dir, "Finance/Reports/data.json", '{"v": 1}')

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        # Modify the file
        file_path.write_text('{"v": 2}', encoding="utf-8")

        result = engine.execute_sync()

        assert result.files_added == 0
        assert result.files_updated == 1
        assert result.files_removed == 0

    def test_sync_updates_hash_and_size(self, db_session, kb_dir):
        """Modified files should have their hash and size updated in DB."""
        file_path = _create_file(kb_dir, "IT_Audit/Security/scan.txt", "short")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        original_file = db_session.query(File).first()
        original_hash = original_file.content_hash
        original_size = original_file.size

        # Modify with longer content
        file_path.write_text("much longer content here", encoding="utf-8")

        engine.execute_sync()

        updated_file = db_session.query(File).first()
        assert updated_file.content_hash != original_hash
        assert updated_file.size != original_size


class TestSyncEngineDeletedFiles:
    """Tests for detecting and removing deleted files."""

    def test_sync_detects_deleted_files(self, db_session, kb_dir):
        """Sync should detect files in DB that no longer exist on disk."""
        file_path = _create_file(kb_dir, "Executive/Strategy/plan.md", "# Plan")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        assert db_session.query(File).count() == 1

        # Delete the file from disk
        file_path.unlink()

        result = engine.execute_sync()

        assert result.files_added == 0
        assert result.files_updated == 0
        assert result.files_removed == 1
        assert db_session.query(File).count() == 0


class TestSyncEngineLogging:
    """Tests for sync operation logging."""

    def test_sync_creates_log_entry(self, db_session, kb_dir):
        """Each sync should create a sync_log entry."""
        _create_file(kb_dir, "Finance/Budgets/budget.md", "# Budget")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        logs = db_session.query(SyncLog).all()
        assert len(logs) == 1
        assert logs[0].files_added == 1
        assert logs[0].files_updated == 0
        assert logs[0].files_removed == 0
        assert logs[0].status == "success"
        assert logs[0].timestamp is not None

    def test_sync_log_counts_match_result(self, db_session, kb_dir):
        """Sync log counts should match the returned SyncResult."""
        _create_file(kb_dir, "HR/Onboarding/checklist.json", '{"items": []}')

        engine = SyncEngine(db_session, str(kb_dir))
        result = engine.execute_sync()

        log = db_session.query(SyncLog).first()
        assert log.files_added == result.files_added
        assert log.files_updated == result.files_updated
        assert log.files_removed == result.files_removed


class TestSyncEngineIdempotency:
    """Tests for sync idempotency (no changes when nothing changed)."""

    def test_sync_is_idempotent_when_no_changes(self, db_session, kb_dir):
        """Running sync twice without changes should produce zero diffs."""
        _create_file(kb_dir, "Finance/Budgets/budget.md", "# Budget")
        _create_file(kb_dir, "HR/Policies/policy.txt", "Policy content")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        result = engine.execute_sync()

        assert result.files_added == 0
        assert result.files_updated == 0
        assert result.files_removed == 0


class TestSyncEngineMixedOperations:
    """Tests for sync with mixed add/update/delete operations."""

    def test_sync_handles_mixed_changes(self, db_session, kb_dir):
        """Sync should handle adds, updates, and deletes in a single run."""
        file_a = _create_file(kb_dir, "Finance/Reports/a.txt", "original")
        file_b = _create_file(kb_dir, "HR/Policies/b.txt", "keep this")

        engine = SyncEngine(db_session, str(kb_dir))
        engine.execute_sync()

        # Modify file_a, delete file_b, add file_c
        file_a.write_text("modified content", encoding="utf-8")
        file_b.unlink()
        _create_file(kb_dir, "Executive/Strategy/c.md", "# New file")

        result = engine.execute_sync()

        assert result.files_added == 1
        assert result.files_updated == 1
        assert result.files_removed == 1
        assert result.status == "success"

        # Verify final DB state
        files = db_session.query(File).all()
        assert len(files) == 2
        paths = {f.path for f in files}
        assert "Finance/Reports/a.txt" in paths
        assert "Executive/Strategy/c.md" in paths
        assert "HR/Policies/b.txt" not in paths
