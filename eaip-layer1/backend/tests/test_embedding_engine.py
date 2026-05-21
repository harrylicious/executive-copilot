"""Unit tests for the EmbeddingEngine orchestrator."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import GraphRAGSettings
from app.database import Base
from app.models.chunk import Chunk
from app.models.embedding_log import EmbeddingLog
from app.models.file import File
from app.services.document_chunker import ChunkResult
from app.services.embedding_engine import EmbeddingEngine, EmbeddingJobResult


@pytest.fixture
def db_session(tmp_path):
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def config(tmp_path):
    """Create a GraphRAGSettings with a temporary vector store path."""
    return GraphRAGSettings(vector_store_path=str(tmp_path / "chroma_test"))


@pytest.fixture
def sample_file(db_session):
    """Create a sample file record in the database."""
    file = File(
        name="test.txt",
        path="knowledge_base/engineering/test.txt",
        department="engineering",
        size=100,
        tags=[],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        content_hash="abc123",
        embedding_status=None,
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture
def pending_file(db_session):
    """Create a file with pending embedding status."""
    file = File(
        name="pending.md",
        path="knowledge_base/engineering/pending.md",
        department="engineering",
        size=200,
        tags=[],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
        content_hash="def456",
        embedding_status="pending",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture
def embedded_file(db_session):
    """Create a file that has already been embedded."""
    file = File(
        name="embedded.txt",
        path="knowledge_base/engineering/embedded.txt",
        department="engineering",
        size=150,
        tags=[],
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        modified_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        content_hash="ghi789",
        embedding_status="embedded",
    )
    db_session.add(file)
    db_session.commit()
    db_session.refresh(file)
    return file


@pytest.fixture
def mock_engine(db_session, config):
    """Create an EmbeddingEngine with mocked external dependencies."""
    with patch("app.services.embedding_engine.TextExtractor") as MockExtractor, \
         patch("app.services.embedding_engine.DocumentChunker") as MockChunker, \
         patch("app.services.embedding_engine.EmbeddingModel") as MockModel, \
         patch("app.services.embedding_engine.ChromaVectorStore") as MockVectorStore, \
         patch("app.services.embedding_engine.GraphRAGEngine") as MockGraphRAG:

        mock_extractor = MockExtractor.return_value
        mock_chunker = MockChunker.return_value
        mock_model = MockModel.return_value
        mock_vector_store = MockVectorStore.return_value
        mock_graphrag = MockGraphRAG.return_value

        # Default behaviors
        mock_extractor.extract.return_value = "Hello world, this is test content."
        mock_chunker.chunk.return_value = [
            ChunkResult(text="Hello world, this is test content.", chunk_index=0, start_offset=0, end_offset=34),
        ]
        mock_model.embed_texts.return_value = [[0.1] * 384]
        mock_vector_store.upsert_chunks.return_value = None
        mock_graphrag.extract_entities_and_relationships.return_value = None

        engine = EmbeddingEngine(db_session, config)

        # Attach mocks for test access
        engine._mock_extractor = mock_extractor
        engine._mock_chunker = mock_chunker
        engine._mock_model = mock_model
        engine._mock_vector_store = mock_vector_store
        engine._mock_graphrag = mock_graphrag

        yield engine


class TestEmbeddingJobResult:
    """Tests for the EmbeddingJobResult dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        result = EmbeddingJobResult()
        assert result.files_processed == 0
        assert result.chunks_generated == 0
        assert result.errors == []
        assert result.status == "success"

    def test_custom_values(self):
        """Should accept custom values."""
        result = EmbeddingJobResult(
            files_processed=5,
            chunks_generated=20,
            errors=[{"file_id": 1, "file_path": "test.txt", "error": "fail"}],
            status="partial_success",
        )
        assert result.files_processed == 5
        assert result.chunks_generated == 20
        assert len(result.errors) == 1
        assert result.status == "partial_success"


class TestRunIncremental:
    """Tests for the run_incremental method."""

    def test_processes_files_with_no_embedding_status(self, mock_engine, db_session, sample_file):
        """Should process files where embedding_status is None."""
        result = mock_engine.run_incremental()

        assert result.files_processed == 1
        assert result.chunks_generated == 1
        assert result.status == "success"

    def test_processes_files_with_pending_status(self, mock_engine, db_session, pending_file):
        """Should process files where embedding_status is 'pending'."""
        result = mock_engine.run_incremental()

        assert result.files_processed == 1
        assert result.status == "success"

    def test_skips_already_embedded_files(self, mock_engine, db_session, embedded_file):
        """Should skip files where embedding_status is 'embedded'."""
        result = mock_engine.run_incremental()

        assert result.files_processed == 0
        assert result.chunks_generated == 0

    def test_processes_both_none_and_pending(self, mock_engine, db_session, sample_file, pending_file):
        """Should process both None and pending files."""
        result = mock_engine.run_incremental()

        assert result.files_processed == 2

    def test_logs_job_in_embedding_log(self, mock_engine, db_session, sample_file):
        """Should create an entry in the embedding_log table."""
        mock_engine.run_incremental()

        logs = db_session.query(EmbeddingLog).all()
        assert len(logs) == 1
        assert logs[0].files_processed == 1
        assert logs[0].chunks_generated == 1
        assert logs[0].status == "completed"


