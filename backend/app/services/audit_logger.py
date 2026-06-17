"""Audit Logger service for recording all system actions.

Fire-and-forget design: database write errors are logged to stderr
without blocking the caller.
"""

import sys
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.audit_log import AuditLog


class AuditEventType(Enum):
    """All auditable system event types."""

    FILE_CREATED = "file_created"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"
    EMBEDDING_STARTED = "embedding_started"
    EMBEDDING_COMPLETED = "embedding_completed"
    EMBEDDING_FAILED = "embedding_failed"
    VERSION_CREATED = "version_created"
    VERSION_RESTORED = "version_restored"
    SYSTEM_ERROR = "system_error"


class AuditLogger:
    """Records system actions with ISO 8601 UTC timestamps (millisecond precision).

    Uses a fire-and-forget approach: any database write errors are caught and
    logged to stderr so the caller is never blocked or interrupted.
    """

    def __init__(self, db: Session | None = None):
        """Initialize the AuditLogger.

        Args:
            db: Optional SQLAlchemy session. If not provided, a new session
                will be created for each operation using SessionLocal.
        """
        self._db = db

    def _get_session(self) -> tuple[Session, bool]:
        """Get a database session.

        Returns:
            A tuple of (session, should_close) where should_close indicates
            whether the caller is responsible for closing the session.
        """
        if self._db is not None:
            return self._db, False
        return SessionLocal(), True

    def _utc_now_iso8601(self) -> str:
        """Return the current UTC time as ISO 8601 with millisecond precision."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"

    def log(
        self,
        event_type: AuditEventType,
        file_id: int | None = None,
        actor: str = "system",
        details: dict | None = None,
    ) -> None:
        """Record an audit event with UTC timestamp.

        This method is fire-and-forget: any database errors are caught and
        logged to stderr without raising to the caller.

        Args:
            event_type: The type of audit event to record.
            file_id: Optional file ID associated with the event.
            actor: The actor performing the action (user ID or "system").
            details: Optional additional context as a JSON-serializable dict.
        """
        session, should_close = self._get_session()
        try:
            record = AuditLog(
                timestamp=self._utc_now_iso8601(),
                event_type=event_type.value,
                file_id=file_id,
                actor=actor,
                details=details,
            )
            session.add(record)
            session.commit()
        except Exception as exc:
            print(
                f"[AuditLogger] Failed to write audit log: {exc}",
                file=sys.stderr,
            )
            try:
                session.rollback()
            except Exception:
                pass
        finally:
            if should_close:
                session.close()

    def get_recent_events(self, limit: int = 50) -> list[AuditLog]:
        """Get the most recent audit events ordered by timestamp descending.

        Args:
            limit: Maximum number of records to return. Defaults to 50.

        Returns:
            A list of AuditLog records ordered by timestamp descending.
        """
        session, should_close = self._get_session()
        try:
            records = (
                session.query(AuditLog)
                .order_by(AuditLog.timestamp.desc())
                .limit(limit)
                .all()
            )
            return records
        except Exception as exc:
            print(
                f"[AuditLogger] Failed to read audit log: {exc}",
                file=sys.stderr,
            )
            return []
        finally:
            if should_close:
                session.close()
