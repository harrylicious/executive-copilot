"""File Watcher Service for real-time filesystem monitoring.

Uses watchdog to monitor the knowledge base directory for file creation,
modification, and deletion events. Implements per-file debouncing,
depth filtering, subscriber pattern, reconciliation, and exponential
backoff reconnection on errors.
"""

import asyncio
import hashlib
import logging
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Awaitable, Callable

from watchdog.events import (
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from app.database import SessionLocal
from app.models.file import File

logger = logging.getLogger(__name__)


class FileEventType(Enum):
    """Types of file system events detected by the watcher."""

    CREATED = "file_created"
    MODIFIED = "file_modified"
    DELETED = "file_deleted"


@dataclass
class FileNotification:
    """Notification emitted when a file system event is detected.

    Attributes:
        event_type: The type of file event.
        file_path: Path relative to the knowledge base root.
        file_size: Size in bytes (None for deletions).
        content_hash: MD5 hash of the file content (None for deletions).
        timestamp: UTC detection timestamp.
    """

    event_type: FileEventType
    file_path: str  # Relative to knowledge base root
    file_size: int | None  # None for deletions
    content_hash: str | None  # None for deletions
    timestamp: datetime  # UTC detection timestamp


EventHandler = Callable[[FileNotification], Awaitable[None]]


class _WatchdogHandler(FileSystemEventHandler):
    """Custom watchdog event handler that forwards events to the watcher service."""

    def __init__(self, watcher: "FileWatcherService") -> None:
        super().__init__()
        self._watcher = watcher

    def on_created(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_raw_event(event.src_path, FileEventType.CREATED)

    def on_modified(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_raw_event(event.src_path, FileEventType.MODIFIED)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._watcher._handle_raw_event(event.src_path, FileEventType.DELETED)

    def on_moved(self, event: FileSystemEvent) -> None:
        if not event.is_directory and isinstance(event, FileMovedEvent):
            # Treat a move as deletion of old path + creation of new path
            self._watcher._handle_raw_event(event.src_path, FileEventType.DELETED)
            self._watcher._handle_raw_event(event.dest_path, FileEventType.CREATED)


class FileWatcherService:
    """Monitors the knowledge base directory for filesystem events.

    Features:
    - Real-time detection of file creation, modification, and deletion
    - Per-file debouncing with configurable window (default 2 seconds)
    - Depth filtering (max 10 levels from KB root)
    - Subscriber pattern for async event handlers
    - Initial reconciliation against database on startup
    - Exponential backoff reconnection on filesystem errors (1s → 60s max)
    """

    def __init__(
        self,
        kb_path: str,
        debounce_seconds: float = 2.0,
        max_depth: int = 10,
    ) -> None:
        """Initialize the FileWatcherService.

        Args:
            kb_path: Absolute path to the knowledge base root directory.
            debounce_seconds: Seconds to wait before emitting a debounced event.
            max_depth: Maximum directory depth to monitor (relative to kb_path).
        """
        self._kb_path = Path(kb_path).resolve()
        self._debounce_seconds = debounce_seconds
        self._max_depth = max_depth
        self._subscribers: list[EventHandler] = []
        self._debounce_tasks: dict[str, asyncio.Task] = {}
        self._observer: Observer | None = None
        self._running = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._backoff_seconds = 1.0
        self._max_backoff_seconds = 60.0
        self._reconnect_task: asyncio.Task | None = None

    def subscribe(self, handler: EventHandler) -> None:
        """Register an async handler for file notifications.

        Args:
            handler: An async callable that receives FileNotification objects.
        """
        self._subscribers.append(handler)

    async def start(self) -> None:
        """Start watching the filesystem and perform initial reconciliation.

        Starts the watchdog observer and performs a full filesystem
        reconciliation against the database.
        """
        self._loop = asyncio.get_running_loop()
        self._running = True
        self._start_observer()
        # Perform initial reconciliation
        await self.reconcile()

    async def stop(self) -> None:
        """Stop watching and clean up resources gracefully."""
        self._running = False

        # Cancel reconnect task if running
        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()
            try:
                await self._reconnect_task
            except asyncio.CancelledError:
                pass
            self._reconnect_task = None

        # Cancel all pending debounce tasks
        for task in self._debounce_tasks.values():
            task.cancel()
        self._debounce_tasks.clear()

        # Stop the watchdog observer
        self._stop_observer()

    async def reconcile(self) -> list[FileNotification]:
        """Full filesystem reconciliation against database state.

        Compares the current filesystem state against the database and
        emits notifications for each discrepancy:
        - Files on disk but not in DB → file-created
        - Files in DB but not on disk → file-deleted
        - Files in both but with different content hash → file-modified

        Returns:
            List of FileNotification objects for all discrepancies found.
        """
        notifications: list[FileNotification] = []

        # Scan the filesystem
        fs_files = self._scan_filesystem()

        # Get database state
        db_files = self._get_db_files()

        fs_paths = set(fs_files.keys())
        db_paths = set(db_files.keys())

        now = datetime.now(timezone.utc)

        # Files on disk but not in DB → CREATED
        for path in fs_paths - db_paths:
            info = fs_files[path]
            notification = FileNotification(
                event_type=FileEventType.CREATED,
                file_path=path,
                file_size=info["size"],
                content_hash=info["content_hash"],
                timestamp=now,
            )
            notifications.append(notification)

        # Files in DB but not on disk → DELETED
        for path in db_paths - fs_paths:
            notification = FileNotification(
                event_type=FileEventType.DELETED,
                file_path=path,
                file_size=None,
                content_hash=None,
                timestamp=now,
            )
            notifications.append(notification)

        # Files in both but with different hash → MODIFIED
        for path in fs_paths & db_paths:
            fs_hash = fs_files[path]["content_hash"]
            db_hash = db_files[path]
            if fs_hash != db_hash:
                info = fs_files[path]
                notification = FileNotification(
                    event_type=FileEventType.MODIFIED,
                    file_path=path,
                    file_size=info["size"],
                    content_hash=fs_hash,
                    timestamp=now,
                )
                notifications.append(notification)

        # Dispatch all notifications to subscribers
        for notification in notifications:
            await self._dispatch(notification)

        return notifications

    def _start_observer(self) -> None:
        """Start the watchdog observer for the KB directory."""
        try:
            self._observer = Observer()
            handler = _WatchdogHandler(self)
            self._observer.schedule(handler, str(self._kb_path), recursive=True)
            self._observer.start()
            self._backoff_seconds = 1.0  # Reset backoff on successful start
            logger.info(f"File watcher started for: {self._kb_path}")
        except Exception as exc:
            logger.error(f"Failed to start file watcher: {exc}")
            self._observer = None
            if self._running:
                self._schedule_reconnect()

    def _stop_observer(self) -> None:
        """Stop the watchdog observer if running."""
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception as exc:
                logger.warning(f"Error stopping observer: {exc}")
            finally:
                self._observer = None

    def _schedule_reconnect(self) -> None:
        """Schedule a reconnection attempt with exponential backoff."""
        if not self._running or self._loop is None:
            return

        async def _reconnect() -> None:
            while self._running and self._observer is None:
                logger.info(
                    f"Attempting reconnection in {self._backoff_seconds:.1f}s..."
                )
                await asyncio.sleep(self._backoff_seconds)
                if not self._running:
                    break
                self._start_observer()
                if self._observer is None:
                    # Increase backoff up to max
                    self._backoff_seconds = min(
                        self._backoff_seconds * 2, self._max_backoff_seconds
                    )

        self._reconnect_task = asyncio.ensure_future(_reconnect())

    def _handle_raw_event(self, abs_path: str, event_type: FileEventType) -> None:
        """Handle a raw filesystem event from watchdog (called from watchdog thread).

        Applies depth filtering and schedules debounced processing on the
        event loop.

        Args:
            abs_path: Absolute path of the affected file.
            event_type: The type of event detected.
        """
        # Compute relative path
        try:
            rel_path = self._get_relative_path(abs_path)
        except ValueError:
            return  # Path is not within KB root

        # Depth filtering
        if not self._is_within_depth(rel_path):
            return

        # Schedule debounced processing on the async event loop
        if self._loop is not None and self._running:
            self._loop.call_soon_threadsafe(
                self._schedule_debounce, rel_path, event_type
            )

    def _schedule_debounce(self, rel_path: str, event_type: FileEventType) -> None:
        """Schedule or restart debounce timer for a file path.

        If a debounce task already exists for this path, cancel it and
        restart with the new event type.

        Args:
            rel_path: Relative path of the file.
            event_type: The latest event type for this file.
        """
        # Cancel existing debounce task for this path
        existing_task = self._debounce_tasks.get(rel_path)
        if existing_task and not existing_task.done():
            existing_task.cancel()

        # Create a new debounce task
        task = asyncio.ensure_future(self._debounce_emit(rel_path, event_type))
        self._debounce_tasks[rel_path] = task

    async def _debounce_emit(self, rel_path: str, event_type: FileEventType) -> None:
        """Wait for the debounce period then emit the notification.

        Args:
            rel_path: Relative path of the file.
            event_type: The event type to emit.
        """
        try:
            await asyncio.sleep(self._debounce_seconds)
        except asyncio.CancelledError:
            return

        # Clean up the debounce task entry
        self._debounce_tasks.pop(rel_path, None)

        # Build the notification
        notification = self._build_notification(rel_path, event_type)

        # Dispatch to subscribers
        await self._dispatch(notification)

    def _build_notification(
        self, rel_path: str, event_type: FileEventType
    ) -> FileNotification:
        """Build a FileNotification for the given path and event type.

        For CREATED/MODIFIED events, computes file size and MD5 content hash.
        For DELETED events, size and hash are None.

        Args:
            rel_path: Relative path of the file.
            event_type: The event type.

        Returns:
            A FileNotification instance.
        """
        if event_type == FileEventType.DELETED:
            return FileNotification(
                event_type=event_type,
                file_path=rel_path,
                file_size=None,
                content_hash=None,
                timestamp=datetime.now(timezone.utc),
            )

        abs_path = self._kb_path / rel_path
        try:
            file_size = abs_path.stat().st_size
            content_hash = self._compute_md5(abs_path)
        except OSError:
            # File may have been deleted between event and processing
            return FileNotification(
                event_type=FileEventType.DELETED,
                file_path=rel_path,
                file_size=None,
                content_hash=None,
                timestamp=datetime.now(timezone.utc),
            )

        return FileNotification(
            event_type=event_type,
            file_path=rel_path,
            file_size=file_size,
            content_hash=content_hash,
            timestamp=datetime.now(timezone.utc),
        )

    async def _dispatch(self, notification: FileNotification) -> None:
        """Dispatch a notification to all registered subscribers.

        Args:
            notification: The FileNotification to dispatch.
        """
        for handler in self._subscribers:
            try:
                await handler(notification)
            except Exception as exc:
                logger.error(
                    f"Error in subscriber handler for {notification.file_path}: {exc}",
                    exc_info=True,
                )

    def _get_relative_path(self, abs_path: str) -> str:
        """Convert an absolute path to a path relative to kb_path.

        Args:
            abs_path: Absolute filesystem path.

        Returns:
            Path string relative to kb_path, using forward slashes.

        Raises:
            ValueError: If the path is not within the KB root.
        """
        resolved = Path(abs_path).resolve()
        rel = resolved.relative_to(self._kb_path)
        return str(rel).replace("\\", "/")

    def _is_within_depth(self, rel_path: str) -> bool:
        """Check if a relative path is within the configured max depth.

        Depth is determined by the number of path components.
        A file at depth N has N components (including the filename).
        We compare against max_depth which limits directory levels.

        Args:
            rel_path: Relative path using forward slashes.

        Returns:
            True if the path depth is within the limit.
        """
        parts = rel_path.split("/")
        # parts includes the filename, so directory depth is len(parts) - 1
        # But the spec says "maximum depth of 10 levels" for directories
        # A file at "a/b/c/file.txt" has 3 directory levels
        # We allow paths where the total component count <= max_depth + 1
        # (max_depth directory levels + the filename)
        return len(parts) <= self._max_depth + 1

    def _scan_filesystem(self) -> dict[str, dict]:
        """Scan the KB directory and return file info keyed by relative path.

        Respects the max_depth configuration.

        Returns:
            Dictionary mapping relative paths to dicts with 'size' and
            'content_hash' keys.
        """
        files: dict[str, dict] = {}

        if not self._kb_path.exists():
            return files

        for file_path in self._kb_path.rglob("*"):
            if not file_path.is_file():
                continue

            try:
                rel_path = str(file_path.relative_to(self._kb_path)).replace("\\", "/")
            except ValueError:
                continue

            # Apply depth filtering
            if not self._is_within_depth(rel_path):
                continue

            try:
                stat = file_path.stat()
                content_hash = self._compute_md5(file_path)
                files[rel_path] = {
                    "size": stat.st_size,
                    "content_hash": content_hash,
                }
            except OSError as exc:
                logger.warning(f"Could not read file {file_path}: {exc}")
                continue

        return files

    def _get_db_files(self) -> dict[str, str]:
        """Get all non-deleted file records from the database.

        Returns:
            Dictionary mapping relative paths to their content_hash values.
        """
        db = SessionLocal()
        try:
            files = (
                db.query(File.path, File.content_hash)
                .filter(File.is_deleted == False)  # noqa: E712
                .all()
            )
            return {f.path: (f.content_hash or "") for f in files}
        finally:
            db.close()

    @staticmethod
    def _compute_md5(file_path: Path) -> str:
        """Compute MD5 hash of a file's content.

        Reads the file in chunks to handle large files efficiently.

        Args:
            file_path: Path to the file.

        Returns:
            Hex digest of the MD5 hash.
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
