"""Unit tests for the DeduplicationEngine service."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.services.ingestion.deduplication import (
    DeduplicationEngine,
    DeduplicationResult,
    MinHashSignature,
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def engine():
    """Create a DeduplicationEngine instance with default threshold."""
    return DeduplicationEngine(similarity_threshold=0.9)


@pytest.fixture
def temp_file():
    """Create a temporary file and clean up after test."""
    files = []

    def _create(content: str, suffix: str = ".txt") -> Path:
        tf = tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        )
        tf.write(content)
        tf.close()
        files.append(Path(tf.name))
        return Path(tf.name)

    yield _create

    for f in files:
        f.unlink(missing_ok=True)


class TestComputeContentHash:
    """Tests for compute_content_hash method."""

    def test_identical_content_produces_same_hash(self, engine, temp_file):
        """Two files with identical content should have the same MD5 hash."""
        content = "Hello, world! This is test content."
        file1 = temp_file(content)
        file2 = temp_file(content)

        hash1 = engine.compute_content_hash(file1)
        hash2 = engine.compute_content_hash(file2)

        assert hash1 == hash2

    def test_different_content_produces_different_hash(self, engine, temp_file):
        """Two files with different content should have different MD5 hashes."""
        file1 = temp_file("Content A")
        file2 = temp_file("Content B")

        hash1 = engine.compute_content_hash(file1)
        hash2 = engine.compute_content_hash(file2)

        assert hash1 != hash2

    def test_hash_is_hex_string(self, engine, temp_file):
        """Content hash should be a valid hexadecimal string."""
        file = temp_file("Some content")
        hash_val = engine.compute_content_hash(file)

        assert len(hash_val) == 32  # MD5 hex digest is 32 chars
        assert all(c in "0123456789abcdef" for c in hash_val)

    def test_empty_file_has_consistent_hash(self, engine, temp_file):
        """An empty file should produce a consistent hash."""
        file1 = temp_file("")
        file2 = temp_file("")

        assert engine.compute_content_hash(file1) == engine.compute_content_hash(file2)


class TestComputeMinHash:
    """Tests for compute_minhash method."""

    def test_identical_text_produces_identical_signature(self, engine):
        """Identical text should produce identical MinHash signatures."""
        text = "This is a test document with enough content for shingles."
        sig1 = engine.compute_minhash(text)
        sig2 = engine.compute_minhash(text)

        assert sig1.values == sig2.values

    def test_signature_has_correct_length(self, engine):
        """MinHash signature should have the expected number of permutations."""
        sig = engine.compute_minhash("Some text content here.")
        assert len(sig.values) == 128
        assert sig.num_perm == 128

    def test_very_short_text_still_produces_signature(self, engine):
        """Even very short text should produce a valid signature."""
        sig = engine.compute_minhash("Hi")
        assert len(sig.values) == 128

    def test_empty_text_produces_signature(self, engine):
        """Empty text should still produce a valid signature."""
        sig = engine.compute_minhash("")
        assert len(sig.values) == 128


class TestEstimateSimilarity:
    """Tests for estimate_similarity method."""

    def test_identical_signatures_have_similarity_one(self, engine):
        """Identical signatures should have similarity 1.0."""
        text = "A document about machine learning and AI."
        sig = engine.compute_minhash(text)
        assert engine.estimate_similarity(sig, sig) == 1.0

    def test_completely_different_texts_have_low_similarity(self, engine):
        """Completely different texts should have low similarity."""
        sig1 = engine.compute_minhash(
            "Machine learning is a subset of artificial intelligence "
            "that focuses on building systems that learn from data."
        )
        sig2 = engine.compute_minhash(
            "Cooking recipes involve combining ingredients in specific "
            "proportions and applying heat for certain durations."
        )
        similarity = engine.estimate_similarity(sig1, sig2)
        assert similarity < 0.5

    def test_similar_texts_have_high_similarity(self, engine):
        """Very similar texts should have high similarity."""
        base = (
            "This is a comprehensive document about machine learning and "
            "artificial intelligence. It covers topics such as neural networks, "
            "deep learning, natural language processing, and computer vision. "
            "The field has seen tremendous growth in recent years with applications "
            "in healthcare, finance, and autonomous vehicles. Researchers continue "
            "to push the boundaries of what is possible."
        )
        modified = base.replace("tremendous", "significant")

        sig1 = engine.compute_minhash(base)
        sig2 = engine.compute_minhash(modified)
        similarity = engine.estimate_similarity(sig1, sig2)

        assert similarity > 0.9

    def test_mismatched_num_perm_raises_error(self, engine):
        """Comparing signatures with different num_perm should raise ValueError."""
        sig1 = MinHashSignature(values=[1, 2, 3], num_perm=3)
        sig2 = MinHashSignature(values=[1, 2, 3, 4], num_perm=4)

        with pytest.raises(ValueError, match="different num_perm"):
            engine.estimate_similarity(sig1, sig2)


class TestFindNearDuplicates:
    """Tests for find_near_duplicates method."""

    def test_no_duplicates_in_empty_db(self, engine, db_session):
        """No near-duplicates should be found in an empty database."""
        sig = engine.compute_minhash("Some document text.")
        result = engine.find_near_duplicates(sig, db_session)
        assert result == []

    def test_finds_near_duplicate_above_threshold(self, engine, db_session):
        """Should find near-duplicates when similarity exceeds threshold."""
        original_text = (
            "This is a comprehensive document about machine learning and "
            "artificial intelligence. It covers topics such as neural networks, "
            "deep learning, natural language processing, and computer vision. "
            "The field has seen tremendous growth in recent years with applications "
            "in healthcare, finance, and autonomous vehicles. Researchers continue "
            "to push the boundaries of what is possible with these technologies."
        )
        existing = File(
            name="original.txt",
            path="/kb/original.txt",
            department="finance",
            size=len(original_text),
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash="abc123",
            extracted_text=original_text,
            is_deleted=False,
        )
        db_session.add(existing)
        db_session.commit()

        # Create a near-duplicate (one word changed)
        near_dup_text = original_text.replace("tremendous", "significant")
        sig = engine.compute_minhash(near_dup_text)

        result = engine.find_near_duplicates(sig, db_session)
        assert existing.id in result

    def test_does_not_find_different_document(self, engine, db_session):
        """Should not flag genuinely different documents as near-duplicates."""
        existing = File(
            name="original.txt",
            path="/kb/original.txt",
            department="finance",
            size=100,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash="abc123",
            extracted_text="Document about cooking and recipes for Italian food.",
            is_deleted=False,
        )
        db_session.add(existing)
        db_session.commit()

        sig = engine.compute_minhash(
            "Machine learning algorithms process large datasets efficiently."
        )
        result = engine.find_near_duplicates(sig, db_session)
        assert result == []

    def test_skips_deleted_files(self, engine, db_session):
        """Should not compare against deleted files."""
        existing = File(
            name="deleted.txt",
            path="/kb/deleted.txt",
            department="finance",
            size=100,
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash="abc123",
            extracted_text="Some text content that was deleted.",
            is_deleted=True,
        )
        db_session.add(existing)
        db_session.commit()

        sig = engine.compute_minhash("Some text content that was deleted.")
        result = engine.find_near_duplicates(sig, db_session)
        assert result == []


class TestCheckDuplicate:
    """Tests for check_duplicate orchestration method."""

    def test_no_duplicate_returns_false(self, engine, db_session, temp_file):
        """Should return not-duplicate when no matching files exist."""
        file = temp_file("Unique content that doesn't exist in the database.")
        result = engine.check_duplicate(file, db_session)

        assert result.is_duplicate is False
        assert result.duplicate_type is None
        assert result.content_hash != ""

    def test_exact_duplicate_detected(self, engine, db_session, temp_file):
        """Should detect exact duplicate when content hash matches."""
        content = "Exact duplicate content for testing."
        file = temp_file(content)
        content_hash = engine.compute_content_hash(file)

        existing = File(
            name="existing.txt",
            path="/kb/existing.txt",
            department="finance",
            size=len(content),
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash=content_hash,
            is_deleted=False,
        )
        db_session.add(existing)
        db_session.commit()

        result = engine.check_duplicate(file, db_session)

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.duplicate_file_id == existing.id
        assert result.content_hash == content_hash

    def test_near_duplicate_detected(self, engine, db_session, temp_file):
        """Should detect near-duplicate when MinHash similarity exceeds threshold."""
        original_text = (
            "This is a comprehensive document about machine learning and "
            "artificial intelligence. It covers topics such as neural networks, "
            "deep learning, natural language processing, and computer vision. "
            "The field has seen tremendous growth in recent years with applications "
            "in healthcare, finance, and autonomous vehicles. Researchers continue "
            "to push the boundaries of what is possible with these technologies."
        )
        existing = File(
            name="original.txt",
            path="/kb/original.txt",
            department="finance",
            size=len(original_text),
            created_at=datetime.now(),
            modified_at=datetime.now(),
            content_hash="different_hash_value",
            extracted_text=original_text,
            is_deleted=False,
        )
        db_session.add(existing)
        db_session.commit()

        # Create a near-duplicate file (one word changed)
        near_dup_text = original_text.replace("tremendous", "significant")
        file = temp_file(near_dup_text)

        result = engine.check_duplicate(file, db_session)

        assert result.is_duplicate is True
        assert result.duplicate_type == "near"
        assert result.duplicate_file_id == existing.id
        assert result.similarity_score is not None
        assert result.similarity_score >= 0.9

    def test_result_includes_content_hash(self, engine, db_session, temp_file):
        """Result should always include the computed content hash."""
        file = temp_file("Any content here.")
        result = engine.check_duplicate(file, db_session)

        assert result.content_hash != ""
        assert len(result.content_hash) == 32

    def test_nonexistent_file_returns_not_duplicate(self, engine, db_session):
        """Should handle nonexistent file gracefully."""
        result = engine.check_duplicate(Path("/nonexistent/file.txt"), db_session)

        assert result.is_duplicate is False
        assert result.content_hash == ""
