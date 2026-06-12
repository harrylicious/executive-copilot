"""Unit tests for the session service — specifically the UNIQUE constraint handling."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.chat_session import ChatMessageRecord, ChatSession
from app.services.session_service import save_session, get_session, get_session_messages


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def session_factory(db_session):
    """Return the sessionmaker bound to the same in-memory DB."""
    return sessionmaker(bind=db_session.get_bind())


class TestSaveSession:
    """Tests for save_session."""

    def test_creates_new_session(self, db_session):
        """Should create a new session when it doesn't exist."""
        result = save_session(
            db=db_session,
            session_id="sess-001",
            title="Test Session",
            retrieval_mode="local",
        )
        assert result.id == "sess-001"
        assert result.title == "Test Session"
        assert result.retrieval_mode == "local"

    def test_updates_existing_session(self, db_session):
        """Should update an existing session's fields."""
        save_session(db=db_session, session_id="sess-002", title="Original")
        result = save_session(db=db_session, session_id="sess-002", title="Updated")
        assert result.title == "Updated"

    def test_inserts_new_messages(self, db_session):
        """Should insert messages for a new session."""
        messages = [
            {
                "id": "msg-001",
                "session_id": "sess-003",
                "role": "user",
                "content": "Hello",
                "sources": None,
                "metadata_json": None,
                "error": None,
                "timestamp": 1000.0,
            },
            {
                "id": "msg-002",
                "session_id": "sess-003",
                "role": "assistant",
                "content": "Hi there!",
                "sources": None,
                "metadata_json": None,
                "error": None,
                "timestamp": 1001.0,
            },
        ]
        save_session(db=db_session, session_id="sess-003", messages=messages)

        stored = get_session_messages(db_session, "sess-003")
        assert len(stored) == 2
        assert stored[0].content == "Hello"
        assert stored[1].content == "Hi there!"

    def test_updates_existing_messages(self, db_session):
        """Should update content of existing messages."""
        messages = [
            {
                "id": "msg-010",
                "session_id": "sess-004",
                "role": "assistant",
                "content": "Partial...",
                "sources": None,
                "metadata_json": None,
                "error": None,
                "timestamp": 2000.0,
            },
        ]
        save_session(db=db_session, session_id="sess-004", messages=messages)

        # Update the message content (simulating streaming completion)
        messages[0]["content"] = "Full response complete."
        save_session(db=db_session, session_id="sess-004", messages=messages)

        stored = get_session_messages(db_session, "sess-004")
        assert len(stored) == 1
        assert stored[0].content == "Full response complete."

    def test_handles_duplicate_message_id_gracefully(self, db_session):
        """Should not crash when the same message ID is inserted twice.

        This simulates the race condition where concurrent requests both
        try to insert the same message ID.
        """
        messages = [
            {
                "id": "msg-dup-001",
                "session_id": "sess-005",
                "role": "user",
                "content": "First insert",
                "sources": None,
                "metadata_json": None,
                "error": None,
                "timestamp": 3000.0,
            },
        ]
        # First save
        save_session(db=db_session, session_id="sess-005", messages=messages)

        # Simulate a second concurrent save with the same message ID
        # but from a "different session check" (the existing_ids query
        # wouldn't find it if scoped differently)
        messages[0]["content"] = "Updated via race"
        save_session(db=db_session, session_id="sess-005", messages=messages)

        stored = get_session_messages(db_session, "sess-005")
        assert len(stored) == 1
        assert stored[0].content == "Updated via race"

    def test_concurrent_saves_do_not_crash(self, session_factory):
        """Concurrent saves with overlapping session+message IDs should not raise.

        This simulates the race condition where two requests both try to
        create the same session ID simultaneously.
        """
        db = session_factory()

        # First, create the session directly (simulating the first concurrent request winning)
        session = ChatSession(id="sess-006", title="First")
        db.add(session)
        db.commit()

        # Now call save_session with the same session ID and a message —
        # this simulates the second concurrent request that also saw session=None
        # but the first request already committed the session
        messages = [
            {
                "id": "msg-race-001",
                "session_id": "sess-006",
                "role": "user",
                "content": "Via save_session",
                "sources": None,
                "metadata_json": None,
                "error": None,
                "timestamp": 4000.0,
            },
        ]
        # This should NOT raise — it should detect the existing session and proceed
        result = save_session(
            db=db, session_id="sess-006", title="Second", messages=messages
        )

        assert result.id == "sess-006"
        stored = get_session_messages(db, "sess-006")
        assert len(stored) == 1
        assert stored[0].id == "msg-race-001"
        assert stored[0].content == "Via save_session"
        db.close()

    def test_session_creation_race_condition(self, session_factory):
        """When session already exists but our query missed it, handle gracefully.

        Simulates: request A creates session, request B's initial query returned
        None but by the time it tries to INSERT, session already exists.
        """
        db1 = session_factory()
        db2 = session_factory()

        # Request A creates the session
        save_session(db=db1, session_id="sess-race", title="Request A")

        # Request B tries to create the same session — should not crash
        result = save_session(db=db2, session_id="sess-race", title="Request B")
        assert result.id == "sess-race"
        # Title should be updated to Request B's value
        assert result.title == "Request B"
        db1.close()
        db2.close()
