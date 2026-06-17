"""Unit tests for the VersionRestoreService."""

import hashlib
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.file_version import FileVersion
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.embedding_queue import EmbeddingQueueService
from app.services.version_restore import (
    FileDeletedError,
    FileNotFoundRestoreError,
    VersionNotFoundError,
    VersionRestoreError,
    VersionRestoreService,
)
from app.services.version_store import VersionStoreService


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
    """Create a temporary knowledge base directory."""
    kb = tmp_path / "kb"
    kb.mkdir()
    return str(kb)


@pytest.fixture
def archive_dir(tmp_path):
    """Create a temporary archive directory."""
    archive = tmp_path / ".versions"
    archive.mkdir()
    return str(archive)


@pytest.fixture
def sample_file(db_session, kb_dir):
    """Create a sample File record and physical file in the knowledge base."""
    file_record = File(
        id=1,
        name="test.txt",
        path="test.txt",
        department="Engineering",
        size=100,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        is_deleted=False,
    )
    db_session.add(file_record)
    db_session.commit()

    # Create the physical file
    file_path = os.path.join(kb_dir, "test.txt")
    with open(file_path, "wb") as f:
        f.write(b"current content")

    return file_record


@pytest.fixture
def deleted_file(db_session):
    """Create a deleted File record in the database."""
    file_record = File(
        id=2,
        name="deleted.txt",
        path="deleted.txt",
        department="Engineering",
        size=50,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        is_deleted=True,
    )
    db_session.add(file_record)
    db_session.commit()
    return file_record


@pytest.fixture
def version_store(db_session, archive_dir):
    """Create a VersionStoreService instance."""
    return VersionStoreService(db=db_session, archive_dir=archive_dir)


@pytest.fixture
def embedding_queue():
    """Create a mock EmbeddingQueueService."""
    mock = AsyncMock(spec=EmbeddingQueueService)
    return mock


@pytest.fixture
def audit_logger():
    """Create a mock AuditLogger."""
    mock = MagicMock(spec=AuditLogger)
    return mock


@pytest.fixture
def service(db_session, version_store, embedding_queue, audit_logger, kb_dir):
    """Create a VersionRestoreService instance."""
    return VersionRestoreService(
        db=db_session,
        version_store=version_store,
        embedding_queue=embedding_queue,
        audit_logger=audit_logger,
        kb_path=kb_dir,
    )


class TestRestoreVersion:
    """Tests for VersionRestoreService.restore_version()."""

    @pytest.mark.asyncio
    async def test_successful_restore(
        self, service, version_store, sample_file, kb_dir, embedding_queue, audit_logger
    ):
        """Should restore file content and create a new version record."""
        # Create initial version
        original_content = b"original content v1"
        version_store.create_version(1, "test.txt", original_content)

        # Create a second version
        modified_content = b"modified content v2"
        version_store.create_version(1, "test.txt", modified_content)

        # Restore to version 1
        result = await service.restore_version(
            file_id=1, version_number=1, actor="admin"
        )

        # Verify new version record was created with restore indicator
        assert result.is_restore is True
        assert result.restored_from_version == 1
        assert result.version_number == 3
        assert result.content_hash == hashlib.md5(original_content).hexdigest()

        # Verify filesystem content was restored
        file_path = os.path.join(kb_dir, "test.txt")
        with open(file_path, "rb") as f:
            assert f.read() == original_content

    @pytest.mark.asyncio
    async def test_triggers_re_embedding(
        self, service, version_store, sample_file, embedding_queue
    ):
        """Should trigger re-embedding via embedding queue after restore."""
        content = b"embeddable content"
        version_store.create_version(1, "test.txt", content)

        await service.restore_version(file_id=1, version_number=1, actor="admin")

        embedding_queue.enqueue.assert_called_once_with(
            file_id=1,
            file_path="test.txt",
            content_hash=hashlib.md5(content).hexdigest(),
        )

    @pytest.mark.asyncio
    async def test_logs_audit_event(
        self, service, version_store, sample_file, audit_logger
    ):
        """Should log the restore event to the audit logger."""
        content = b"audit test"
        version_store.create_version(1, "test.txt", content)

        await service.restore_version(file_id=1, version_number=1, actor="user123")

        audit_logger.log.assert_called_once()
        call_kwargs = audit_logger.log.call_args
        assert call_kwargs[1]["event_type"] == AuditEventType.VERSION_RESTORED
        assert call_kwargs[1]["file_id"] == 1
        assert call_kwargs[1]["actor"] == "user123"
        assert call_kwargs[1]["details"]["source_version"] == 1

    @pytest.mark.asyncio
    async def test_raises_when_file_not_found(self, service):
        """Should raise FileNotFoundRestoreError when file doesn't exist."""
        with pytest.raises(FileNotFoundRestoreError):
            await service.restore_version(
                file_id=999, version_number=1, actor="admin"
            )

    @pytest.mark.asyncio
    async def test_raises_when_file_deleted(self, service, deleted_file):
        """Should raise FileDeletedError when file is marked as deleted."""
        with pytest.raises(FileDeletedError):
            await service.restore_version(
                file_id=2, version_number=1, actor="admin"
            )

    @pytest.mark.asyncio
    async def test_raises_when_version_not_found(
        self, service, version_store, sample_file
    ):
        """Should raise VersionNotFoundError when version doesn't exist."""
        with pytest.raises(VersionNotFoundError):
            await service.restore_version(
                file_id=1, version_number=99, actor="admin"
            )

    @pytest.mark.asyncio
    async def test_atomic_write_preserves_current_on_failure(
        self, service, version_store, sample_file, kb_dir, audit_logger
    ):
        """On filesystem write failure, current file should remain unchanged."""
        content = b"version to restore"
        version_store.create_version(1, "test.txt", content)

        # Make the target directory read-only to force write failure
        file_path = os.path.join(kb_dir, "test.txt")
        original_content = b"current content"
        with open(file_path, "wb") as f:
            f.write(original_content)

        # Patch tempfile.mkstemp to simulate write failure
        with patch("app.services.version_restore.tempfile.mkstemp") as mock_mkstemp:
            mock_mkstemp.side_effect = OSError("Disk full")

            with pytest.raises(VersionRestoreError, match="Failed to write"):
                await service.restore_version(
                    file_id=1, version_number=1, actor="admin"
                )

        # Verify original file is untouched
        with open(file_path, "rb") as f:
            assert f.read() == original_content

    @pytest.mark.asyncio
    async def test_cleans_up_temp_file_on_replace_failure(
        self, service, version_store, sample_file, kb_dir
    ):
        """Should clean up temp file when os.replace fails."""
        content = b"restore content"
        version_store.create_version(1, "test.txt", content)

        # Patch os.replace to fail after temp file is written
        with patch("app.services.version_restore.os.replace") as mock_replace:
            mock_replace.side_effect = OSError("Permission denied")

            with pytest.raises(VersionRestoreError):
                await service.restore_version(
                    file_id=1, version_number=1, actor="admin"
                )

        # Verify no temp files remain
        kb_files = os.listdir(kb_dir)
        temp_files = [f for f in kb_files if f.startswith(".restore_")]
        assert len(temp_files) == 0
