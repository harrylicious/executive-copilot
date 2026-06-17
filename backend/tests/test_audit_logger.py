"""Unit tests for the AuditLogger service."""

import re
import sys
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.audit_log import AuditLog
from app.services.audit_logger import AuditEventType, AuditLogger


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def logger(db_session):
    """Create an AuditLogger with an in-memory database session."""
    return AuditLogger(db=db_session)


class TestAuditEventType:
    """Tests for the AuditEventType enum."""

    def test_all_event_types_exist(self):
        """All required event types should be defined."""
        assert AuditEventType.FILE_CREATED.value == "file_created"
        assert AuditEventType.FILE_MODIFIED.value == "file_modified"
        assert AuditEventType.FILE_DELETED.value == "file_deleted"
        assert AuditEventType.EMBEDDING_STARTED.value == "embedding_started"
        assert AuditEventType.EMBEDDING_COMPLETED.value == "embedding_completed"
        assert AuditEventType.EMBEDDING_FAILED.value == "embedding_failed"
        assert AuditEventType.VERSION_CREATED.value == "version_created"
        assert AuditEventType.VERSION_RESTORED.value == "version_restored"
        assert AuditEventType.SYSTEM_ERROR.value == "system_error"

    def test_enum_has_exactly_nine_members(self):
        """There should be exactly 9 audit event types."""
        assert len(AuditEventType) == 9


class TestAuditLoggerLog:
    """Tests for the AuditLogger.log() method."""

    def test_creates_record_with_correct_fields(self, db_session, logger):
        """Should create an AuditLog record with all expected fields."""
        logger.log(
            event_type=AuditEventType.FILE_CREATED,
            file_id=42,
            actor="user_123",
            details={"path": "/docs/report.md"},
        )

        records = db_session.query(AuditLog).all()
        assert len(records) == 1

        record = records[0]
        assert record.event_type == "file_created"
        assert record.file_id == 42
        assert record.actor == "user_123"
        assert record.details == {"path": "/docs/report.md"}

    def test_timestamp_is_iso8601_utc_with_milliseconds(self, db_session, logger):
        """Timestamp should be ISO 8601 format with millisecond precision and Z suffix."""
        logger.log(event_type=AuditEventType.EMBEDDING_STARTED, file_id=1)

        record = db_session.query(AuditLog).first()
        # Pattern: YYYY-MM-DDTHH:MM:SS.mmmZ
        iso_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$"
        assert re.match(iso_pattern, record.timestamp), (
            f"Timestamp '{record.timestamp}' does not match ISO 8601 with ms precision"
        )

    def test_default_actor_is_system(self, db_session, logger):
        """When no actor is provided, it should default to 'system'."""
        logger.log(event_type=AuditEventType.FILE_DELETED, file_id=5)

        record = db_session.query(AuditLog).first()
        assert record.actor == "system"

    def test_file_id_can_be_none(self, db_session, logger):
        """file_id should be optional (e.g., for system-level events)."""
        logger.log(event_type=AuditEventType.SYSTEM_ERROR, details={"msg": "oops"})

        record = db_session.query(AuditLog).first()
        assert record.file_id is None

    def test_details_can_be_none(self, db_session, logger):
        """details should be optional."""
        logger.log(event_type=AuditEventType.FILE_MODIFIED, file_id=3)

        record = db_session.query(AuditLog).first()
        assert record.details is None

    def test_fire_and_forget_catches_db_errors(self, db_session, logger):
        """Database write errors should be caught and logged to stderr, not raised."""
        # Force a commit error by invalidating the session
        db_session.execute(
            __import__("sqlalchemy").text("DROP TABLE audit_log")
        )
        db_session.commit()

        captured = StringIO()
        with patch("sys.stderr", captured):
            # This should NOT raise
            logger.log(event_type=AuditEventType.SYSTEM_ERROR)

        stderr_output = captured.getvalue()
        assert "[AuditLogger]" in stderr_output
        assert "Failed to write audit log" in stderr_output


class TestAuditLoggerGetRecentEvents:
    """Tests for the AuditLogger.get_recent_events() method."""

    def test_returns_empty_list_when_no_records(self, logger):
        """Should return an empty list when no audit records exist."""
        result = logger.get_recent_events()
        assert result == []

    def test_returns_records_ordered_by_timestamp_desc(self, db_session, logger):
        """Should return records ordered by timestamp descending (most recent first)."""
        # Create records with known timestamps
        for i in range(5):
            record = AuditLog(
                timestamp=f"2024-01-0{i + 1}T00:00:00.000Z",
                event_type="file_created",
                file_id=i,
                actor="system",
            )
            db_session.add(record)
        db_session.commit()

        result = logger.get_recent_events()
        assert len(result) == 5
        # Most recent first
        assert result[0].timestamp == "2024-01-05T00:00:00.000Z"
        assert result[-1].timestamp == "2024-01-01T00:00:00.000Z"

    def test_respects_limit_parameter(self, db_session, logger):
        """Should return at most `limit` records."""
        for i in range(10):
            record = AuditLog(
                timestamp=f"2024-01-{i + 1:02d}T00:00:00.000Z",
                event_type="file_modified",
                file_id=i,
                actor="system",
            )
            db_session.add(record)
        db_session.commit()

        result = logger.get_recent_events(limit=3)
        assert len(result) == 3

    def test_default_limit_is_50(self, db_session, logger):
        """Default limit should be 50."""
        for i in range(60):
            record = AuditLog(
                timestamp=f"2024-06-15T10:{i:02d}:00.000Z",
                event_type="embedding_completed",
                file_id=i,
                actor="system",
            )
            db_session.add(record)
        db_session.commit()

        result = logger.get_recent_events()
        assert len(result) == 50
