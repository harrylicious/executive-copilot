"""Ingestion pipeline orchestrator.

Coordinates all pipeline stages for a given ingestion job:
validation → preprocessing → chunking → embedding.

Updates job status at each stage transition, records stage logs,
and handles errors with proper failure_stage/error_code/error_message.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import turbovec_settings, ingestion_settings
from app.models.chunk import Chunk
from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.models.ingestion_stage_log import IngestionStageLog
from app.services.embedding_model import EmbeddingModel
from app.services.ingestion.access_rules import AccessRuleEnforcer
from app.services.ingestion.deduplication import DeduplicationEngine
from app.services.ingestion.normalizer import NormalizedText, TextNormalizer
from app.services.ingestion.ocr_engine import OCREngine
from app.services.ingestion.pii_redactor import PIIRedactor
from app.services.ingestion.schema_validator import SchemaValidator
from app.services.ingestion.semantic_chunker import SemanticChunker, SemanticChunkResult
from app.services.text_extractor import TextExtractor

logger = logging.getLogger(__name__)


class IngestionOrchestrator:
    """Coordinates the ingestion pipeline stages for a given job.

    Accepts a job_id and database session, loads the IngestionJob,
    and runs each stage in sequence: validation → preprocessing →
    chunking → embedding. Updates job status at each transition and
    records IngestionStageLog entries.

    On any stage failure, sets the job to the appropriate failure status
    and records failure_stage, error_code, and error_message.
    """

    def __init__(self, db: Session) -> None:
        """Initialize the orchestrator with a database session.

        Args:
            db: SQLAlchemy database session for persistence operations.
        """
        self.db = db
        self.schema_validator = SchemaValidator()
        self.deduplication_engine = DeduplicationEngine(
            similarity_threshold=ingestion_settings.dedup_similarity_threshold
        )
        self.access_rule_enforcer = AccessRuleEnforcer()
        self.ocr_engine = OCREngine()
        self.text_normalizer = TextNormalizer()
        self.pii_redactor = PIIRedactor()
        self.semantic_chunker = SemanticChunker()
        self.text_extractor = TextExtractor()

    def run_pipeline(self, job_id: str) -> None:
        """Run the full ingestion pipeline for a job.

        Loads the job from the database and executes each stage in sequence.
        On success, sets status to "completed". On failure, records the
        failure details and sets the appropriate failure status.

        Args:
            job_id: The UUID of the IngestionJob to process.
        """
        job = self.db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job is None:
            logger.error(f"IngestionJob not found: {job_id}")
            return

        file_path = Path(job.staging_path) if job.staging_path else None
        if file_path is None or not file_path.exists():
            self._fail_job(
                job,
                stage="validation",
                error_code="FILE_NOT_FOUND",
                error_message=f"Staging file not found: {job.staging_path}",
            )
            return

        try:
            # Stage 1: Validation
            self._run_validation(job, file_path)

            # Stage 2: Preprocessing
            normalized = self._run_preprocessing(job, file_path)

            # Stage 3: Chunking
            chunks = self._run_chunking(job, normalized)

            # Stage 4: Embedding
            self._run_embedding(job, chunks)

            # Mark job as completed
            self._update_job_status(job, "completed")
            job.completed_at = datetime.now(timezone.utc)
            self.db.commit()

        except _PipelineStageError:
            # Stage errors are already handled (job status updated)
            pass
        except Exception as e:
            # Unexpected error
            logger.exception(f"Unexpected error in pipeline for job {job_id}: {e}")
            current_stage = job.current_stage or "unknown"
            self._fail_job(
                job,
                stage=current_stage,
                error_code="UNEXPECTED_ERROR",
                error_message=str(e),
            )

    def _run_validation(self, job: IngestionJob, file_path: Path) -> None:
        """Run the validation stage: schema, deduplication, access rules.

        Args:
            job: The IngestionJob being processed.
            file_path: Path to the staged file.

        Raises:
            _PipelineStageError: If validation fails.
        """
        self._update_job_status(job, "validating")
        stage_log = self._start_stage_log(job, "validation")

        try:
            # Schema validation
            declared_format = Path(job.file_name).suffix.lower()
            validation_result = self.schema_validator.validate(file_path, declared_format)
            if not validation_result.is_valid:
                self._complete_stage_log(stage_log, "failed", details=validation_result.details)
                self._fail_job(
                    job,
                    stage="validation",
                    error_code=validation_result.error_code or "VALIDATION_FAILED",
                    error_message=validation_result.error_message or "Schema validation failed",
                    status="validation_failed",
                )
                raise _PipelineStageError("validation")

            # Deduplication check
            dedup_result = self.deduplication_engine.check_duplicate(file_path, self.db)
            job.content_hash = dedup_result.content_hash
            self.db.commit()

            if dedup_result.is_duplicate:
                duplicate_status = (
                    "duplicate_exact" if dedup_result.duplicate_type == "exact"
                    else "duplicate_near"
                )
                job.duplicate_of_file_id = dedup_result.duplicate_file_id
                self._complete_stage_log(stage_log, "failed", details=dedup_result.details)
                self._fail_job(
                    job,
                    stage="validation",
                    error_code=f"DUPLICATE_{dedup_result.duplicate_type.upper()}" if dedup_result.duplicate_type else "DUPLICATE",
                    error_message=(
                        f"File is a {dedup_result.duplicate_type} duplicate of "
                        f"file_id={dedup_result.duplicate_file_id}"
                    ),
                    status=duplicate_status,
                )
                raise _PipelineStageError("validation")

            # Access rule enforcement
            access_result = self.access_rule_enforcer.enforce(
                department=job.department,
                subfolder=job.subfolder,
            )
            if not access_result.is_allowed:
                self._complete_stage_log(stage_log, "failed", details=access_result.details)
                self._fail_job(
                    job,
                    stage="validation",
                    error_code=access_result.error_code or "ACCESS_DENIED",
                    error_message=access_result.error_message or "Access denied",
                    status="access_denied",
                )
                raise _PipelineStageError("validation")

            # Record sensitivity level from access check
            job.sensitivity_level = access_result.sensitivity_level
            self.db.commit()

            self._complete_stage_log(stage_log, "completed", details={
                "content_hash": dedup_result.content_hash,
                "sensitivity_level": access_result.sensitivity_level,
            })

        except _PipelineStageError:
            raise
        except Exception as e:
            self._complete_stage_log(stage_log, "failed", details={"error": str(e)})
            self._fail_job(
                job,
                stage="validation",
                error_code="VALIDATION_ERROR",
                error_message=str(e),
            )
            raise _PipelineStageError("validation") from e

    def _run_preprocessing(self, job: IngestionJob, file_path: Path) -> NormalizedText:
        """Run the preprocessing stage: text extraction, OCR, normalization, PII redaction.

        Args:
            job: The IngestionJob being processed.
            file_path: Path to the staged file.

        Returns:
            NormalizedText with the processed text and structure metadata.

        Raises:
            _PipelineStageError: If preprocessing fails.
        """
        self._update_job_status(job, "preprocessing")
        stage_log = self._start_stage_log(job, "preprocessing")

        try:
            # Step 1: Check if OCR is needed and extract text
            ocr_result = self.ocr_engine.extract_text(file_path)
            text: str | None = None

            if ocr_result.text:
                # OCR produced text (file was an image or image-only PDF)
                text = ocr_result.text
                if ocr_result.needs_manual_review:
                    logger.warning(
                        f"Job {job.id}: OCR confidence {ocr_result.confidence:.2f} "
                        f"below threshold, flagged for manual review"
                    )
            else:
                # Use standard text extraction
                declared_format = Path(job.file_name).suffix.lower()
                text = self.text_extractor.extract(file_path, declared_format)

            if text is None or not text.strip():
                self._complete_stage_log(stage_log, "failed", details={
                    "error": "No text could be extracted from the file"
                })
                self._fail_job(
                    job,
                    stage="preprocessing",
                    error_code="TEXT_EXTRACTION_FAILED",
                    error_message="No text could be extracted from the file",
                )
                raise _PipelineStageError("preprocessing")

            # Step 2: Normalize text
            normalized = self.text_normalizer.normalize(text)

            # Step 3: PII redaction
            redaction_result = self.pii_redactor.redact(normalized.text)

            # Update normalized text with redacted version
            normalized = NormalizedText(
                text=redaction_result.redacted_text,
                structure=normalized.structure,
            )

            self._complete_stage_log(stage_log, "completed", details={
                "ocr_used": bool(ocr_result.text),
                "ocr_confidence": ocr_result.confidence if ocr_result.text else None,
                "ocr_needs_review": ocr_result.needs_manual_review if ocr_result.text else False,
                "pii_spans_found": len(redaction_result.spans),
                "pii_spans_redacted": sum(
                    1 for s in redaction_result.spans if not s.flagged_for_review
                ),
                "text_length": len(normalized.text),
            })

            return normalized

        except _PipelineStageError:
            raise
        except Exception as e:
            self._complete_stage_log(stage_log, "failed", details={"error": str(e)})
            self._fail_job(
                job,
                stage="preprocessing",
                error_code="PREPROCESSING_ERROR",
                error_message=str(e),
            )
            raise _PipelineStageError("preprocessing") from e

    def _run_chunking(
        self, job: IngestionJob, normalized: NormalizedText
    ) -> list[SemanticChunkResult]:
        """Run the chunking stage using the semantic chunker.

        Args:
            job: The IngestionJob being processed.
            normalized: The normalized text with structure metadata.

        Returns:
            List of SemanticChunkResult from the chunker.

        Raises:
            _PipelineStageError: If chunking fails.
        """
        self._update_job_status(job, "chunking")
        stage_log = self._start_stage_log(job, "chunking")

        try:
            chunks = self.semantic_chunker.chunk(normalized.text, normalized.structure)

            if not chunks:
                # Empty document after preprocessing - not necessarily an error
                logger.info(f"Job {job.id}: No chunks produced (empty text after preprocessing)")

            self._complete_stage_log(stage_log, "completed", details={
                "chunks_produced": len(chunks),
                "semantic_chunks": sum(1 for c in chunks if c.chunking_method == "semantic"),
                "sliding_window_chunks": sum(1 for c in chunks if c.chunking_method == "sliding_window"),
            })

            return chunks

        except _PipelineStageError:
            raise
        except Exception as e:
            self._complete_stage_log(stage_log, "failed", details={"error": str(e)})
            self._fail_job(
                job,
                stage="chunking",
                error_code="CHUNKING_ERROR",
                error_message=str(e),
            )
            raise _PipelineStageError("chunking") from e

    def _run_embedding(
        self, job: IngestionJob, chunks: list[SemanticChunkResult]
    ) -> None:
        """Run the embedding stage: generate embeddings and store in SQLite.

        Creates a File record, generates embeddings for each chunk, and
        persists Chunk records in SQLite.

        Args:
            job: The IngestionJob being processed.
            chunks: List of SemanticChunkResult from the chunking stage.

        Raises:
            _PipelineStageError: If embedding fails.
        """
        self._update_job_status(job, "embedding")
        stage_log = self._start_stage_log(job, "embedding")

        try:
            if not chunks:
                # No chunks to embed - still create the file record
                file_record = self._create_file_record(job)
                job.file_id = file_record.id
                self.db.commit()
                self._complete_stage_log(stage_log, "completed", details={
                    "chunks_embedded": 0,
                    "file_id": file_record.id,
                })
                return

            # Step 1: Create file record in the database
            file_record = self._create_file_record(job)
            job.file_id = file_record.id
            self.db.commit()

            # Step 2: Generate embeddings
            embedding_model = EmbeddingModel(turbovec_settings.embedding_model)
            chunk_texts = [c.text for c in chunks]
            embeddings = embedding_model.embed_texts(chunk_texts)

            # Step 3: Store chunk records in SQLite
            for chunk, embedding in zip(chunks, embeddings):
                db_chunk = Chunk(
                    file_id=file_record.id,
                    chunk_index=chunk.chunk_index,
                    text=chunk.text[:10000],
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset,
                    embedding=embedding,
                    section_path=chunk.section_path,
                    chunking_method=chunk.chunking_method,
                    job_id=job.id,
                )
                self.db.add(db_chunk)

            self.db.commit()

            # Update file embedding status
            file_record.embedding_status = "embedded"
            self.db.commit()

            self._complete_stage_log(stage_log, "completed", details={
                "chunks_embedded": len(chunks),
                "file_id": file_record.id,
                "embedding_model": turbovec_settings.embedding_model,
            })

        except _PipelineStageError:
            raise
        except Exception as e:
            self._complete_stage_log(stage_log, "failed", details={"error": str(e)})
            self._fail_job(
                job,
                stage="embedding",
                error_code="EMBEDDING_ERROR",
                error_message=str(e),
            )
            raise _PipelineStageError("embedding") from e

    # ─── Helper Methods ───────────────────────────────────────────────────

    def _create_file_record(self, job: IngestionJob) -> File:
        """Create a File record in the database for the completed ingestion.

        Args:
            job: The IngestionJob to create a file record for.

        Returns:
            The created File model instance with an assigned ID.
        """
        now = datetime.now(timezone.utc)
        file_record = File(
            name=job.file_name,
            path=job.staging_path or "",
            department=job.department,
            subfolder=job.subfolder,
            file_type=Path(job.file_name).suffix.lower() if job.file_name else None,
            size=job.file_size,
            tags=[],
            created_at=now,
            modified_at=now,
            indexed_at=now,
            content_hash=job.content_hash,
            checksum_md5=job.content_hash,
            sync_status="synced",
            sensitivity_level=job.sensitivity_level or "Internal",
            is_deleted=False,
            embedding_status="pending",
        )
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        return file_record

    def _update_job_status(self, job: IngestionJob, status: str) -> None:
        """Update the job status and current_stage.

        Args:
            job: The IngestionJob to update.
            status: The new status value.
        """
        job.status = status
        job.current_stage = status if status not in ("completed", "failed") else job.current_stage
        job.updated_at = datetime.now(timezone.utc)
        self.db.commit()

    def _fail_job(
        self,
        job: IngestionJob,
        stage: str,
        error_code: str,
        error_message: str,
        status: str = "failed",
    ) -> None:
        """Mark a job as failed with error details.

        Args:
            job: The IngestionJob to mark as failed.
            stage: The pipeline stage where the failure occurred.
            error_code: Machine-readable error code.
            error_message: Human-readable error description.
            status: The failure status to set (default "failed").
        """
        job.status = status
        job.failure_stage = stage
        job.error_code = error_code
        job.error_message = error_message
        job.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.error(
            f"Job {job.id} failed at stage '{stage}': "
            f"[{error_code}] {error_message}"
        )

    def _start_stage_log(self, job: IngestionJob, stage: str) -> IngestionStageLog:
        """Create a stage log entry with status 'started'.

        Args:
            job: The IngestionJob being processed.
            stage: The pipeline stage name.

        Returns:
            The created IngestionStageLog instance.
        """
        stage_log = IngestionStageLog(
            job_id=job.id,
            stage=stage,
            status="started",
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(stage_log)
        self.db.commit()
        self.db.refresh(stage_log)
        return stage_log

    def _complete_stage_log(
        self,
        stage_log: IngestionStageLog,
        status: str,
        details: dict | None = None,
    ) -> None:
        """Update a stage log entry with completion status and details.

        Args:
            stage_log: The IngestionStageLog to update.
            status: The completion status ("completed" or "failed").
            details: Optional stage-specific metadata.
        """
        stage_log.status = status
        stage_log.completed_at = datetime.now(timezone.utc)
        stage_log.details = details
        self.db.commit()


class _PipelineStageError(Exception):
    """Internal exception to signal a handled pipeline stage failure.

    This exception is raised after the job status has already been updated
    to the appropriate failure state. It signals to run_pipeline() that
    processing should stop without additional error handling.
    """

    def __init__(self, stage: str) -> None:
        self.stage = stage
        super().__init__(f"Pipeline failed at stage: {stage}")
