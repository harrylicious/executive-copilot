"""In-memory conversation history store for chat sessions."""


class SessionStore:
    """In-memory conversation history store.

    Stores conversation turns per session as a list of {role, content} dicts.
    Each session is bounded to MAX_TURNS; when exceeded, the oldest turn is evicted.
    """

    MAX_TURNS: int = 20

    def __init__(self) -> None:
        self._sessions: dict[str, list[dict[str, str]]] = {}

    def get_history(self, session_id: str) -> list[dict[str, str]]:
        """Return conversation history for a session.

        Returns an empty list if the session_id is unknown.
        """
        return list(self._sessions.get(session_id, []))

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        """Add a conversation turn to a session.

        If the session exceeds MAX_TURNS after adding, the oldest turn is evicted.
        """
        if session_id not in self._sessions:
            self._sessions[session_id] = []

        self._sessions[session_id].append({"role": role, "content": content})

        if len(self._sessions[session_id]) > self.MAX_TURNS:
            self._sessions[session_id] = self._sessions[session_id][-self.MAX_TURNS:]

    def clear(self, session_id: str) -> None:
        """Remove a session entirely."""
        self._sessions.pop(session_id, None)
