"""EmbeddingEngine orchestrator for the embedding pipeline.

Coordinates document chunking, embedding generation, and SQLite
chunk persistence for files in the knowledge base.
Supports incremental, full, and single-file embedding modes.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import TurboVecSettings
from app.models.chunk import Chunk
from app.models.embedding_log import EmbeddingLog
from app.models.file import File
from app.services.document_chunker import DocumentChunker
from app.services.embedding_model import EmbeddingModel
from app.services.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingJobResult:
    """Result summary of an embedding job execution.

    Attributes:
        files_processed: Number of files that were processed (success or failure).
        chunks_generated: Total number of chunks created across all files.
        errors: List of per-file error dicts with keys: file_id, file_path, error.
        status: Overall job status - "success", "partial_success", or "error".
    """

    job_id: int = 0
    files_processed: int = 0
    chunks_generated: int = 0
    errors: list[dict] = field(default_factory=list)
    status: str = "success"


class EmbeddingEngine:
    """Orchestrates document chunking and embedding.

    Manages the embedding pipeline: text extraction, chunking, embedding
    generation, and SQLite chunk storage.

    Args:
        db: SQLAlchemy database session.
        config: TurboVec configuration settings.
    """

    def __init__(self, db: Session, config: TurboVecSettings, kb_path: str = "./knowledge_base"):
        self.db = db
        self.config = config
        self.kb_path = kb_path
        self.extractor = TextExtractor()
        self.chunker = DocumentChunker(
            config.chunk_size, config.chunk_overlap, config.embedding_model
        )
        self.model = EmbeddingModel(config.embedding_model)

    def run_incremental(self) -> EmbeddingJobResult:
        """Process files with changed content_hash or no prior embedding.

        Queries for files where embedding_status is None (never embedded)
        or "pending" (content_hash changed since last embedding), and
        processes each through the embedding pipeline.

        Returns:
            EmbeddingJobResult with counts and per-file errors.
        """
        # Find files needing embedding: never embedded or pending
        files = (
            self.db.query(File)
            .filter(
                (File.embedding_status == None)  # noqa: E711
                | (File.embedding_status == "pending")
            )
            .all()
        )

        result = self._process_files(files)
        result.job_id = self._log_job(result)
        return result

    def run_full(self) -> EmbeddingJobResult:
        """Re-embed all indexed files regardless of hash.

        Processes every file in the index through the embedding pipeline,
        ignoring content_hash comparison. Skips files that are soft-deleted
        or no longer exist on disk.

        Returns:
            EmbeddingJobResult with counts and per-file errors.
        """
        all_files = (
            self.db.query(File)
            .filter((File.is_deleted == False) | (File.is_deleted == None))  # noqa: E711, E712
            .all()
        )

        # Filter out files whose path no longer exists on disk
        files = []
        for f in all_files:
            full_path = Path(self.kb_path) / f.path
            if full_path.exists():
                files.append(f)
            else:
                logger.warning(
                    f"Skipping stale file_id={f.id} (path not found): {f.path}"
                )

        result = self._process_files(files)
        result.job_id = self._log_job(result)
        return result

    def run_single(self, file_id: int) -> EmbeddingJobResult:
        """Embed a specific file by its database ID.

        Args:
            file_id: The database ID of the file to embed.

        Returns:
            EmbeddingJobResult with counts and per-file errors.
            If the file is not found, returns an error result.
        """
        file = self.db.query(File).filter(File.id == file_id).first()

        if file is None:
            result = EmbeddingJobResult(
                files_processed=0,
                chunks_generated=0,
                errors=[{"file_id": file_id, "file_path": "", "error": "File not found"}],
                status="error",
            )
            result.job_id = self._log_job(result)
            return result

        result = self._process_files([file])
        result.job_id = self._log_job(result)
        return result

    def _process_files(self, files: list[File]) -> EmbeddingJobResult:
        """Process a list of files through the embedding pipeline.

        Handles file-level errors without halting the batch.

        Args:
            files: List of File model instances to process.

        Returns:
            EmbeddingJobResult summarizing the batch outcome.
        """
        total_chunks = 0
        errors: list[dict] = []

        for file in files:
            try:
                chunks_count, file_errors = self._process_file(file)
                total_chunks += chunks_count
                errors.extend(file_errors)
            except Exception as e:
                logger.error(
                    f"Unexpected error processing file_id={file.id} "
                    f"({file.path}): {e}"
                )
                errors.append(
                    {
                        "file_id": file.id,
                        "file_path": file.path,
                        "error": str(e),
                    }
                )

        # Determine status
        files_processed = len(files)
        files_with_errors = len({e["file_id"] for e in errors})

        if files_processed == 0:
            status = "success"
        elif files_with_errors == 0:
            status = "success"
        elif files_with_errors >= files_processed:
            status = "error"
        else:
            status = "partial_success"

        return EmbeddingJobResult(
            files_processed=files_processed,
            chunks_generated=total_chunks,
            errors=errors,
            status=status,
        )

    def _process_file(self, file: File) -> tuple[int, list[dict]]:
        """Process one file: extract → chunk → embed → store in SQLite.

        Pipeline steps:
        1. Extract text from the file
        2. Chunk the extracted text
        3. Generate embeddings for each chunk
        4. Store chunk records in SQLite

        Handles chunk-level errors without halting the file processing.

        Args:
            file: The File model instance to process.

        Returns:
            Tuple of (chunks_generated_count, list_of_error_dicts).
        """
        errors: list[dict] = []

        # Step 1: Extract text (resolve absolute path from kb_path + relative file path)
        full_path = Path(self.kb_path) / file.path
        file_format = full_path.suffix
        text = self.extractor.extract(full_path, file_format)

        if text is None:
            errors.append(
                {
                    "file_id": file.id,
                    "file_path": file.path,
                    "error": f"Text extraction failed or unsupported format: {file_format}",
                }
            )
            return 0, errors

        # Step 2: Chunk the text
        if not text.strip():
            logger.info(f"Empty text extracted for file: {file.path}")
            # Update embedding status even for empty files
            file.embedding_status = "embedded"
            self.db.commit()
            return 0, []

        chunk_results = self.chunker.chunk(text)

        if not chunk_results:
            logger.info(f"No chunks produced for file: {file.path}")
            file.embedding_status = "embedded"
            self.db.commit()
            return 0, []

        # Step 3: Generate embeddings for each chunk (handle chunk-level errors)
        chunk_texts = [c.text for c in chunk_results]
        chunk_embeddings: list[list[float] | None] = []

        for i, chunk_text in enumerate(chunk_texts):
            try:
                embedding = self.model.embed_texts([chunk_text])
                chunk_embeddings.append(embedding[0] if embedding else None)
            except Exception as e:
                logger.error(
                    f"Embedding generation failed for file_id={file.id}, "
                    f"chunk_index={i}: {e}"
                )
                chunk_embeddings.append(None)
                errors.append(
                    {
                        "file_id": file.id,
                        "file_path": file.path,
                        "error": f"Embedding failed for chunk {i}: {e}",
                    }
                )

        # Filter out chunks that failed embedding
        valid_chunks = []
        valid_embeddings = []
        for chunk_result, embedding in zip(chunk_results, chunk_embeddings):
            if embedding is not None:
                valid_chunks.append(chunk_result)
                valid_embeddings.append(embedding)

        if not valid_chunks:
            errors.append(
                {
                    "file_id": file.id,
                    "file_path": file.path,
                    "error": "All chunk embeddings failed",
                }
            )
            return 0, errors

        # Step 4: Store chunk records in SQLite
        # First remove existing chunks for this file
        self.db.query(Chunk).filter(Chunk.file_id == file.id).delete(
            synchronize_session="fetch"
        )

        # Compute document-level embedding
        doc_embedding = self._compute_document_embedding(valid_embeddings)

        db_chunks = []
        for chunk_result, embedding in zip(valid_chunks, valid_embeddings):
            db_chunk = Chunk(
                file_id=file.id,
                chunk_index=chunk_result.chunk_index,
                text=chunk_result.text[:10000],
                start_offset=chunk_result.start_offset,
                end_offset=chunk_result.end_offset,
                embedding=embedding,
            )
            self.db.add(db_chunk)
            db_chunks.append(db_chunk)

        self.db.commit()

        # Refresh to get IDs assigned
        for db_chunk in db_chunks:
            self.db.refresh(db_chunk)

        # Update file embedding status
        file.embedding_status = "embedded"
        self.db.commit()

        return len(valid_chunks), errors

    def _compute_document_embedding(
        self, chunk_embeddings: list[list[float]]
    ) -> list[float]:
        """Compute document-level embedding as element-wise mean of chunk embeddings.

        Args:
            chunk_embeddings: List of embedding vectors from all chunks.

        Returns:
            A single embedding vector representing the document, computed as
            the element-wise arithmetic mean of all chunk embeddings.
        """
        if not chunk_embeddings:
            return []

        dimension = len(chunk_embeddings[0])
        n = len(chunk_embeddings)

        # Element-wise sum then divide by count
        mean_embedding = [0.0] * dimension
        for embedding in chunk_embeddings:
            for i in range(dimension):
                mean_embedding[i] += embedding[i]

        for i in range(dimension):
            mean_embedding[i] /= n

        return mean_embedding

    def _log_job(self, result: EmbeddingJobResult) -> int:
        """Log the embedding job in the embedding_log table.

        Records timestamp, file/chunk counts, error count, and status.

        Args:
            result: The EmbeddingJobResult to log.

        Returns:
            The database ID of the created EmbeddingLog entry.
        """
        # Map job result status to log status
        log_status_map = {
            "success": "completed",
            "partial_success": "completed",
            "error": "failed",
        }
        log_status = log_status_map.get(result.status, "failed")

        log_entry = EmbeddingLog(
            timestamp=datetime.now(timezone.utc),
            files_processed=result.files_processed,
            chunks_generated=result.chunks_generated,
            errors_count=len(result.errors),
            status=log_status,
        )
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        return log_entry.id
