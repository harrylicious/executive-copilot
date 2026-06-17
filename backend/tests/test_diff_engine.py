"""Unit tests for the DiffEngine service."""

import hashlib
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.file_version import FileVersion
from app.services.diff_engine import (
    DIFF_TIMEOUT_SECONDS,
    DiffEngine,
    DiffOperation,
    DiffResult,
    DiffSummary,
    DiffTimeoutError,
)
from app.services.text_extractor import TextExtractor
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
def archive_dir(tmp_path):
    """Create a temporary archive directory."""
    archive = tmp_path / ".versions"
    archive.mkdir()
    return str(archive)


@pytest.fixture
def sample_file(db_session):
    """Create a sample text File record in the database."""
    file_record = File(
        id=1,
        name="test.txt",
        path="/kb/test.txt",
        department="Engineering",
        size=100,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(file_record)
    db_session.commit()
    return file_record


@pytest.fixture
def sample_pdf_file(db_session):
    """Create a sample PDF File record in the database."""
    file_record = File(
        id=2,
        name="report.pdf",
        path="/kb/report.pdf",
        department="Finance",
        size=5000,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(file_record)
    db_session.commit()
    return file_record


@pytest.fixture
def version_store(db_session, archive_dir):
    """Create a VersionStoreService instance."""
    return VersionStoreService(db=db_session, archive_dir=archive_dir)


@pytest.fixture
def text_extractor():
    """Create a TextExtractor instance."""
    return TextExtractor()


@pytest.fixture
def diff_engine(text_extractor, version_store):
    """Create a DiffEngine instance."""
    return DiffEngine(text_extractor=text_extractor, version_store=version_store)


class TestComputeDiffBasic:
    """Tests for basic diff computation between text versions."""

    def test_identical_versions_returns_empty(self, diff_engine, version_store, sample_file):
        """Should return empty operations and zero counts for identical content."""
        content = b"Hello, world!\nLine two.\n"
        version_store.create_version(1, "/kb/test.txt", content)
        # Force a second version with same content by changing slightly then back
        version_store.create_version(1, "/kb/test.txt", b"different")
        version_store.create_version(1, "/kb/test.txt", content)

        result = diff_engine.compute_diff(1, 1, 3)

        assert result.operations == []
        assert result.summary.lines_added == 0
        assert result.summary.lines_deleted == 0
        assert result.summary.lines_modified == 0

    def test_single_line_addition(self, diff_engine, version_store, sample_file):
        """Should detect a line addition."""
        content_a = b"line 1\nline 2\n"
        content_b = b"line 1\nline 2\nline 3\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        assert result.summary.lines_added == 1
        assert result.summary.lines_deleted == 0
        assert result.summary.lines_modified == 0
        additions = [op for op in result.operations if op.operation == "addition"]
        assert len(additions) == 1
        assert additions[0].content == "line 3"

    def test_single_line_deletion(self, diff_engine, version_store, sample_file):
        """Should detect a line deletion."""
        content_a = b"line 1\nline 2\nline 3\n"
        content_b = b"line 1\nline 3\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        assert result.summary.lines_deleted == 1
        deletions = [op for op in result.operations if op.operation == "deletion"]
        assert len(deletions) == 1
        assert deletions[0].content == "line 2"

    def test_single_line_modification(self, diff_engine, version_store, sample_file):
        """Should detect a line modification."""
        content_a = b"line 1\nold content\nline 3\n"
        content_b = b"line 1\nnew content\nline 3\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        assert result.summary.lines_modified == 1
        modifications = [op for op in result.operations if op.operation == "modification"]
        assert len(modifications) == 1
        assert modifications[0].content == "new content"
        assert modifications[0].old_content == "old content"

    def test_multiple_changes(self, diff_engine, version_store, sample_file):
        """Should detect additions, deletions, and modifications together."""
        content_a = b"alpha\nbeta\ngamma\ndelta\n"
        content_b = b"alpha\nBETA\nepsilon\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        # beta -> BETA is a modification, gamma -> epsilon is a modification, delta is deleted
        total_ops = result.summary.lines_added + result.summary.lines_deleted + result.summary.lines_modified
        assert total_ops > 0

    def test_empty_to_content(self, diff_engine, version_store, sample_file):
        """Should detect all additions when going from empty to content."""
        content_a = b""
        content_b = b"line 1\nline 2\nline 3\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        assert result.summary.lines_added == 3
        assert result.summary.lines_deleted == 0
        assert result.summary.lines_modified == 0

    def test_content_to_empty(self, diff_engine, version_store, sample_file):
        """Should detect all deletions when going from content to empty."""
        content_a = b"line 1\nline 2\nline 3\n"
        content_b = b""
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        assert result.summary.lines_deleted == 3
        assert result.summary.lines_added == 0
        assert result.summary.lines_modified == 0


class TestComputeDiffSummary:
    """Tests for DiffSummary correctness."""

    def test_summary_matches_operations_count(self, diff_engine, version_store, sample_file):
        """Summary counts should match the actual number of each operation type."""
        content_a = b"aaa\nbbb\nccc\nddd\n"
        content_b = b"aaa\nBBB\neee\n"
        version_store.create_version(1, "/kb/test.txt", content_a)
        version_store.create_version(1, "/kb/test.txt", content_b)

        result = diff_engine.compute_diff(1, 1, 2)

        actual_additions = sum(1 for op in result.operations if op.operation == "addition")
        actual_deletions = sum(1 for op in result.operations if op.operation == "deletion")
        actual_modifications = sum(1 for op in result.operations if op.operation == "modification")

        assert result.summary.lines_added == actual_additions
        assert result.summary.lines_deleted == actual_deletions
        assert result.summary.lines_modified == actual_modifications


class TestComputeDiffErrors:
    """Tests for error handling in diff computation."""

    def test_nonexistent_version_a_raises(self, diff_engine, version_store, sample_file):
        """Should raise FileNotFoundError when version_a doesn't exist."""
        version_store.create_version(1, "/kb/test.txt", b"content")

        with pytest.raises(FileNotFoundError):
            diff_engine.compute_diff(1, 99, 1)

    def test_nonexistent_version_b_raises(self, diff_engine, version_store, sample_file):
        """Should raise FileNotFoundError when version_b doesn't exist."""
        version_store.create_version(1, "/kb/test.txt", b"content")

        with pytest.raises(FileNotFoundError):
            diff_engine.compute_diff(1, 1, 99)

    def test_both_versions_nonexistent_raises(self, diff_engine, version_store, sample_file):
        """Should raise FileNotFoundError when both versions don't exist."""
        with pytest.raises(FileNotFoundError):
            diff_engine.compute_diff(1, 1, 2)


class TestComputeDiffNonTextFiles:
    """Tests for non-text file handling via TextExtractor."""

    def test_non_utf8_content_uses_text_extractor(
        self, version_store, sample_pdf_file, db_session
    ):
        """Should use TextExtractor for non-UTF-8 content."""
        # Create a mock text extractor that returns known text
        mock_extractor = MagicMock(spec=TextExtractor)
        mock_extractor.extract.side_effect = [
            "Page 1 text from PDF v1",
            "Page 1 text from PDF v2",
        ]

        engine = DiffEngine(text_extractor=mock_extractor, version_store=version_store)

        # Create versions with binary content that is NOT valid UTF-8
        # 0xFE and 0xFF are never valid in UTF-8
        binary_content_a = b"\xfe\xff\x80\x81PDF content v1"
        binary_content_b = b"\xfe\xff\x80\x81PDF content v2"
        version_store.create_version(2, "/kb/report.pdf", binary_content_a)
        version_store.create_version(2, "/kb/report.pdf", binary_content_b)

        result = engine.compute_diff(2, 1, 2)

        # Should have called extract twice (once per version)
        assert mock_extractor.extract.call_count == 2
        # Should have detected a modification
        assert result.summary.lines_modified == 1

    def test_text_extraction_failure_raises_value_error(
        self, version_store, sample_pdf_file, db_session
    ):
        """Should raise ValueError when text extraction returns None."""
        mock_extractor = MagicMock(spec=TextExtractor)
        mock_extractor.extract.return_value = None

        engine = DiffEngine(text_extractor=mock_extractor, version_store=version_store)

        # Binary content that can't be decoded as UTF-8 (0xFE/0xFF are invalid)
        binary_content_a = b"\xfe\xff\x80\x81"
        binary_content_b = b"\xfe\xff\x82\x83"
        version_store.create_version(2, "/kb/report.pdf", binary_content_a)
        version_store.create_version(2, "/kb/report.pdf", binary_content_b)

        with pytest.raises(ValueError, match="Text extraction failed"):
            engine.compute_diff(2, 1, 2)


class TestComputeDiffTimeout:
    """Tests for the 30-second timeout enforcement."""

    def test_timeout_raises_diff_timeout_error(self, version_store, sample_file):
        """Should raise DiffTimeoutError when computation takes too long."""
        text_extractor = TextExtractor()
        engine = DiffEngine(text_extractor=text_extractor, version_store=version_store)

        # Patch _parse_diff to simulate a long-running computation
        def slow_parse(text_a, text_b):
            time.sleep(5)  # Simulate slow diff
            return DiffResult()

        version_store.create_version(1, "/kb/test.txt", b"content a")
        version_store.create_version(1, "/kb/test.txt", b"content b")

        with patch.object(engine, "_parse_diff", side_effect=slow_parse):
            with patch(
                "app.services.diff_engine.DIFF_TIMEOUT_SECONDS", 1
            ):
                # Re-create engine to pick up patched timeout
                # Instead, patch the thread join timeout directly
                pass

        # Use a more direct approach: patch the thread timeout
        original_compute = engine._compute_with_timeout

        def patched_compute(text_a, text_b):
            import app.services.diff_engine as de_module
            original_timeout = de_module.DIFF_TIMEOUT_SECONDS
            de_module.DIFF_TIMEOUT_SECONDS = 1
            try:
                # Patch _parse_diff to sleep
                original_parse = engine._parse_diff
                engine._parse_diff = slow_parse
                try:
                    return engine._compute_with_timeout.__func__(engine, text_a, text_b)  # type: ignore
                finally:
                    engine._parse_diff = original_parse
            finally:
                de_module.DIFF_TIMEOUT_SECONDS = original_timeout

        with pytest.raises(DiffTimeoutError):
            patched_compute("text a", "text b")


class TestDiffOperationStructure:
    """Tests for DiffOperation structure correctness."""

    def test_addition_has_no_old_content(self, diff_engine, version_store, sample_file):
        """Additions should have content set and old_content as None."""
        version_store.create_version(1, "/kb/test.txt", b"line 1\n")
        version_store.create_version(1, "/kb/test.txt", b"line 1\nline 2\n")

        result = diff_engine.compute_diff(1, 1, 2)

        additions = [op for op in result.operations if op.operation == "addition"]
        for op in additions:
            assert op.old_content is None
            assert op.content != ""

    def test_deletion_has_no_old_content(self, diff_engine, version_store, sample_file):
        """Deletions should have content set (the deleted line) and old_content as None."""
        version_store.create_version(1, "/kb/test.txt", b"line 1\nline 2\n")
        version_store.create_version(1, "/kb/test.txt", b"line 1\n")

        result = diff_engine.compute_diff(1, 1, 2)

        deletions = [op for op in result.operations if op.operation == "deletion"]
        for op in deletions:
            assert op.old_content is None
            assert op.content == "line 2"

    def test_modification_has_old_content(self, diff_engine, version_store, sample_file):
        """Modifications should have both content and old_content set."""
        version_store.create_version(1, "/kb/test.txt", b"line 1\nold\nline 3\n")
        version_store.create_version(1, "/kb/test.txt", b"line 1\nnew\nline 3\n")

        result = diff_engine.compute_diff(1, 1, 2)

        modifications = [op for op in result.operations if op.operation == "modification"]
        assert len(modifications) == 1
        assert modifications[0].content == "new"
        assert modifications[0].old_content == "old"

    def test_line_numbers_are_positive(self, diff_engine, version_store, sample_file):
        """All line numbers should be >= 1 (1-indexed)."""
        version_store.create_version(1, "/kb/test.txt", b"a\nb\nc\n")
        version_store.create_version(1, "/kb/test.txt", b"x\ny\nz\n")

        result = diff_engine.compute_diff(1, 1, 2)

        for op in result.operations:
            assert op.line_number >= 1
