"""Unit tests for the file service."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.services import file_service


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
def sample_file(db_session):
    """Insert a sample file record into the database."""
    file = File(
        name="report.md",
        path="Finance/Reports/report.md",
        department="Finance",
        size=1024,
        tags=["budget", "quarterly"],
        created_at=datetime(2024, 1, 1),
        modified_at=datetime(2024, 6, 15),
        content_hash="abc123",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


class TestListFiles:
    """Tests for list_files."""

    def test_returns_empty_list_when_no_files(self, db_session):
        """Should return an empty list when no files are indexed."""
        result = file_service.list_files(db_session)
        assert result == []

    def test_returns_all_files(self, db_session, sample_file):
        """Should return all indexed files."""
        # Add a second file
        file2 = File(
            name="policy.txt",
            path="HR/Policies/policy.txt",
            department="HR",
            size=512,
            tags=[],
            created_at=datetime(2024, 2, 1),
            modified_at=datetime(2024, 3, 1),
            content_hash="def456",
        )
        db_session.add(file2)
        db_session.commit()

        result = file_service.list_files(db_session)
        assert len(result) == 2


class TestGetFile:
    """Tests for get_file."""

    def test_returns_file_by_id(self, db_session, sample_file):
        """Should return the file when it exists."""
        result = file_service.get_file(db_session, sample_file.id)
        assert result.id == sample_file.id
        assert result.name == "report.md"

    def test_raises_404_when_not_found(self, db_session):
        """Should raise HTTPException 404 for non-existent file."""
        with pytest.raises(HTTPException) as exc_info:
            file_service.get_file(db_session, 9999)
        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail.lower()


class TestGetFileContent:
    """Tests for get_file_content."""

    def test_returns_path_when_file_exists_on_disk(self, db_session, sample_file, tmp_path):
        """Should return the resolved file path when the file exists on disk."""
        # Create the file on disk
        kb_path = tmp_path / "knowledge_base"
        file_on_disk = kb_path / "Finance" / "Reports" / "report.md"
        file_on_disk.parent.mkdir(parents=True, exist_ok=True)
        file_on_disk.write_text("# Report content")

        with patch("app.services.file_service.settings") as mock_settings:
            mock_settings.knowledge_base_path = str(kb_path)
            result = file_service.get_file_content(db_session, sample_file.id)

        assert result == file_on_disk

    def test_raises_404_when_file_missing_from_disk(self, db_session, sample_file, tmp_path):
        """Should raise HTTPException 404 when file record exists but file is missing from disk."""
        kb_path = tmp_path / "knowledge_base"
        kb_path.mkdir()

        with patch("app.services.file_service.settings") as mock_settings:
            mock_settings.knowledge_base_path = str(kb_path)
            with pytest.raises(HTTPException) as exc_info:
                file_service.get_file_content(db_session, sample_file.id)

        assert exc_info.value.status_code == 404
        assert "missing from disk" in exc_info.value.detail.lower()

    def test_raises_404_when_file_record_not_found(self, db_session):
        """Should raise HTTPException 404 when file ID doesn't exist."""
        with pytest.raises(HTTPException) as exc_info:
            file_service.get_file_content(db_session, 9999)
        assert exc_info.value.status_code == 404


class TestUpdateTags:
    """Tests for update_tags."""

    def test_updates_tags_on_file(self, db_session, sample_file):
        """Should update the tags field and return the updated file."""
        new_tags = ["finance", "annual", "2024"]
        result = file_service.update_tags(db_session, sample_file.id, new_tags)

        assert result.tags == new_tags
        assert result.id == sample_file.id

    def test_can_set_empty_tags(self, db_session, sample_file):
        """Should allow setting tags to an empty list."""
        result = file_service.update_tags(db_session, sample_file.id, [])
        assert result.tags == []

    def test_raises_404_when_file_not_found(self, db_session):
        """Should raise HTTPException 404 for non-existent file."""
        with pytest.raises(HTTPException) as exc_info:
            file_service.update_tags(db_session, 9999, ["tag"])
        assert exc_info.value.status_code == 404


class TestDeleteFile:
    """Tests for delete_file."""

    def test_deletes_file_from_database(self, db_session, sample_file):
        """Should soft-delete the file record (is_deleted=True)."""
        file_id = sample_file.id
        file_service.delete_file(db_session, file_id)

        file = db_session.query(File).filter(File.id == file_id).first()
        assert file is not None
        assert file.is_deleted is True
        assert file.sync_status == "deleted"

    def test_raises_404_when_file_not_found(self, db_session):
        """Should raise HTTPException 404 for non-existent file."""
        with pytest.raises(HTTPException) as exc_info:
            file_service.delete_file(db_session, 9999)
        assert exc_info.value.status_code == 404
