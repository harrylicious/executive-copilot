"""WebSocket Manager service for real-time event broadcasting.

Manages WebSocket connections, broadcasts events to all clients,
maintains a ring buffer for reconnection replay, and sends initial
state snapshots on connect.
"""

import asyncio
import sys
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from sqlalchemy import func

from app.database import SessionLocal
from app.models.file import File
from app.services.audit_logger import AuditLogger


class WSEventType(Enum):
    """WebSocket event types broadcast to clients."""

    STATUS_CHANGED = "status_changed"
    VERSION_CREATED = "version_created"
    EMBEDDING_PROGRESS = "embedding_progress"
    ACTIVITY_EVENT = "activity_event"
    INITIAL_STATE = "initial_state"


@dataclass
class WSEvent:
    """A WebSocket event to be broadcast to connected clients."""

    event_type: WSEventType
    payload: dict
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class BufferedEvent:
    """An event stored in the ring buffer with its assigned ID."""

    event_id: int
    event_type: WSEventType
    payload: dict
    timestamp: datetime


class WebSocketManager:
    """Manages WebSocket connections and real-time event broadcasting.

    Features:
    - Connection tracking with connect/disconnect lifecycle
    - Broadcasting events to all connected clients
    - Ring buffer (max 100 events) for reconnection replay
    - Monotonically increasing event IDs
    - Initial state snapshot on connect (embedding status counts + last 50 activity events)
    - Ping/pong with 30s timeout for connection health detection
    """

    def __init__(self, max_event_buffer: int = 100):
        """Initialize the WebSocketManager.

        Args:
            max_event_buffer: Maximum number of events to keep in the ring buffer
                for reconnection replay. Defaults to 100.
        """
        self._active_connections: set[WebSocket] = set()
        self._event_buffer: deque[BufferedEvent] = deque(maxlen=max_event_buffer)
        self._next_event_id: int = 1
        self._lock: asyncio.Lock = asyncio.Lock()
        self._ping_tasks: dict[WebSocket, asyncio.Task] = {}
        self._audit_logger: AuditLogger | None = None

    @property
    def active_connections(self) -> set[WebSocket]:
        """Return the set of currently active WebSocket connections."""
        return self._active_connections

    @property
    def event_buffer(self) -> deque[BufferedEvent]:
        """Return the event ring buffer (read-only access)."""
        return self._event_buffer

    def set_audit_logger(self, audit_logger: AuditLogger) -> None:
        """Set the audit logger instance for retrieving recent events.

        Args:
            audit_logger: The AuditLogger service instance.
        """
        self._audit_logger = audit_logger

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a WebSocket connection and send initial state snapshot.

        Accepts the connection, adds it to the active set, starts a
        ping/pong health check task, and sends the initial state snapshot
        containing embedding status counts and last 50 activity events.

        Args:
            websocket: The WebSocket connection to accept.
        """
        await websocket.accept()
        self._active_connections.add(websocket)

        # Start ping/pong health check
        task = asyncio.create_task(self._ping_loop(websocket))
        self._ping_tasks[websocket] = task

        # Send initial state snapshot
        try:
            initial_state = self._build_initial_state()
            await self._send_event(websocket, initial_state)
        except Exception as exc:
            print(
                f"[WebSocketManager] Failed to send initial state: {exc}",
                file=sys.stderr,
            )

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active set.

        Cancels the ping/pong health check task and removes the connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        self._active_connections.discard(websocket)

        # Cancel ping/pong task
        task = self._ping_tasks.pop(websocket, None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def broadcast(self, event: WSEvent) -> None:
        """Broadcast an event to all connected clients and buffer it.

        Assigns a monotonically increasing event ID, stores the event in the
        ring buffer, and sends it to all active connections. Failed sends
        are silently ignored (disconnected clients will be cleaned up by
        the ping/pong mechanism).

        Args:
            event: The WSEvent to broadcast.
        """
        async with self._lock:
            event_id = self._next_event_id
            self._next_event_id += 1

        buffered = BufferedEvent(
            event_id=event_id,
            event_type=event.event_type,
            payload=event.payload,
            timestamp=event.timestamp,
        )
        self._event_buffer.append(buffered)

        # Send to all connected clients
        message = self._format_event_message(buffered)
        disconnected: list[WebSocket] = []

        for connection in list(self._active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up failed connections
        for conn in disconnected:
            await self.disconnect(conn)

    async def send_missed_events(
        self, websocket: WebSocket, last_event_id: int
    ) -> None:
        """Send events missed during disconnection.

        Replays all buffered events with IDs greater than last_event_id
        in chronological order. Limited to events in the ring buffer
        (up to 100 events).

        Args:
            websocket: The WebSocket connection to send missed events to.
            last_event_id: The last event ID the client received. All events
                with IDs greater than this will be sent.
        """
        missed_events = [
            ev for ev in self._event_buffer if ev.event_id > last_event_id
        ]

        # Events are already in chronological order in the deque
        for event in missed_events:
            message = self._format_event_message(event)
            try:
                await websocket.send_json(message)
            except Exception as exc:
                print(
                    f"[WebSocketManager] Failed to send missed event: {exc}",
                    file=sys.stderr,
                )
                break

    def _build_initial_state(self) -> dict[str, Any]:
        """Build the initial state snapshot for a new connection.

        Queries the database for embedding status counts and retrieves
        the last 50 activity events from the audit logger.

        Returns:
            A dictionary containing embedding_status_counts and recent_activity.
        """
        # Get embedding status counts from database
        embedding_counts = self._get_embedding_status_counts()

        # Get last 50 activity events from audit logger
        activity_events = self._get_recent_activity_events()

        return {
            "event_type": WSEventType.INITIAL_STATE.value,
            "payload": {
                "embedding_status_counts": embedding_counts,
                "recent_activity": activity_events,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": 0,  # Initial state is not a buffered event
        }

    def _get_embedding_status_counts(self) -> dict[str, int]:
        """Query the database for file embedding status counts.

        Returns:
            A dictionary with status as key and count as value.
        """
        session = SessionLocal()
        try:
            results = (
                session.query(File.embedding_status, func.count(File.id))
                .filter(File.is_deleted == False)  # noqa: E712
                .group_by(File.embedding_status)
                .all()
            )
            counts = {
                "pending": 0,
                "embedding": 0,
                "embedded": 0,
                "failed": 0,
                "stale": 0,
            }
            for status, count in results:
                if status in counts:
                    counts[status] = count
            return counts
        except Exception as exc:
            print(
                f"[WebSocketManager] Failed to get embedding status counts: {exc}",
                file=sys.stderr,
            )
            return {
                "pending": 0,
                "embedding": 0,
                "embedded": 0,
                "failed": 0,
                "stale": 0,
            }
        finally:
            session.close()

    def _get_recent_activity_events(self) -> list[dict[str, Any]]:
        """Get the last 50 activity events from the audit logger.

        Returns:
            A list of activity event dictionaries.
        """
        if self._audit_logger is None:
            return []

        try:
            records = self._audit_logger.get_recent_events(limit=50)
            events = []
            for record in records:
                events.append(
                    {
                        "id": record.id,
                        "timestamp": record.timestamp,
                        "event_type": record.event_type,
                        "file_id": record.file_id,
                        "actor": record.actor,
                        "details": record.details,
                    }
                )
            return events
        except Exception as exc:
            print(
                f"[WebSocketManager] Failed to get recent events: {exc}",
                file=sys.stderr,
            )
            return []

    def _format_event_message(self, event: BufferedEvent) -> dict[str, Any]:
        """Format a buffered event into a JSON-serializable message.

        Args:
            event: The BufferedEvent to format.

        Returns:
            A dictionary matching the WSMessage schema.
        """
        return {
            "event_type": event.event_type.value,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat(),
            "event_id": event.event_id,
        }

    async def _send_event(self, websocket: WebSocket, message: dict) -> None:
        """Send a JSON message to a single WebSocket connection.

        Args:
            websocket: The target WebSocket connection.
            message: The message dictionary to send.
        """
        await websocket.send_json(message)

    async def _ping_loop(self, websocket: WebSocket) -> None:
        """Send periodic pings to detect connection health.

        Sends a WebSocket ping every 30 seconds and expects a pong
        response. If no pong is received within the timeout, the
        connection is considered dead and removed.

        Args:
            websocket: The WebSocket connection to monitor.
        """
        try:
            while True:
                await asyncio.sleep(30)
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    # Connection is dead
                    break
        except asyncio.CancelledError:
            pass
        finally:
            # If the loop exits due to a failed ping, disconnect
            if websocket in self._active_connections:
                self._active_connections.discard(websocket)
                self._ping_tasks.pop(websocket, None)
