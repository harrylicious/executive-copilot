"""Unit tests for SessionStore."""

import pytest

from app.services.langchain.session_store import SessionStore


class TestSessionStore:
    """Tests for the in-memory session store."""

    def setup_method(self):
        self.store = SessionStore()

    def test_get_history_unknown_session_returns_empty_list(self):
        """Unknown session IDs return an empty list."""
        result = self.store.get_history("nonexistent")
        assert result == []

    def test_add_turn_and_get_history(self):
        """Adding a turn makes it retrievable via get_history."""
        self.store.add_turn("s1", "user", "hello")
        history = self.store.get_history("s1")
        assert history == [{"role": "user", "content": "hello"}]

    def test_add_multiple_turns(self):
        """Multiple turns are stored in order."""
        self.store.add_turn("s1", "user", "hi")
        self.store.add_turn("s1", "assistant", "hello")
        self.store.add_turn("s1", "user", "how are you?")
        history = self.store.get_history("s1")
        assert len(history) == 3
        assert history[0] == {"role": "user", "content": "hi"}
        assert history[1] == {"role": "assistant", "content": "hello"}
        assert history[2] == {"role": "user", "content": "how are you?"}

    def test_max_turns_eviction(self):
        """When exceeding MAX_TURNS, the oldest turn is evicted."""
        for i in range(21):
            self.store.add_turn("s1", "user", f"message {i}")

        history = self.store.get_history("s1")
        assert len(history) == 20
        # Oldest message (message 0) should be evicted
        assert history[0] == {"role": "user", "content": "message 1"}
        assert history[-1] == {"role": "user", "content": "message 20"}

    def test_max_turns_constant_is_20(self):
        """MAX_TURNS is set to 20."""
        assert SessionStore.MAX_TURNS == 20

    def test_eviction_keeps_most_recent(self):
        """After eviction, the most recent MAX_TURNS messages are kept."""
        for i in range(25):
            self.store.add_turn("s1", "user", f"msg {i}")

        history = self.store.get_history("s1")
        assert len(history) == 20
        # Should have messages 5 through 24
        assert history[0] == {"role": "user", "content": "msg 5"}
        assert history[-1] == {"role": "user", "content": "msg 24"}

    def test_clear_removes_session(self):
        """clear() removes the session entirely."""
        self.store.add_turn("s1", "user", "hello")
        self.store.clear("s1")
        assert self.store.get_history("s1") == []

    def test_clear_nonexistent_session_no_error(self):
        """Clearing a nonexistent session does not raise."""
        self.store.clear("nonexistent")  # Should not raise

    def test_sessions_are_independent(self):
        """Different session IDs maintain independent histories."""
        self.store.add_turn("s1", "user", "hello from s1")
        self.store.add_turn("s2", "user", "hello from s2")

        assert self.store.get_history("s1") == [{"role": "user", "content": "hello from s1"}]
        assert self.store.get_history("s2") == [{"role": "user", "content": "hello from s2"}]

    def test_get_history_returns_copy(self):
        """get_history returns a copy, not a reference to internal state."""
        self.store.add_turn("s1", "user", "hello")
        history = self.store.get_history("s1")
        history.append({"role": "user", "content": "injected"})
        # Internal state should not be affected
        assert len(self.store.get_history("s1")) == 1

    def test_clear_does_not_affect_other_sessions(self):
        """Clearing one session does not affect others."""
        self.store.add_turn("s1", "user", "msg1")
        self.store.add_turn("s2", "user", "msg2")
        self.store.clear("s1")
        assert self.store.get_history("s1") == []
        assert self.store.get_history("s2") == [{"role": "user", "content": "msg2"}]
