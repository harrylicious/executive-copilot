"""Batch Loader for scheduled scanning of external sources.

Scans configured source paths (local filesystem or S3) for new/modified
files, filters out already-ingested files by content hash, and submits
new files to the ingestion pipeline as IngestionJobs.
"""

import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import ingestion_settings
from app.models.batch_execution_log import BatchExecutionLog
from app.models.batch_loader_config import BatchLoaderConfig
from app.models.file import File
from app.models.ingestion_job import IngestionJob
from app.services.ingestion.deduplication import DeduplicationEngine

logger = logging.getLogger(__name__)


class BatchLoader:
    """Scans external sources for new/modified files and submits them to the pipeline.

    Accepts a BatchLoaderConfig and database session, scans the configured
    source path for files modified since the last execution, filters out
    already-ingested files by content hash, and creates IngestionJobs for
    each new file.
    """

    def __init__(self, db: Session) -> None:
        """Initialize the batch loader.

        Args:
            db: SQLAlchemy database session for persistence operations.
        """
        self.db = db
        self.deduplication_engine = DeduplicationEngine(
            similarity_threshold=ingestion_settings.dedup_similarity_threshold
        )

    def _scan_local_path(
        self, path: str, last_execution_at: datetime | None
    ) -> list[Path]:
        """Scan a local directory for files modified since the last execution.

        Recursively walks the directory tree and returns paths to files
        whose modification time is after the last execution timestamp.
        If last_execution_at is None (first run), all files are returned.

        Args:
            path: Local filesystem path to scan.
            last_execution_at: Timestamp of the last successful execution,
                or None if this is the first scan.

        Returns:
            List of Path objects for new/modified files.

        Raises:
            OSError: If the path is unreachable or permission is denied.
        """
        source_path = Path(path)
        if not source_path.exists():
            raise OSError(f"Source path does not exist: {path}")
        if not source_path.is_dir():
            raise OSError(f"Source path is not a directory: {path}")

        found_files: list[Path] = []

        for root, _dirs, files in os.walk(source_path):
            for file_name in files:
                file_path = Path(root) / file_name

                # Skip hidden files and directories
                if any(part.startswith(".") for part in file_path.parts):
                    continue

                try:
                    stat = file_path.stat()
                except OSError:
                    continue

                # If no last execution, include all files
                if last_execution_at is None:
                    found_files.append(file_path)
                else:
                    # Compare modification time against last execution
                    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                    if mtime > last_execution_at:
                        found_files.append(file_path)

        return found_files

    def _scan_s3_uri(self, uri: str) -> list[Path]:
        """Scan an S3 URI for new/modified files.

        This is a stub implementation that raises NotImplementedError.
        S3 scanning will be implemented in a future iteration.

        Args:
            uri: S3 URI in the format s3://bucket/prefix.

        Raises:
            NotImplementedError: Always raised; S3 scanning is not yet implemented.
        """
        raise NotImplementedError(
            f"S3 source scanning is not yet implemented. URI: {uri}"
        )

    def _is_already_ingested(self, file_path: Path) -> bool:
        """Check if a file has already been ingested by comparing content hash.

        Computes the MD5 hash of the file and checks if it exists in either
        the IngestionJob table or the File table (content_hash field).

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file's content hash already exists in the tracking
            store (already ingested), False otherwise.
        """
        content_hash = self.deduplication_engine.compute_content_hash(file_path)

        # Check IngestionJob table for existing hash (non-failed jobs)
        existing_job = (
            self.db.query(IngestionJob)
            .filter(IngestionJob.content_hash == content_hash)
            .filter(
                IngestionJob.status.notin_(
                    ["failed", "validation_failed", "access_denied"]
                )
            )
            .first()
        )
        if existing_job is not None:
            return True

        # Check File table for existing hash (non-deleted files)
        existing_file = (
            self.db.query(File)
            .filter(File.content_hash == content_hash)
            .filter(File.is_deleted == False)  # noqa: E712
            .first()
        )
        if existing_file is not None:
            return True

        return False

    def execute_scan(self, config_id: str) -> BatchExecutionLog:
        """Execute a batch scan for the given configuration.

        Orchestrates the full scan workflow:
        1. Load the BatchLoaderConfig from the database.
        2. Determine source type and scan for files.
        3. Filter out already-ingested files by content hash.
        4. Create an IngestionJob for each new file (copy to staging, set status "queued").
        5. Record execution results in a BatchExecutionLog.

        Handles errors gracefully: if one file fails, continues with others
        and logs the error.

        Args:
            config_id: The UUID of the BatchLoaderConfig to execute.

        Returns:
            BatchExecutionLog recording the execution results.
        """
        now = datetime.now(timezone.utc)

        # Load configuration
        config = (
            self.db.query(BatchLoaderConfig)
            .filter(BatchLoaderConfig.id == config_id)
            .first()
        )
        if config is None:
            # Create a failed execution log for missing config
            execution_log = BatchExecutionLog(
                config_id=config_id,
                started_at=now,
                completed_at=datetime.now(timezone.utc),
                files_found=0,
                files_submitted=0,
                files_skipped=0,
                errors=[{"error": f"Configuration not found: {config_id}"}],
                status="failed",
            )
            self.db.add(execution_log)
            self.db.commit()
            self.db.refresh(execution_log)
            return execution_log

        # Create execution log entry (status: running)
        execution_log = BatchExecutionLog(
            config_id=config_id,
            started_at=now,
            files_found=0,
            files_submitted=0,
            files_skipped=0,
            errors=None,
            status="running",
        )
        self.db.add(execution_log)
        self.db.commit()
        self.db.refresh(execution_log)

        errors: list[dict] = []
        files_found = 0
        files_submitted = 0
        files_skipped = 0

        try:
            # Step 1: Scan for files based on source type
            if config.source_type == "local":
                found_files = self._scan_local_path(
                    config.source_path, config.last_execution_at
                )
            elif config.source_type == "s3":
                found_files = self._scan_s3_uri(config.source_path)
            else:
                raise ValueError(f"Unsupported source type: {config.source_type}")

            files_found = len(found_files)

            # Step 2: Filter and submit each file
            for file_path in found_files:
                try:
                    # Check if already ingested
                    if self._is_already_ingested(file_path):
                        files_skipped += 1
                        continue

                    # Copy file to staging area and create IngestionJob
                    self._submit_file(file_path, config)
                    files_submitted += 1

                except Exception as e:
                    error_detail = {
                        "file": str(file_path),
                        "error": str(e),
                    }
                    errors.append(error_detail)
                    logger.error(
                        f"Batch loader error processing '{file_path}': {e}"
                    )

            # Update execution log with results
            execution_log.files_found = files_found
            execution_log.files_submitted = files_submitted
            execution_log.files_skipped = files_skipped
            execution_log.errors = errors if errors else None
            execution_log.status = "completed"
            execution_log.completed_at = datetime.now(timezone.utc)

            # Update config with last execution info
            config.last_execution_at = now
            config.last_execution_status = "completed"

            self.db.commit()

        except Exception as e:
            # Top-level scan failure (e.g., source unreachable)
            logger.error(
                f"Batch scan failed for config '{config_id}': {e}"
            )
            errors.append({"error": str(e)})

            execution_log.files_found = files_found
            execution_log.files_submitted = files_submitted
            execution_log.files_skipped = files_skipped
            execution_log.errors = errors
            execution_log.status = "failed"
            execution_log.completed_at = datetime.now(timezone.utc)

            # Update config with last execution info
            config.last_execution_at = now
            config.last_execution_status = "failed"

            self.db.commit()

        self.db.refresh(execution_log)
        return execution_log

    def _submit_file(self, file_path: Path, config: BatchLoaderConfig) -> None:
        """Copy a file to the staging area and create an IngestionJob.

        Args:
            file_path: Path to the source file.
            config: The BatchLoaderConfig providing department/subfolder metadata.
        """
        # Ensure staging directory exists
        staging_dir = Path(ingestion_settings.staging_path)
        staging_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique staging filename
        job_id = str(uuid.uuid4())
        staging_filename = f"{job_id}_{file_path.name}"
        staging_path = staging_dir / staging_filename

        # Copy file to staging
        shutil.copy2(str(file_path), str(staging_path))

        # Get file size
        file_size = staging_path.stat().st_size

        # Create IngestionJob
        now = datetime.now(timezone.utc)
        job = IngestionJob(
            id=job_id,
            file_name=file_path.name,
            file_size=file_size,
            department=config.department,
            subfolder=config.subfolder,
            status="queued",
            staging_path=str(staging_path),
            created_at=now,
            updated_at=now,
        )
        self.db.add(job)
        self.db.commit()

        logger.info(
            f"Batch loader submitted file '{file_path.name}' as job {job_id}"
        )
