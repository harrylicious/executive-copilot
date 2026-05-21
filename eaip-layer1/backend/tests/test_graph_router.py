"""Unit tests for the graph router endpoints and layout algorithm."""

import math
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.relationship import Relationship
from app.routers.graph import _compute_radial_layout


# ─── Test fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_file(db, name, department, file_id=None):
    """Helper to create a file record."""
    now = datetime.now(timezone.utc)
    file = File(
        name=name,
        path=f"{department}/{name}",
        department=department,
        size=1024,
        tags=[],
        created_at=now,
        modified_at=now,
        content_hash="abc123",
    )
    if file_id:
        file.id = file_id
    db.add(file)
    db.commit()
    db.refresh(file)
    return file


# ─── Layout algorithm tests ─────────────────────────────────────────────────


class TestRadialLayout:
    """Tests for the radial layout algorithm."""

    def test_empty_files_returns_empty_positions(self):
        """Empty file list produces no positions."""
        positions = _compute_radial_layout([])
        assert positions == {}

    def test_single_file_gets_position(self, db_session):
        """A single file gets a valid position."""
        file = _create_file(db_session, "report.pdf", "Finance")
        positions = _compute_radial_layout([file])
        assert file.id in positions
        pos = positions[file.id]
        assert pos.x != 0 or pos.y != 0

    def test_files_in_same_department_grouped(self, db_session):
        """Files in the same department are positioned closer together than to distant departments."""
        f1 = _create_file(db_session, "budget.xlsx", "Finance")
        f2 = _create_file(db_session, "report.pdf", "Finance")
        f3 = _create_file(db_session, "policy.docx", "HR")
        f4 = _create_file(db_session, "strategy.pdf", "Executive")
        f5 = _create_file(db_session, "audit.txt", "IT_Audit")

        positions = _compute_radial_layout([f1, f2, f3, f4, f5])

        # Distance between same-department files (Finance)
        same_dept_dist = math.sqrt(
            (positions[f1.id].x - positions[f2.id].x) ** 2
            + (positions[f1.id].y - positions[f2.id].y) ** 2
        )
        # Average distance from Finance files to all other department files
        cross_dists = []
        for other in [f3, f4, f5]:
            for fin in [f1, f2]:
                d = math.sqrt(
                    (positions[fin.id].x - positions[other.id].x) ** 2
                    + (positions[fin.id].y - positions[other.id].y) ** 2
                )
                cross_dists.append(d)
        avg_cross_dist = sum(cross_dists) / len(cross_dists)
        assert same_dept_dist < avg_cross_dist

    def test_all_files_get_positions(self, db_session):
        """Every file gets a position in the layout."""
        files = [
            _create_file(db_session, f"file{i}.txt", dept)
            for i, dept in enumerate(["Finance", "HR", "Executive", "IT_Audit"])
        ]
        positions = _compute_radial_layout(files)
        assert len(positions) == len(files)
        for file in files:
            assert file.id in positions

    def test_many_files_per_department(self, db_session):
        """Layout handles many files in a single department (multi-ring)."""
        files = [
            _create_file(db_session, f"file{i}.txt", "Finance")
            for i in range(8)
        ]
        positions = _compute_radial_layout(files)
        assert len(positions) == 8
        # All positions should be unique
        pos_tuples = [(p.x, p.y) for p in positions.values()]
        assert len(set(pos_tuples)) == 8


# ─── Relationship endpoint logic tests ──────────────────────────────────────


class TestGraphEndpointLogic:
    """Tests for graph endpoint business logic."""

    def test_create_manual_relationship(self, db_session):
        """Creating a manual relationship persists correctly."""
        from app.services.relationship_engine import RelationshipEngine

        f1 = _create_file(db_session, "a.txt", "Finance")
        f2 = _create_file(db_session, "b.txt", "HR")

        engine = RelationshipEngine(db_session)
        rel = engine.create_manual_relationship(f1.id, f2.id, "references")

        assert rel.source_file_id == f1.id
        assert rel.target_file_id == f2.id
        assert rel.relationship_type == "references"
        assert rel.is_manual is True

    def test_delete_relationship(self, db_session):
        """Deleting a relationship removes it from the database."""
        from app.services.relationship_engine import RelationshipEngine

        f1 = _create_file(db_session, "a.txt", "Finance")
        f2 = _create_file(db_session, "b.txt", "HR")

        engine = RelationshipEngine(db_session)
        rel = engine.create_manual_relationship(f1.id, f2.id, "references")

        deleted = engine.delete_relationship(rel.id)
        assert deleted is True

        # Verify it's gone
        remaining = db_session.query(Relationship).filter(Relationship.id == rel.id).first()
        assert remaining is None

    def test_delete_nonexistent_relationship(self, db_session):
        """Deleting a non-existent relationship returns False."""
        from app.services.relationship_engine import RelationshipEngine

        engine = RelationshipEngine(db_session)
        deleted = engine.delete_relationship(9999)
        assert deleted is False
