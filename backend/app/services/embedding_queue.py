"""EmbeddingQueueService for managing async embedding jobs with FIFO ordering.

Provides a configurable-concurrency queue that processes embedding jobs
triggered by file change events, with deduplication, cancellation, and
retry logic with exponential backoff.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session

from app.config import TurboVecSettings, turbovec_settings, settings
from app.database import SessionLocal
from app.models.chunk import Chunk
from app.models.file import File
from app.services.embedding_engine import EmbeddingEngine

logger = logging.getLogger(__name__)


class JobStatus(Enum):
    """Status of an embedding job in the queue."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EmbeddingJob:
    """Represents a single embedding job in the queue."""

    file_id: int
    file_path: str
    content_hash: str
    retry_count: int = 0
    max_retries: int = 3
    status: JobStatus = field(default=JobStatus.QUEUED)
    cancelled: bool = False


# Exponential backoff delays in seconds for retries (5s, 15s, 45s)
RETRY_DELAYS = [5, 15, 45]


class EmbeddingQueueService:
    """Manages a FIFO queue of embedding jobs with configurable concurrency.

    Features:
    - FIFO ordering via asyncio.Queue
    - Configurable concurrency (1-10, default 3) via asyncio.Semaphore
    - Job deduplication: new job for same file cancels existing job
    - Retry with exponential backoff (5s, 15s, 45s)
    - Integration with EmbeddingEngine.run_single() for processing
    - File embedding_status updates at each stage
    - Deletion handling: removes all chunks for deleted files
    """

    def __init__(
        self,
        concurrency: int = 3,
        max_concurrency: int = 10,
        embedding_engine: EmbeddingEngine | None = None,
        config: TurboVecSettings | None = None,
        kb_path: str | None = None,
    ):
        """Initialize the embedding queue service.

        Args:
            concurrency: Number of parallel embedding jobs (1-10, default 3).
            max_concurrency: Maximum allowed concurrency value.
            embedding_engine: Optional pre-configured EmbeddingEngine instance.
            config: TurboVec settings for creating EmbeddingEngine if not provided.
            kb_path: Knowledge base path for EmbeddingEngine initialization.
        """
        # Clamp concurrency to valid range
        self._concurrency = max(1, min(concurrency, max_concurrency))
        self._max_concurrency = max_concurrency

        self._queue: asyncio.Queue[EmbeddingJob] = asyncio.Queue()
        self._semaphore = asyncio.Semaphore(self._concurrency)

        # Track jobs by file_id for deduplication/cancellation
        self._active_jobs: dict[int, EmbeddingJob] = {}

        # Track completed/failed counts
        self._completed_count: int = 0
        self._failed_count: int = 0

        # Lifecycle
        self._running: bool = False
        self._workers: list[asyncio.Task] = []

        # Embedding engine configuration
        self._embedding_engine = embedding_engine
        self._config = config or turbovec_settings
        self._kb_path = kb_path or settings.knowledge_base_path

    async def enqueue(self, file_id: int, file_path: str, content_hash: str) -> None:
        """Add a file to the embedding queue. Cancels existing jobs for same file.

        Args:
            file_id: Database ID of the file to embed.
            file_path: Relative path of the file.
            content_hash: MD5 hash of the current file content.
        """
        # Cancel any existing job for this file
        await self.cancel_file(file_id)

        # Create new job
        job = EmbeddingJob(
            file_id=file_id,
            file_path=file_path,
            content_hash=content_hash,
        )

        # Track the job
        self._active_jobs[file_id] = job

        # Update file status to "pending" in the database
        self._update_embedding_status(file_id, "pending")

        # Add to FIFO queue
        await self._queue.put(job)
        logger.info(
            f"Enqueued embedding job for file_id={file_id}, path={file_path}"
        )

    async def cancel_file(self, file_id: int) -> None:
        """Cancel any queued/processing job for the given file.

        Args:
            file_id: Database ID of the file whose job should be cancelled.
        """
        if file_id in self._active_jobs:
            existing_job = self._active_jobs[file_id]
            existing_job.cancelled = True
            existing_job.status = JobStatus.CANCELLED
            del self._active_jobs[file_id]
            logger.info(f"Cancelled existing job for file_id={file_id}")

    async def delete_file_chunks(self, file_id: int) -> None:
        """Remove all chunks for a file from the database (deletion event).

        Args:
            file_id: Database ID of the file whose chunks should be removed.
        """
        # Cancel any pending/processing job first
        await self.cancel_file(file_id)

        db: Session = SessionLocal()
        try:
            deleted_count = (
                db.query(Chunk).filter(Chunk.file_id == file_id).delete(
                    synchronize_session="fetch"
                )
            )
            # Clear embedding status
            file = db.query(File).filter(File.id == file_id).first()
            if file:
                file.embedding_status = None
            db.commit()
            logger.info(
                f"Deleted {deleted_count} chunks for file_id={file_id} (file deleted)"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting chunks for file_id={file_id}: {e}")
        finally:
            db.close()

    async def start(self) -> None:
        """Start processing the queue with configured concurrency."""
        if self._running:
            logger.warning("EmbeddingQueueService is already running")
            return

        self._running = True
        # Start worker tasks based on concurrency
        for i in range(self._concurrency):
            worker = asyncio.create_task(self._worker(i))
            self._workers.append(worker)

        logger.info(
            f"EmbeddingQueueService started with concurrency={self._concurrency}"
        )

    async def stop(self) -> None:
        """Gracefully stop processing after current jobs complete."""
        if not self._running:
            return

        self._running = False

        # Cancel all worker tasks
        for worker in self._workers:
            worker.cancel()

        # Wait for workers to finish (with timeout)
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)

        self._workers.clear()
        logger.info("EmbeddingQueueService stopped")

    def get_queue_status(self) -> dict:
        """Return counts by status: queued, processing, completed, failed.

        Returns:
            Dictionary with counts for each job status category.
        """
        queued = 0
        processing = 0

        for job in self._active_jobs.values():
            if job.status == JobStatus.QUEUED:
                queued += 1
            elif job.status == JobStatus.PROCESSING:
                processing += 1

        return {
            "queued": queued,
            "processing": processing,
            "completed": self._completed_count,
            "failed": self._failed_count,
        }

    async def _worker(self, worker_id: int) -> None:
        """Worker coroutine that processes jobs from the queue.

        Args:
            worker_id: Identifier for this worker (for logging).
        """
        while self._running:
            try:
                # Wait for a job with timeout so we can check _running flag
                try:
                    job = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                # Skip cancelled jobs
                if job.cancelled:
                    self._queue.task_done()
                    continue

                # Acquire semaphore for concurrency control
                async with self._semaphore:
                    await self._process_job(job)

                self._queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} encountered error: {e}")

    async def _process_job(self, job: EmbeddingJob) -> None:
        """Process a single embedding job with retry logic.

        Args:
            job: The embedding job to process.
        """
        # Check if job was cancelled while waiting
        if job.cancelled:
            return

        job.status = JobStatus.PROCESSING

        # Update file status to "embedding"
        self._update_embedding_status(job.file_id, "embedding")

        try:
            # Run the embedding engine in a thread pool to avoid blocking
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_embedding, job.file_id
            )

            # Check cancellation after processing
            if job.cancelled:
                return

            if result.status == "error":
                await self._handle_failure(job, result.errors)
            else:
                # Success
                job.status = JobStatus.COMPLETED
                self._completed_count += 1
                # Remove from active tracking
                if job.file_id in self._active_jobs:
                    del self._active_jobs[job.file_id]
                # Status is already set to "embedded" by EmbeddingEngine._process_file
                logger.info(
                    f"Embedding completed for file_id={job.file_id}, "
                    f"chunks={result.chunks_generated}"
                )

        except Exception as e:
            logger.error(
                f"Unexpected error processing file_id={job.file_id}: {e}"
            )
            await self._handle_failure(
                job, [{"file_id": job.file_id, "error": str(e)}]
            )

    async def _handle_failure(self, job: EmbeddingJob, errors: list[dict]) -> None:
        """Handle a failed embedding job with retry logic.

        Implements exponential backoff: 5s, 15s, 45s before permanent failure.

        Args:
            job: The failed job.
            errors: List of error dictionaries from the embedding result.
        """
        job.retry_count += 1

        if job.retry_count < job.max_retries:
            # Retry with exponential backoff
            delay = RETRY_DELAYS[min(job.retry_count - 1, len(RETRY_DELAYS) - 1)]
            logger.warning(
                f"Embedding failed for file_id={job.file_id} "
                f"(attempt {job.retry_count}/{job.max_retries}), "
                f"retrying in {delay}s. Errors: {errors}"
            )

            # Wait before retrying
            await asyncio.sleep(delay)

            # Check if cancelled during sleep
            if job.cancelled:
                return

            # Reset status and requeue
            job.status = JobStatus.QUEUED
            self._update_embedding_status(job.file_id, "pending")
            await self._queue.put(job)
        else:
            # Permanently failed
            job.status = JobStatus.FAILED
            self._failed_count += 1
            self._update_embedding_status(job.file_id, "failed")
            # Remove from active tracking
            if job.file_id in self._active_jobs:
                del self._active_jobs[job.file_id]
            logger.error(
                f"Embedding permanently failed for file_id={job.file_id} "
                f"after {job.max_retries} retries. Errors: {errors}"
            )

    def _run_embedding(self, file_id: int) -> "EmbeddingEngine":
        """Run the embedding engine for a single file (blocking, runs in executor).

        Creates a new DB session for thread safety.

        Args:
            file_id: Database ID of the file to embed.

        Returns:
            EmbeddingJobResult from the engine.
        """
        from app.services.embedding_engine import EmbeddingJobResult

        db: Session = SessionLocal()
        try:
            if self._embedding_engine is not None:
                # Use the provided engine (for testing or pre-configured scenarios)
                return self._embedding_engine.run_single(file_id)
            else:
                # Create a fresh engine with its own session
                engine = EmbeddingEngine(
                    db=db, config=self._config, kb_path=self._kb_path
                )
                return engine.run_single(file_id)
        except Exception as e:
            logger.error(f"Embedding engine error for file_id={file_id}: {e}")
            return EmbeddingJobResult(
                files_processed=0,
                chunks_generated=0,
                errors=[{"file_id": file_id, "error": str(e)}],
                status="error",
            )
        finally:
            db.close()

    def _update_embedding_status(self, file_id: int, status: str) -> None:
        """Update the embedding_status field for a file in the database.

        Args:
            file_id: Database ID of the file.
            status: New embedding status value.
        """
        db: Session = SessionLocal()
        try:
            file = db.query(File).filter(File.id == file_id).first()
            if file:
                file.embedding_status = status
                db.commit()
                logger.debug(
                    f"Updated embedding_status for file_id={file_id} to '{status}'"
                )
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to update embedding_status for file_id={file_id}: {e}"
            )
        finally:
            db.close()

    async def enqueue_stale(
        self, file_id: int, file_path: str, content_hash: str
    ) -> None:
        """Enqueue a modified file, setting status to 'stale' first.

        Used for file-modified events where existing embeddings should be
        retained until new ones are generated.

        Args:
            file_id: Database ID of the file.
            file_path: Relative path of the file.
            content_hash: MD5 hash of the new file content.
        """
        # Cancel existing job
        await self.cancel_file(file_id)

        # Set status to "stale" (retains existing embeddings)
        self._update_embedding_status(file_id, "stale")

        # Create and enqueue new job
        job = EmbeddingJob(
            file_id=file_id,
            file_path=file_path,
            content_hash=content_hash,
        )
        self._active_jobs[file_id] = job
        await self._queue.put(job)
        logger.info(
            f"Enqueued stale embedding job for file_id={file_id}, path={file_path}"
        )
