"""Version Restore Service for restoring historical file versions.

Restores a specific historical version of a file to the filesystem,
creates a new version record with restore indicator, triggers re-embedding,
and logs the event to the audit logger.
"""

import logging
import os
import tempfile

from sqlalchemy.orm import Session

from app.models.file import File
from app.services.audit_logger import AuditEventType, AuditLogger
from app.services.embedding_queue import EmbeddingQueueService
from app.services.version_store import VersionInfo, VersionStoreService

logger = logging.getLogger(__name__)


class VersionRestoreError(Exception):
    """Base error for version restore operations."""

    pass


class FileNotFoundRestoreError(VersionRestoreError):
    """Raised when the target file does not exist or has been deleted."""

    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message)
        self.status_code = status_code


class VersionNotFoundError(VersionRestoreError):
    """Raised when the requested version does not exist."""

    def __init__(self, file_id: int, version_number: int):
        self.file_id = file_id
        self.version_number = version_number
        super().__init__(
            f"Version {version_number} not found for file {file_id}."
        )
        self.status_code = 404


class FileDeletedError(VersionRestoreError):
    """Raised when the file has been deleted from the knowledge base."""

    def __init__(self, file_id: int):
        self.file_id = file_id
        super().__init__(
            f"File {file_id} has been deleted and cannot be restored."
        )
        self.status_code = 410


class VersionRestoreService:
    """Restores historical versions of files and triggers re-embedding.

    The restore operation:
    1. Validates that the file exists and is not deleted
    2. Retrieves version content from the version archive
    3. Writes content atomically to the filesystem (temp file + os.replace)
    4. Creates a new FileVersion record with is_restore=True
    5. Triggers re-embedding via the embedding queue
    6. Logs the restore event to the audit logger

    On filesystem write failure, temp files are cleaned up and the
    current file content is preserved unchanged.
    """

    def __init__(
        self,
        db: Session,
        version_store: VersionStoreService,
        embedding_queue: EmbeddingQueueService,
        audit_logger: AuditLogger,
        kb_path: str,
    ):
        """Initialize the VersionRestoreService.

        Args:
            db: SQLAlchemy database session.
            version_store: Service for version content retrieval and creation.
            embedding_queue: Service for triggering re-embedding jobs.
            audit_logger: Service for recording audit events.
            kb_path: Absolute path to the knowledge base root directory.
        """
        self._db = db
        self._version_store = version_store
        self._embedding_queue = embedding_queue
        self._audit_logger = audit_logger
        self._kb_path = kb_path

    async def restore_version(
        self, file_id: int, version_number: int, actor: str
    ) -> VersionInfo:
        """Restore a file to a specific historical version.

        Retrieves the content from the version archive, writes it atomically
        to the filesystem, creates a new version record with restore indicator,
        triggers re-embedding, and logs the event.

        Args:
            file_id: Database ID of the file to restore.
            version_number: The version number to restore from.
            actor: The identity of the user performing the restore.

        Returns:
            VersionInfo for the newly created restore version record.

        Raises:
            FileNotFoundRestoreError: If the file does not exist in the database.
            FileDeletedError: If the file has been deleted (is_deleted=True).
            VersionNotFoundError: If the specified version does not exist.
            VersionRestoreError: If the filesystem write fails.
        """
        # 1. Validate file exists and is not deleted
        file_record = self._db.query(File).filter(File.id == file_id).first()
        if file_record is None:
            raise FileNotFoundRestoreError(
                f"File with id {file_id} not found."
            )
        if file_record.is_deleted:
            raise FileDeletedError(file_id)

        # 2. Retrieve version content from the version store
        try:
            content = self._version_store.get_version_content(
                file_id, version_number
            )
        except FileNotFoundError:
            raise VersionNotFoundError(file_id, version_number)

        # 3. Write content atomically to the filesystem
        file_path = os.path.join(self._kb_path, file_record.path)
        await self._atomic_write(file_path, content, file_id, version_number)

        # 4. Create a new FileVersion record with restore indicator
        new_version = self._version_store.create_restore_version(
            file_id=file_id,
            file_path=file_record.path,
            content=content,
            restored_from=version_number,
        )

        # 5. Trigger re-embedding via embedding queue
        content_hash = new_version.content_hash
        await self._embedding_queue.enqueue(
            file_id=file_id,
            file_path=file_record.path,
            content_hash=content_hash,
        )

        # 6. Log the restore event to the audit logger
        self._audit_logger.log(
            event_type=AuditEventType.VERSION_RESTORED,
            file_id=file_id,
            actor=actor,
            details={
                "source_version": version_number,
                "target_version": new_version.version_number,
                "content_hash": content_hash,
            },
        )

        logger.info(
            f"Restored file_id={file_id} to version {version_number} "
            f"(new version {new_version.version_number}) by actor '{actor}'"
        )

        return new_version

    async def _atomic_write(
        self, file_path: str, content: bytes, file_id: int, version_number: int
    ) -> None:
        """Write content atomically using temp file + os.replace.

        On failure, cleans up the temp file and preserves current content.

        Args:
            file_path: Absolute path to the target file.
            content: The bytes to write.
            file_id: File ID (for error logging).
            version_number: Version number being restored (for error logging).

        Raises:
            VersionRestoreError: If the write operation fails.
        """
        # Ensure directory exists
        target_dir = os.path.dirname(file_path)
        os.makedirs(target_dir, exist_ok=True)

        temp_fd = None
        temp_path = None
        try:
            # Write to a temp file in the same directory for atomic replace
            temp_fd, temp_path = tempfile.mkstemp(
                dir=target_dir, prefix=".restore_"
            )
            os.write(temp_fd, content)
            os.close(temp_fd)
            temp_fd = None  # Mark as closed

            # Atomic replace
            os.replace(temp_path, file_path)
            temp_path = None  # Mark as replaced (no cleanup needed)

        except OSError as exc:
            # Log the error
            logger.error(
                f"Filesystem write failed for file_id={file_id}, "
                f"version={version_number}: {exc}"
            )
            self._audit_logger.log(
                event_type=AuditEventType.SYSTEM_ERROR,
                file_id=file_id,
                actor="system",
                details={
                    "error": str(exc),
                    "operation": "version_restore",
                    "version_number": version_number,
                },
            )
            raise VersionRestoreError(
                f"Failed to write restored content for file {file_id}: {exc}"
            ) from exc

        finally:
            # Clean up temp file descriptor if still open
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except OSError:
                    pass
            # Clean up temp file if it still exists (write failed before replace)
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
