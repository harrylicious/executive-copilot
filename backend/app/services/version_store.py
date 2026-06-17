"""Version Store service for managing file version history.

Stores content snapshots in an archive directory, enforces size limits,
verifies write integrity, and provides version retrieval and pagination.
"""

import hashlib
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.file import File
from app.models.file_version import FileVersion


# 500 MB file size limit in bytes
MAX_FILE_SIZE_BYTES = 524_288_000


@dataclass
class VersionInfo:
    """Represents metadata about a specific file version."""

    version_number: int
    content_hash: str
    file_size: int
    timestamp: datetime
    is_restore: bool = False
    restored_from_version: int | None = None


class VersionStoreService:
    """Manages file version history with content snapshots and integrity checks.

    Content snapshots are stored in an archive directory structured as:
        {archive_dir}/{file_id}/{version_number}

    MD5 hashing is used for content deduplication (consistent with the
    existing content_hash field on the File model).
    """

    def __init__(self, db: Session, archive_dir: str):
        """Initialize the VersionStoreService.

        Args:
            db: SQLAlchemy database session.
            archive_dir: Base path for the version archive directory
                         (typically {kb_path}/.versions).
        """
        self._db = db
        self._archive_dir = archive_dir

    @staticmethod
    def _compute_md5(content: bytes) -> str:
        """Compute MD5 hash of content bytes."""
        return hashlib.md5(content).hexdigest()

    def _get_archive_path(self, file_id: int, version_number: int) -> str:
        """Build the archive file path for a given file version."""
        return os.path.join(self._archive_dir, str(file_id), str(version_number))

    def _get_next_version_number(self, file_id: int) -> int:
        """Get the next version number for a file (MAX + 1, or 1 if none exist)."""
        result = (
            self._db.query(func.max(FileVersion.version_number))
            .filter(FileVersion.file_id == file_id)
            .scalar()
        )
        return (result or 0) + 1

    def _write_content(self, archive_path: str, content: bytes) -> bool:
        """Write content to the archive path with integrity verification.

        After writing, re-hashes the written file and compares against
        the expected hash. Deletes the file on mismatch.

        Args:
            archive_path: Destination file path.
            content: The bytes to write.

        Returns:
            True if write succeeded and integrity check passed, False otherwise.
        """
        os.makedirs(os.path.dirname(archive_path), exist_ok=True)

        try:
            with open(archive_path, "wb") as f:
                f.write(content)
        except OSError as exc:
            print(
                f"[VersionStore] Disk write failed for {archive_path}: {exc}",
                file=sys.stderr,
            )
            return False

        # Integrity verification: re-read and compare hash
        expected_hash = self._compute_md5(content)
        try:
            with open(archive_path, "rb") as f:
                written_content = f.read()
            actual_hash = self._compute_md5(written_content)
        except OSError as exc:
            print(
                f"[VersionStore] Integrity read failed for {archive_path}: {exc}",
                file=sys.stderr,
            )
            self._safe_delete(archive_path)
            return False

        if actual_hash != expected_hash:
            print(
                f"[VersionStore] Integrity check failed for {archive_path}: "
                f"expected {expected_hash}, got {actual_hash}",
                file=sys.stderr,
            )
            self._safe_delete(archive_path)
            return False

        return True

    @staticmethod
    def _safe_delete(path: str) -> None:
        """Delete a file, ignoring errors."""
        try:
            os.remove(path)
        except OSError:
            pass

    def create_version(
        self, file_id: int, file_path: str, content: bytes
    ) -> VersionInfo | None:
        """Create a new version if content hash differs from the latest.

        Computes MD5 hash, compares against latest version, creates a
        FileVersion record only if hash differs. Stores content snapshot
        in the archive directory.

        Args:
            file_id: The database ID of the file.
            file_path: The relative file path (stored for reference).
            content: The file content bytes.

        Returns:
            VersionInfo if a new version was created, None if content is
            a duplicate of the latest version.

        Raises:
            ValueError: If file exceeds the 500 MB size limit.
            OSError: Re-raised if disk space errors prevent version creation.
        """
        # Enforce file size limit
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(content)} bytes exceeds the "
                f"{MAX_FILE_SIZE_BYTES} byte (500 MB) limit."
            )

        content_hash = self._compute_md5(content)

        # Compare against latest version
        latest = self.get_latest_version(file_id)
        if latest is not None and latest.content_hash == content_hash:
            return None

        # Assign next version number within the current session/transaction
        version_number = self._get_next_version_number(file_id)
        archive_path = self._get_archive_path(file_id, version_number)

        # Write content to archive with integrity verification
        if not self._write_content(archive_path, content):
            raise OSError(
                f"Failed to write version archive for file {file_id} "
                f"version {version_number}."
            )

        timestamp = datetime.now(timezone.utc)

        # Create database record
        version_record = FileVersion(
            file_id=file_id,
            version_number=version_number,
            content_hash=content_hash,
            file_size=len(content),
            timestamp=timestamp,
            archive_path=archive_path,
            is_restore=False,
            restored_from_version=None,
        )
        self._db.add(version_record)

        # Update current_version on the File model
        self._db.query(File).filter(File.id == file_id).update(
            {"current_version": version_number}
        )

        self._db.commit()

        return VersionInfo(
            version_number=version_number,
            content_hash=content_hash,
            file_size=len(content),
            timestamp=timestamp,
            is_restore=False,
            restored_from_version=None,
        )

    def create_restore_version(
        self, file_id: int, file_path: str, content: bytes, restored_from: int
    ) -> VersionInfo:
        """Create a version record with restore indicator.

        This always creates a new version (no deduplication check) since
        restoring is an explicit user action that should be recorded.

        Args:
            file_id: The database ID of the file.
            file_path: The relative file path.
            content: The restored file content bytes.
            restored_from: The version number being restored from.

        Returns:
            VersionInfo for the newly created restore version.

        Raises:
            ValueError: If file exceeds the 500 MB size limit.
            OSError: If disk write fails.
        """
        # Enforce file size limit
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File size {len(content)} bytes exceeds the "
                f"{MAX_FILE_SIZE_BYTES} byte (500 MB) limit."
            )

        content_hash = self._compute_md5(content)
        version_number = self._get_next_version_number(file_id)
        archive_path = self._get_archive_path(file_id, version_number)

        # Write content to archive with integrity verification
        if not self._write_content(archive_path, content):
            raise OSError(
                f"Failed to write restore version archive for file {file_id} "
                f"version {version_number}."
            )

        timestamp = datetime.now(timezone.utc)

        # Create database record with restore indicator
        version_record = FileVersion(
            file_id=file_id,
            version_number=version_number,
            content_hash=content_hash,
            file_size=len(content),
            timestamp=timestamp,
            archive_path=archive_path,
            is_restore=True,
            restored_from_version=restored_from,
        )
        self._db.add(version_record)

        # Update current_version on the File model
        self._db.query(File).filter(File.id == file_id).update(
            {"current_version": version_number}
        )

        self._db.commit()

        return VersionInfo(
            version_number=version_number,
            content_hash=content_hash,
            file_size=len(content),
            timestamp=timestamp,
            is_restore=True,
            restored_from_version=restored_from,
        )

    def get_versions(
        self, file_id: int, page: int = 1, page_size: int = 50
    ) -> list[VersionInfo]:
        """Get version history for a file, ordered by version_number descending.

        Args:
            file_id: The database ID of the file.
            page: Page number (1-indexed). Defaults to 1.
            page_size: Number of results per page. Defaults to 50.

        Returns:
            A list of VersionInfo records for the requested page.
        """
        offset = (page - 1) * page_size
        records = (
            self._db.query(FileVersion)
            .filter(FileVersion.file_id == file_id)
            .order_by(FileVersion.version_number.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )
        return [
            VersionInfo(
                version_number=r.version_number,
                content_hash=r.content_hash,
                file_size=r.file_size,
                timestamp=r.timestamp,
                is_restore=r.is_restore or False,
                restored_from_version=r.restored_from_version,
            )
            for r in records
        ]

    def get_version_content(self, file_id: int, version_number: int) -> bytes:
        """Retrieve stored content for a specific version.

        Args:
            file_id: The database ID of the file.
            version_number: The version number to retrieve.

        Returns:
            The archived content as bytes.

        Raises:
            FileNotFoundError: If the version record or archive file doesn't exist.
        """
        record = (
            self._db.query(FileVersion)
            .filter(
                FileVersion.file_id == file_id,
                FileVersion.version_number == version_number,
            )
            .first()
        )
        if record is None:
            raise FileNotFoundError(
                f"Version {version_number} not found for file {file_id}."
            )

        archive_path = record.archive_path
        if not os.path.exists(archive_path):
            raise FileNotFoundError(
                f"Archive file not found at {archive_path} for file {file_id} "
                f"version {version_number}."
            )

        with open(archive_path, "rb") as f:
            return f.read()

    def get_latest_version(self, file_id: int) -> VersionInfo | None:
        """Get the latest version record for a file.

        Args:
            file_id: The database ID of the file.

        Returns:
            VersionInfo for the latest version, or None if no versions exist.
        """
        record = (
            self._db.query(FileVersion)
            .filter(FileVersion.file_id == file_id)
            .order_by(FileVersion.version_number.desc())
            .first()
        )
        if record is None:
            return None

        return VersionInfo(
            version_number=record.version_number,
            content_hash=record.content_hash,
            file_size=record.file_size,
            timestamp=record.timestamp,
            is_restore=record.is_restore or False,
            restored_from_version=record.restored_from_version,
        )