class TestRunFull:
    """Tests for the run_full method."""

    def test_processes_all_files(self, mock_engine, db_session, sample_file, embedded_file):
        """Should process all files regardless of embedding_status."""
        result = mock_engine.run_full()

        assert result.files_processed == 2

    def test_reprocesses_already_embedded_files(self, mock_engine, db_session, embedded_file):
        """Should re-embed files that are already embedded."""
        result = mock_engine.run_full()

        assert result.files_processed == 1
        assert result.status == "success"


class TestRunSingle:
    """Tests for the run_single method."""

    def test_processes_specific_file(self, mock_engine, db_session, sample_file):
        """Should process the file with the given ID."""
        result = mock_engine.run_single(sample_file.id)

        assert result.files_processed == 1
        assert result.status == "success"

    def test_returns_error_for_nonexistent_file(self, mock_engine, db_session):
        """Should return error result when file ID doesn't exist."""
        result = mock_engine.run_single(9999)

        assert result.files_processed == 0
        assert result.status == "error"
        assert len(result.errors) == 1
        assert result.errors[0]["error"] == "File not found"

    def test_logs_job_for_nonexistent_file(self, mock_engine, db_session):
        """Should still log the job even when file is not found."""
        mock_engine.run_single(9999)

        logs = db_session.query(EmbeddingLog).all()
        assert len(logs) == 1
        assert logs[0].status == "failed"


class TestProcessFile:
    """Tests for the _process_file pipeline."""

    def test_full_pipeline_success(self, mock_engine, db_session, sample_file):
        """Should execute the full pipeline: extract → chunk → embed → store."""
        chunks_count, errors = mock_engine._process_file(sample_file)

        assert chunks_count == 1
        assert errors == []
        # Verify vector store was called
        mock_engine._mock_vector_store.upsert_chunks.assert_called_once()
        # Verify graph extraction was triggered
        mock_engine._mock_graphrag.extract_entities_and_relationships.assert_called_once()

    def test_updates_embedding_status_on_success(self, mock_engine, db_session, sample_file):
        """Should set embedding_status to 'embedded' after success."""
        mock_engine._process_file(sample_file)

        db_session.refresh(sample_file)
        assert sample_file.embedding_status == "embedded"

    def test_stores_chunks_in_sqlite(self, mock_engine, db_session, sample_file):
        """Should persist chunk records in the database."""
        mock_engine._process_file(sample_file)

        chunks = db_session.query(Chunk).filter(Chunk.file_id == sample_file.id).all()
        assert len(chunks) == 1
        assert chunks[0].chunk_index == 0
        assert chunks[0].text == "Hello world, this is test content."

    def test_handles_extraction_failure(self, mock_engine, db_session, sample_file):
        """Should return error when text extraction fails."""
        mock_engine._mock_extractor.extract.return_value = None

        chunks_count, errors = mock_engine._process_file(sample_file)

        assert chunks_count == 0
        assert len(errors) == 1
        assert "extraction failed" in errors[0]["error"].lower() or "unsupported" in errors[0]["error"].lower()

    def test_handles_empty_text(self, mock_engine, db_session, sample_file):
        """Should handle empty extracted text gracefully."""
        mock_engine._mock_extractor.extract.return_value = "   "
        mock_engine._mock_chunker.chunk.return_value = []

        chunks_count, errors = mock_engine._process_file(sample_file)

        assert chunks_count == 0
        assert errors == []

    def test_handles_embedding_failure_per_chunk(self, mock_engine, db_session, sample_file):
        """Should continue processing when individual chunk embedding fails."""
        mock_engine._mock_chunker.chunk.return_value = [
            ChunkResult(text="Chunk 0", chunk_index=0, start_offset=0, end_offset=7),
            ChunkResult(text="Chunk 1", chunk_index=1, start_offset=7, end_offset=14),
        ]
        # First chunk succeeds, second fails
        mock_engine._mock_model.embed_texts.side_effect = [
            [[0.1] * 384],
            Exception("Model error"),
        ]

        chunks_count, errors = mock_engine._process_file(sample_file)

        # Should still process the successful chunk
        assert chunks_count == 1
        assert len(errors) == 1
        assert "chunk 1" in errors[0]["error"].lower()

    def test_handles_vector_store_failure(self, mock_engine, db_session, sample_file):
        """Should return error when vector store is unavailable."""
        mock_engine._mock_vector_store.upsert_chunks.side_effect = Exception("ChromaDB down")

        chunks_count, errors = mock_engine._process_file(sample_file)

        assert chunks_count == 0
        assert len(errors) == 1
        assert "vector store" in errors[0]["error"].lower()

    def test_handles_graph_extraction_failure(self, mock_engine, db_session, sample_file):
        """Should continue even when graph extraction fails (non-fatal)."""
        mock_engine._mock_graphrag.extract_entities_and_relationships.side_effect = Exception(
            "Graph error"
        )

        chunks_count, errors = mock_engine._process_file(sample_file)

        # Chunks should still be counted as generated
        assert chunks_count == 1
        # But there should be an error logged
        assert len(errors) == 1
        assert "graph extraction" in errors[0]["error"].lower()

    def test_removes_existing_chunks_before_storing(self, mock_engine, db_session, sample_file):
        """Should delete old chunks for the file before inserting new ones."""
        # Pre-populate with an old chunk
        old_chunk = Chunk(
            file_id=sample_file.id,
            chunk_index=0,
            text="Old content",
            start_offset=0,
            end_offset=11,
            embedding=[0.5] * 384,
        )
        db_session.add(old_chunk)
        db_session.commit()

        mock_engine._process_file(sample_file)

        chunks = db_session.query(Chunk).filter(Chunk.file_id == sample_file.id).all()
        assert len(chunks) == 1
        assert chunks[0].text == "Hello world, this is test content."


