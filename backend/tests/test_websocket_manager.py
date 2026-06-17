"""Unit tests for the WebSocketManager service."""

import asyncio
from collections import deque
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.audit_log import AuditLog
from app.services.audit_logger import AuditLogger
from app.services.websocket_manager import (
    BufferedEvent,
    WSEvent,
    WSEventType,
    WebSocketManager,
)


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
def manager():
    """Create a WebSocketManager instance for testing."""
    return WebSocketManager(max_event_buffer=100)


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
def manager_with_audit(db_session):
    """Create a WebSocketManager with an audit logger."""
    mgr = WebSocketManager(max_event_buffer=100)
    audit_logger = AuditLogger(db=db_session)
    mgr.set_audit_logger(audit_logger)
    return mgr, db_session


class TestWSEventType:
    """Tests for the WSEventType enum."""

    def test_all_event_types_defined(self):
        """All required event types should exist."""
        assert WSEventType.STATUS_CHANGED.value == "status_changed"
        assert WSEventType.VERSION_CREATED.value == "version_created"
        assert WSEventType.EMBEDDING_PROGRESS.value == "embedding_progress"
        assert WSEventType.ACTIVITY_EVENT.value == "activity_event"
        assert WSEventType.INITIAL_STATE.value == "initial_state"

    def test_enum_has_five_members(self):
        """There should be exactly 5 event types."""
        assert len(WSEventType) == 5


class TestWSEvent:
    """Tests for the WSEvent dataclass."""

    def test_default_timestamp_is_utc(self):
        """WSEvent should have a UTC timestamp by default."""
        event = WSEvent(
            event_type=WSEventType.STATUS_CHANGED,
            payload={"file_id": 1, "status": "embedded"},
        )
        assert event.timestamp.tzinfo is not None
        assert event.timestamp.tzinfo == timezone.utc

    def test_custom_timestamp(self):
        """WSEvent should accept a custom timestamp."""
        ts = datetime(2024, 6, 15, 10, 30, 0, tzinfo=timezone.utc)
        event = WSEvent(
            event_type=WSEventType.VERSION_CREATED,
            payload={"version": 3},
            timestamp=ts,
        )
        assert event.timestamp == ts


