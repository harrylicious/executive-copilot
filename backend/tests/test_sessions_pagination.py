"""Unit tests for GET /api/sessions pagination support."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.chat_session import ChatSession


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
def client(db_session):
    """Create a test client with overridden DB dependency."""

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _create_sessions(db_session, count: int):
    """Helper to create N sessions with sequential timestamps."""
    from datetime import datetime, timedelta

    base_time = datetime(2024, 1, 1, 12, 0, 0)
    for i in range(count):
        session = ChatSession(
            id=f"sess-{i:03d}",
            title=f"Session {i}",
            retrieval_mode="combined",
            created_at=base_time + timedelta(minutes=i),
            updated_at=base_time + timedelta(minutes=i),
        )
        db_session.add(session)
    db_session.commit()


class TestGetSessionsPagination:
    """Tests for GET /api/sessions with pagination."""

    def test_returns_paginated_response_shape(self, client, db_session):
        """Response should contain items, total, and has_more fields."""
        _create_sessions(db_session, 5)
        response = client.get("/api/sessions")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "has_more" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)
        assert isinstance(data["has_more"], bool)

    def test_default_page_and_page_size(self, client, db_session):
        """Without params, should return page 1 with page_size 20."""
        _create_sessions(db_session, 25)
        response = client.get("/api/sessions")
        data = response.json()

        assert len(data["items"]) == 20
        assert data["total"] == 25
        assert data["has_more"] is True

    def test_custom_page_size(self, client, db_session):
        """Should respect custom page_size parameter."""
        _create_sessions(db_session, 10)
        response = client.get("/api/sessions?page_size=5")
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total"] == 10
        assert data["has_more"] is True

    def test_second_page(self, client, db_session):
        """Should return the correct items for page 2."""
        _create_sessions(db_session, 10)
        response = client.get("/api/sessions?page=2&page_size=5")
        data = response.json()

        assert len(data["items"]) == 5
        assert data["total"] == 10
        assert data["has_more"] is False

    def test_last_page_has_more_false(self, client, db_session):
        """has_more should be False on the last page."""
        _create_sessions(db_session, 10)
        response = client.get("/api/sessions?page=2&page_size=5")
        data = response.json()

        assert data["has_more"] is False

    def test_empty_result(self, client):
        """Should return empty items with total 0 when no sessions exist."""
        response = client.get("/api/sessions")
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    def test_page_beyond_total(self, client, db_session):
        """Requesting a page beyond total should return empty items."""
        _create_sessions(db_session, 5)
        response = client.get("/api/sessions?page=10&page_size=5")
        data = response.json()

        assert data["items"] == []
        assert data["total"] == 5
        assert data["has_more"] is False

    def test_results_sorted_by_updated_at_desc(self, client, db_session):
        """Sessions should be sorted by most recent activity first."""
        _create_sessions(db_session, 5)
        response = client.get("/api/sessions?page_size=5")
        data = response.json()

        # Sessions were created with increasing timestamps, so most recent is last
        items = data["items"]
        assert items[0]["title"] == "Session 4"
        assert items[-1]["title"] == "Session 0"

    def test_invalid_page_zero_returns_422(self, client):
        """page=0 should return 422 validation error."""
        response = client.get("/api/sessions?page=0")
        assert response.status_code == 422

    def test_invalid_page_negative_returns_422(self, client):
        """page=-1 should return 422 validation error."""
        response = client.get("/api/sessions?page=-1")
        assert response.status_code == 422

    def test_invalid_page_size_zero_returns_422(self, client):
        """page_size=0 should return 422 validation error."""
        response = client.get("/api/sessions?page_size=0")
        assert response.status_code == 422

    def test_invalid_page_size_exceeds_max_returns_422(self, client):
        """page_size=101 should return 422 validation error."""
        response = client.get("/api/sessions?page_size=101")
        assert response.status_code == 422

    def test_invalid_page_non_integer_returns_422(self, client):
        """Non-integer page should return 422 validation error."""
        response = client.get("/api/sessions?page=abc")
        assert response.status_code == 422

    def test_page_size_boundary_1(self, client, db_session):
        """page_size=1 is valid and should return 1 item per page."""
        _create_sessions(db_session, 3)
        response = client.get("/api/sessions?page_size=1")
        data = response.json()

        assert len(data["items"]) == 1
        assert data["total"] == 3
        assert data["has_more"] is True

    def test_page_size_boundary_100(self, client, db_session):
        """page_size=100 is valid and should work."""
        _create_sessions(db_session, 3)
        response = client.get("/api/sessions?page_size=100")
        data = response.json()

        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["has_more"] is False