class TestComputeDocumentEmbedding:
    """Tests for the _compute_document_embedding method."""

    def test_single_embedding_returns_itself(self, mock_engine):
        """Should return the same embedding when only one chunk exists."""
        embedding = [[1.0, 2.0, 3.0]]
        result = mock_engine._compute_document_embedding(embedding)

        assert result == [1.0, 2.0, 3.0]

    def test_averages_multiple_embeddings(self, mock_engine):
        """Should compute element-wise mean of multiple embeddings."""
        embeddings = [
            [1.0, 2.0, 3.0],
            [3.0, 4.0, 5.0],
        ]
        result = mock_engine._compute_document_embedding(embeddings)

        assert len(result) == 3
        assert abs(result[0] - 2.0) < 1e-6
        assert abs(result[1] - 3.0) < 1e-6
        assert abs(result[2] - 4.0) < 1e-6

    def test_empty_embeddings_returns_empty(self, mock_engine):
        """Should return empty list for empty input."""
        result = mock_engine._compute_document_embedding([])
        assert result == []

    def test_preserves_dimension(self, mock_engine):
        """Should preserve the embedding dimension in the output."""
        embeddings = [
            [0.1] * 384,
            [0.3] * 384,
        ]
        result = mock_engine._compute_document_embedding(embeddings)

        assert len(result) == 384
        for val in result:
            assert abs(val - 0.2) < 1e-6


class TestJobStatus:
    """Tests for job status determination."""

    def test_all_success_returns_success(self, mock_engine, db_session, sample_file):
        """Should return 'success' when all files process without errors."""
        result = mock_engine.run_single(sample_file.id)
        assert result.status == "success"

    def test_all_failures_returns_error(self, mock_engine, db_session, sample_file):
        """Should return 'error' when all files fail."""
        mock_engine._mock_extractor.extract.return_value = None

        result = mock_engine.run_single(sample_file.id)
        assert result.status == "error"

    def test_partial_failure_returns_partial_success(self, mock_engine, db_session, sample_file, pending_file):
        """Should return 'partial_success' when some files fail."""
        # First file succeeds, second fails
        mock_engine._mock_extractor.extract.side_effect = [
            "Good content",
            None,
        ]

        result = mock_engine.run_incremental()
        assert result.status == "partial_success"

    def test_no_files_returns_success(self, mock_engine, db_session):
        """Should return 'success' when no files need processing."""
        result = mock_engine.run_incremental()
        assert result.status == "success"
        assert result.files_processed == 0


class TestJobLogging:
    """Tests for embedding_log table entries."""

    def test_success_job_logged_as_completed(self, mock_engine, db_session, sample_file):
        """Should log successful jobs with status 'completed'."""
        mock_engine.run_single(sample_file.id)

        log = db_session.query(EmbeddingLog).first()
        assert log.status == "completed"
        assert log.files_processed == 1
        assert log.chunks_generated == 1
        assert log.errors_count == 0

    def test_failed_job_logged_as_failed(self, mock_engine, db_session):
        """Should log failed jobs with status 'failed'."""
        mock_engine.run_single(9999)

        log = db_session.query(EmbeddingLog).first()
        assert log.status == "failed"

    def test_partial_success_logged_as_completed(self, mock_engine, db_session, sample_file, pending_file):
        """Should log partial_success jobs with status 'completed'."""
        mock_engine._mock_extractor.extract.side_effect = ["Good content", None]

        mock_engine.run_incremental()

        log = db_session.query(EmbeddingLog).first()
        assert log.status == "completed"
        assert log.errors_count == 1

    def test_log_has_timestamp(self, mock_engine, db_session, sample_file):
        """Should record a timestamp for each job."""
        mock_engine.run_single(sample_file.id)

        log = db_session.query(EmbeddingLog).first()
        assert log.timestamp is not None

    def test_each_job_creates_one_log_entry(self, mock_engine, db_session, sample_file):
        """Should create exactly one log entry per job execution."""
        mock_engine.run_single(sample_file.id)
        mock_engine.run_single(sample_file.id)

        logs = db_session.query(EmbeddingLog).all()
        assert len(logs) == 2