class TestWebSocketManagerConnect:
    """Tests for WebSocketManager.connect()."""

    @pytest.mark.asyncio
    async def test_accept_is_called(self, manager, mock_websocket):
        """connect() should call websocket.accept()."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_adds_to_active_connections(self, manager, mock_websocket):
        """connect() should add the websocket to active connections."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        assert mock_websocket in manager.active_connections

    @pytest.mark.asyncio
    async def test_sends_initial_state(self, manager, mock_websocket):
        """connect() should send an initial state snapshot."""
        fake_state = {
            "event_type": "initial_state",
            "payload": {"embedding_status_counts": {}, "recent_activity": []},
            "timestamp": "2024-01-01T00:00:00+00:00",
            "event_id": 0,
        }
        with patch.object(manager, "_build_initial_state", return_value=fake_state):
            await manager.connect(mock_websocket)
        mock_websocket.send_json.assert_called_with(fake_state)

    @pytest.mark.asyncio
    async def test_starts_ping_task(self, manager, mock_websocket):
        """connect() should start a ping/pong health check task."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        assert mock_websocket in manager._ping_tasks
        # Clean up
        await manager.disconnect(mock_websocket)


class TestWebSocketManagerDisconnect:
    """Tests for WebSocketManager.disconnect()."""

    @pytest.mark.asyncio
    async def test_removes_from_active_connections(self, manager, mock_websocket):
        """disconnect() should remove the websocket from active connections."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        await manager.disconnect(mock_websocket)
        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_cancels_ping_task(self, manager, mock_websocket):
        """disconnect() should cancel the ping task."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        assert mock_websocket in manager._ping_tasks
        await manager.disconnect(mock_websocket)
        assert mock_websocket not in manager._ping_tasks

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_is_safe(self, manager, mock_websocket):
        """disconnect() should not raise for a websocket not in the set."""
        await manager.disconnect(mock_websocket)
        # Should not raise


class TestWebSocketManagerBroadcast:
    """Tests for WebSocketManager.broadcast()."""

    @pytest.mark.asyncio
    async def test_assigns_monotonically_increasing_event_ids(self, manager):
        """Each broadcast should assign increasing event IDs."""
        event1 = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={"a": 1})
        event2 = WSEvent(event_type=WSEventType.VERSION_CREATED, payload={"b": 2})
        event3 = WSEvent(event_type=WSEventType.ACTIVITY_EVENT, payload={"c": 3})

        await manager.broadcast(event1)
        await manager.broadcast(event2)
        await manager.broadcast(event3)

        ids = [ev.event_id for ev in manager.event_buffer]
        assert ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_sends_to_all_connected_clients(self, manager, mock_websocket):
        """broadcast() should send the event to all connected clients."""
        ws1 = AsyncMock()
        ws1.accept = AsyncMock()
        ws1.send_json = AsyncMock()
        ws2 = AsyncMock()
        ws2.accept = AsyncMock()
        ws2.send_json = AsyncMock()

        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(ws1)
            await manager.connect(ws2)

        # Reset send_json call counts after initial state
        ws1.send_json.reset_mock()
        ws2.send_json.reset_mock()

        event = WSEvent(
            event_type=WSEventType.STATUS_CHANGED,
            payload={"file_id": 1, "status": "embedded"},
        )
        await manager.broadcast(event)

        ws1.send_json.assert_called_once()
        ws2.send_json.assert_called_once()

        # Clean up
        await manager.disconnect(ws1)
        await manager.disconnect(ws2)

    @pytest.mark.asyncio
    async def test_buffers_event_in_ring_buffer(self, manager):
        """broadcast() should add the event to the ring buffer."""
        event = WSEvent(
            event_type=WSEventType.VERSION_CREATED,
            payload={"file_id": 5, "version": 2},
        )
        await manager.broadcast(event)

        assert len(manager.event_buffer) == 1
        buffered = manager.event_buffer[0]
        assert buffered.event_id == 1
        assert buffered.event_type == WSEventType.VERSION_CREATED
        assert buffered.payload == {"file_id": 5, "version": 2}

    @pytest.mark.asyncio
    async def test_ring_buffer_evicts_oldest_when_full(self):
        """Ring buffer should evict oldest events when max capacity is reached."""
        mgr = WebSocketManager(max_event_buffer=5)

        for i in range(8):
            event = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={"i": i})
            await mgr.broadcast(event)

        # Buffer should have max 5 events (the last 5: IDs 4, 5, 6, 7, 8)
        assert len(mgr.event_buffer) == 5
        ids = [ev.event_id for ev in mgr.event_buffer]
        assert ids == [4, 5, 6, 7, 8]

    @pytest.mark.asyncio
    async def test_disconnects_failed_clients(self, manager):
        """broadcast() should disconnect clients that fail to receive messages."""
        ws_good = AsyncMock()
        ws_good.accept = AsyncMock()
        ws_good.send_json = AsyncMock()
        ws_bad = AsyncMock()
        ws_bad.accept = AsyncMock()
        ws_bad.send_json = AsyncMock(side_effect=Exception("Connection lost"))

        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(ws_good)
            await manager.connect(ws_bad)

        event = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={"x": 1})
        await manager.broadcast(event)

        assert ws_good in manager.active_connections
        assert ws_bad not in manager.active_connections

        # Clean up
        await manager.disconnect(ws_good)

    @pytest.mark.asyncio
    async def test_event_message_format(self, manager, mock_websocket):
        """Broadcast message should match WSMessage schema format."""
        with patch.object(manager, "_build_initial_state", return_value={"event_type": "initial_state", "payload": {}, "timestamp": "", "event_id": 0}):
            await manager.connect(mock_websocket)
        mock_websocket.send_json.reset_mock()

        ts = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        event = WSEvent(
            event_type=WSEventType.STATUS_CHANGED,
            payload={"file_id": 1, "status": "embedding"},
            timestamp=ts,
        )
        await manager.broadcast(event)

        call_args = mock_websocket.send_json.call_args[0][0]
        assert call_args["event_type"] == "status_changed"
        assert call_args["payload"] == {"file_id": 1, "status": "embedding"}
        assert call_args["timestamp"] == "2024-06-15T12:00:00+00:00"
        assert call_args["event_id"] == 1

        await manager.disconnect(mock_websocket)


class TestWebSocketManagerSendMissedEvents:
    """Tests for WebSocketManager.send_missed_events()."""

    @pytest.mark.asyncio
    async def test_sends_events_after_last_event_id(self, manager, mock_websocket):
        """send_missed_events() should send only events with ID > last_event_id."""
        # Populate buffer
        for i in range(5):
            event = WSEvent(
                event_type=WSEventType.STATUS_CHANGED, payload={"idx": i}
            )
            await manager.broadcast(event)

        mock_websocket.send_json.reset_mock()
        await manager.send_missed_events(mock_websocket, last_event_id=3)

        # Should send events with IDs 4 and 5
        assert mock_websocket.send_json.call_count == 2
        calls = mock_websocket.send_json.call_args_list
        assert calls[0][0][0]["event_id"] == 4
        assert calls[1][0][0]["event_id"] == 5

    @pytest.mark.asyncio
    async def test_sends_nothing_if_caught_up(self, manager, mock_websocket):
        """send_missed_events() should send nothing if client is up to date."""
        for i in range(3):
            event = WSEvent(
                event_type=WSEventType.STATUS_CHANGED, payload={"idx": i}
            )
            await manager.broadcast(event)

        mock_websocket.send_json.reset_mock()
        await manager.send_missed_events(mock_websocket, last_event_id=3)

        mock_websocket.send_json.assert_not_called()

    @pytest.mark.asyncio
    async def test_sends_all_buffered_if_last_id_is_zero(self, manager, mock_websocket):
        """send_missed_events() with last_event_id=0 should send all buffered events."""
        for i in range(3):
            event = WSEvent(
                event_type=WSEventType.ACTIVITY_EVENT, payload={"idx": i}
            )
            await manager.broadcast(event)

        mock_websocket.send_json.reset_mock()
        await manager.send_missed_events(mock_websocket, last_event_id=0)

        assert mock_websocket.send_json.call_count == 3

    @pytest.mark.asyncio
    async def test_chronological_order(self, manager, mock_websocket):
        """Missed events should be sent in chronological order (ascending ID)."""
        for i in range(5):
            event = WSEvent(
                event_type=WSEventType.VERSION_CREATED, payload={"v": i + 1}
            )
            await manager.broadcast(event)

        mock_websocket.send_json.reset_mock()
        await manager.send_missed_events(mock_websocket, last_event_id=2)

        calls = mock_websocket.send_json.call_args_list
        ids = [c[0][0]["event_id"] for c in calls]
        assert ids == [3, 4, 5]

    @pytest.mark.asyncio
    async def test_stops_on_send_failure(self, manager, mock_websocket):
        """send_missed_events() should stop sending if a send fails."""
        for i in range(5):
            event = WSEvent(
                event_type=WSEventType.STATUS_CHANGED, payload={"idx": i}
            )
            await manager.broadcast(event)

        # Fail on the second send
        mock_websocket.send_json = AsyncMock(
            side_effect=[None, Exception("Connection lost"), None]
        )
        await manager.send_missed_events(mock_websocket, last_event_id=0)

        # Should have attempted 2 sends (success, then failure)
        assert mock_websocket.send_json.call_count == 2


class TestWebSocketManagerRingBuffer:
    """Tests for ring buffer behavior."""

    @pytest.mark.asyncio
    async def test_max_buffer_size_respected(self):
        """Ring buffer should never exceed max_event_buffer size."""
        mgr = WebSocketManager(max_event_buffer=10)

        for i in range(25):
            event = WSEvent(
                event_type=WSEventType.STATUS_CHANGED, payload={"i": i}
            )
            await mgr.broadcast(event)

        assert len(mgr.event_buffer) == 10
        # Should contain the 10 most recent events (IDs 16-25)
        ids = [ev.event_id for ev in mgr.event_buffer]
        assert ids == list(range(16, 26))

    @pytest.mark.asyncio
    async def test_default_buffer_size_is_100(self):
        """Default ring buffer size should be 100."""
        mgr = WebSocketManager()
        assert mgr._event_buffer.maxlen == 100


class TestWebSocketManagerInitialState:
    """Tests for initial state snapshot building."""

    def test_get_embedding_status_counts_with_data(self, db_session):
        """Should return correct counts per embedding status."""
        # Add files with different statuses
        for i, status in enumerate(
            ["pending", "pending", "embedding", "embedded", "embedded", "embedded", "failed", "stale"]
        ):
            f = File(
                id=i + 1,
                name=f"file_{i}.txt",
                path=f"/kb/file_{i}.txt",
                department="eng",
                size=100,
                created_at=datetime.now(timezone.utc),
                modified_at=datetime.now(timezone.utc),
                embedding_status=status,
                is_deleted=False,
            )
            db_session.add(f)
        db_session.commit()

        mgr = WebSocketManager()
        with patch("app.services.websocket_manager.SessionLocal", return_value=db_session):
            # Prevent session.close() from actually closing our test session
            with patch.object(db_session, "close"):
                counts = mgr._get_embedding_status_counts()

        assert counts == {
            "pending": 2,
            "embedding": 1,
            "embedded": 3,
            "failed": 1,
            "stale": 1,
        }

    def test_get_embedding_status_counts_excludes_deleted(self, db_session):
        """Should exclude deleted files from counts."""
        f1 = File(
            id=1,
            name="active.txt",
            path="/kb/active.txt",
            department="eng",
            size=100,
            created_at=datetime.now(timezone.utc),
            modified_at=datetime.now(timezone.utc),
            embedding_status="embedded",
            is_deleted=False,
        )
        f2 = File(
            id=2,
            name="deleted.txt",
            path="/kb/deleted.txt",
            department="eng",
            size=100,
            created_at=datetime.now(timezone.utc),
            modified_at=datetime.now(timezone.utc),
            embedding_status="embedded",
            is_deleted=True,
        )
        db_session.add_all([f1, f2])
        db_session.commit()

        mgr = WebSocketManager()
        with patch("app.services.websocket_manager.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                counts = mgr._get_embedding_status_counts()

        assert counts["embedded"] == 1

    def test_get_recent_activity_events_without_logger(self):
        """Should return empty list when no audit logger is set."""
        mgr = WebSocketManager()
        events = mgr._get_recent_activity_events()
        assert events == []

    def test_get_recent_activity_events_with_logger(self, db_session):
        """Should return formatted activity events from audit logger."""
        # Add audit records
        for i in range(3):
            record = AuditLog(
                timestamp=f"2024-06-15T10:0{i}:00.000Z",
                event_type="file_created",
                file_id=i + 1,
                actor="system",
                details={"path": f"/kb/file_{i}.txt"},
            )
            db_session.add(record)
        db_session.commit()

        mgr = WebSocketManager()
        audit_logger = AuditLogger(db=db_session)
        mgr.set_audit_logger(audit_logger)

        events = mgr._get_recent_activity_events()
        assert len(events) == 3
        assert events[0]["event_type"] == "file_created"
        assert events[0]["actor"] == "system"

    def test_build_initial_state_structure(self, db_session):
        """Initial state should have the correct structure."""
        mgr = WebSocketManager()
        audit_logger = AuditLogger(db=db_session)
        mgr.set_audit_logger(audit_logger)

        with patch("app.services.websocket_manager.SessionLocal", return_value=db_session):
            with patch.object(db_session, "close"):
                state = mgr._build_initial_state()

        assert state["event_type"] == "initial_state"
        assert "embedding_status_counts" in state["payload"]
        assert "recent_activity" in state["payload"]
        assert state["event_id"] == 0
        assert "timestamp" in state


class TestWebSocketManagerMonotonicIds:
    """Tests for monotonically increasing event IDs."""

    @pytest.mark.asyncio
    async def test_ids_start_at_one(self, manager):
        """First event should have ID 1."""
        event = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={})
        await manager.broadcast(event)
        assert manager.event_buffer[0].event_id == 1

    @pytest.mark.asyncio
    async def test_ids_never_repeat(self, manager):
        """Event IDs should never repeat."""
        for i in range(50):
            event = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={"i": i})
            await manager.broadcast(event)

        ids = [ev.event_id for ev in manager.event_buffer]
        assert len(ids) == len(set(ids))

    @pytest.mark.asyncio
    async def test_ids_strictly_increasing(self, manager):
        """Event IDs should be strictly increasing."""
        for i in range(20):
            event = WSEvent(event_type=WSEventType.STATUS_CHANGED, payload={"i": i})
            await manager.broadcast(event)

        ids = [ev.event_id for ev in manager.event_buffer]
        for j in range(1, len(ids)):
            assert ids[j] > ids[j - 1]
