"""Unit tests for the RelationshipEngine service."""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.relationship import Relationship
from app.services.relationship_engine import RelationshipEngine


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_files(db_session):
    """Create sample files across departments with tags."""
    now = datetime.utcnow()
    files = [
        File(
            name="budget_2024.xlsx",
            path="Finance/Budgets/budget_2024.xlsx",
            department="Finance",
            size=1024,
            tags=["budget", "2024"],
            created_at=now,
            modified_at=now,
            content_hash="abc123",
        ),
        File(
            name="forecast_q1.xlsx",
            path="Finance/Reports/forecast_q1.xlsx",
            department="Finance",
            size=2048,
            tags=["forecast", "2024"],
            created_at=now,
            modified_at=now,
            content_hash="def456",
        ),
        File(
            name="sales_report.pdf",
            path="Retail_Operations/Sales/sales_report.pdf",
            department="Retail_Operations",
            size=4096,
            tags=["sales", "2024"],
            created_at=now,
            modified_at=now,
            content_hash="ghi789",
        ),
        File(
            name="inventory.json",
            path="Retail_Operations/Inventory/inventory.json",
            department="Retail_Operations",
            size=512,
            tags=["inventory"],
            created_at=now,
            modified_at=now,
            content_hash="jkl012",
        ),
        File(
            name="policy_handbook.docx",
            path="HR/Policies/policy_handbook.docx",
            department="HR",
            size=8192,
            tags=[],
            created_at=now,
            modified_at=now,
            content_hash="mno345",
        ),
    ]
    for f in files:
        db_session.add(f)
    db_session.commit()
    for f in files:
        db_session.refresh(f)
    return files


class TestRecalculateForFile:
    """Tests for recalculate_for_file method."""

    def test_creates_department_relationships(self, db_session, sample_files):
        """Files in the same department get department edges when they don't share tags."""
        engine = RelationshipEngine(db_session)

        # Add a Finance file with no shared tags to test pure department edge
        now = datetime.utcnow()
        finance_no_tags = File(
            name="audit.txt",
            path="Finance/Reports/audit.txt",
            department="Finance",
            size=100,
            tags=["audit"],  # unique tag, not shared with others
            created_at=now,
            modified_at=now,
            content_hash="zzz999",
        )
        db_session.add(finance_no_tags)
        db_session.commit()
        db_session.refresh(finance_no_tags)

        engine.recalculate_for_file(finance_no_tags.id)
        db_session.commit()

        rels = db_session.query(Relationship).all()
        # Should have department relationships with other Finance files
        # (files 0 and 1 share "2024" tag with file 2, but finance_no_tags
        # only shares department with files 0 and 1)
        dept_rels = [r for r in rels if r.relationship_type == "department"]
        assert len(dept_rels) >= 1
        assert any(
            (r.source_file_id == finance_no_tags.id and r.target_file_id == sample_files[0].id)
            or (r.source_file_id == sample_files[0].id and r.target_file_id == finance_no_tags.id)
            for r in dept_rels
        )

    def test_creates_tag_relationships(self, db_session, sample_files):
        """Files sharing tags get tag edges."""
        engine = RelationshipEngine(db_session)
        # sample_files[0] has tags ["budget", "2024"]
        # sample_files[1] has tags ["forecast", "2024"]
        # sample_files[2] has tags ["sales", "2024"]
        # All three share the "2024" tag

        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        rels = db_session.query(Relationship).all()
        tag_rels = [r for r in rels if r.relationship_type == "tag"]
        # File 0 should have tag relationships with files 1 and 2 (shared "2024")
        assert len(tag_rels) == 2

    def test_tag_edge_replaces_department_edge(self, db_session, sample_files):
        """When both department and tag edges exist, only tag edge remains."""
        engine = RelationshipEngine(db_session)
        # Files 0 and 1 are both in Finance AND share the "2024" tag
        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        rels = db_session.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
        ).all()

        # Between files 0 and 1, only tag edge should exist (not department)
        pair_rels = [
            r for r in rels
            if (r.source_file_id == sample_files[0].id and r.target_file_id == sample_files[1].id)
            or (r.source_file_id == sample_files[1].id and r.target_file_id == sample_files[0].id)
        ]
        assert len(pair_rels) == 1
        assert pair_rels[0].relationship_type == "tag"

    def test_does_not_overwrite_manual_relationships(self, db_session, sample_files):
        """Manual relationships are preserved during recalculation."""
        engine = RelationshipEngine(db_session)

        # Create a manual relationship between files 0 and 1
        manual_rel = Relationship(
            source_file_id=sample_files[0].id,
            target_file_id=sample_files[1].id,
            relationship_type="manual",
            is_manual=True,
        )
        db_session.add(manual_rel)
        db_session.commit()

        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        # Manual relationship should still exist
        manual_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == True  # noqa: E712
        ).all()
        assert len(manual_rels) == 1
        assert manual_rels[0].relationship_type == "manual"

        # No auto-generated relationship should exist between files 0 and 1
        auto_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            Relationship.source_file_id == sample_files[0].id,
            Relationship.target_file_id == sample_files[1].id,
        ).all()
        assert len(auto_rels) == 0

    def test_nonexistent_file_does_nothing(self, db_session, sample_files):
        """Recalculating for a nonexistent file ID does not crash."""
        engine = RelationshipEngine(db_session)
        engine.recalculate_for_file(9999)
        db_session.commit()
        rels = db_session.query(Relationship).all()
        assert len(rels) == 0

    def test_file_with_no_tags_gets_only_department_edges(self, db_session, sample_files):
        """A file with no tags only gets department relationships."""
        engine = RelationshipEngine(db_session)
        # sample_files[4] is in HR with no tags, and is the only HR file
        engine.recalculate_for_file(sample_files[4].id)
        db_session.commit()

        rels = db_session.query(Relationship).all()
        # No other HR files, so no relationships at all
        assert len(rels) == 0


class TestRecalculateAll:
    """Tests for recalculate_all method."""

    def test_generates_all_relationships(self, db_session, sample_files):
        """Recalculate all creates relationships for every file."""
        engine = RelationshipEngine(db_session)
        engine.recalculate_all()

        rels = db_session.query(Relationship).all()
        # Should have relationships between files sharing departments or tags
        assert len(rels) > 0

    def test_removes_stale_auto_relationships(self, db_session, sample_files):
        """Recalculate all removes old auto relationships before regenerating."""
        engine = RelationshipEngine(db_session)

        # Create a stale auto relationship
        stale = Relationship(
            source_file_id=sample_files[0].id,
            target_file_id=sample_files[4].id,
            relationship_type="department",
            is_manual=False,
        )
        db_session.add(stale)
        db_session.commit()

        engine.recalculate_all()

        # The stale relationship should be gone (files 0 and 4 are in different depts)
        rels = db_session.query(Relationship).filter(
            Relationship.source_file_id == sample_files[0].id,
            Relationship.target_file_id == sample_files[4].id,
        ).all()
        assert len(rels) == 0

    def test_preserves_manual_relationships(self, db_session, sample_files):
        """Manual relationships survive recalculate_all."""
        engine = RelationshipEngine(db_session)

        manual_rel = Relationship(
            source_file_id=sample_files[0].id,
            target_file_id=sample_files[3].id,
            relationship_type="custom",
            is_manual=True,
        )
        db_session.add(manual_rel)
        db_session.commit()

        engine.recalculate_all()

        manual_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == True  # noqa: E712
        ).all()
        assert len(manual_rels) == 1
        assert manual_rels[0].relationship_type == "custom"


class TestManualRelationships:
    """Tests for manual relationship CRUD."""

    def test_create_manual_relationship(self, db_session, sample_files):
        """Creating a manual relationship persists it correctly."""
        engine = RelationshipEngine(db_session)
        rel = engine.create_manual_relationship(
            sample_files[0].id, sample_files[2].id, "related"
        )

        assert rel.id is not None
        assert rel.source_file_id == sample_files[0].id
        assert rel.target_file_id == sample_files[2].id
        assert rel.relationship_type == "related"
        assert rel.is_manual is True

    def test_manual_overrides_auto(self, db_session, sample_files):
        """Creating a manual relationship removes existing auto relationship."""
        engine = RelationshipEngine(db_session)

        # First create auto relationships
        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        # Now create manual relationship between files 0 and 2 (which had a tag edge)
        engine.create_manual_relationship(
            sample_files[0].id, sample_files[2].id, "override"
        )

        # Check that no auto relationship exists between 0 and 2
        auto_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == False,  # noqa: E712
            Relationship.source_file_id == sample_files[0].id,
            Relationship.target_file_id == sample_files[2].id,
        ).all()
        assert len(auto_rels) == 0

        # Manual relationship should exist
        manual_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == True,  # noqa: E712
            Relationship.source_file_id == sample_files[0].id,
            Relationship.target_file_id == sample_files[2].id,
        ).all()
        assert len(manual_rels) == 1

    def test_create_manual_updates_existing(self, db_session, sample_files):
        """Creating a manual relationship between an existing pair updates the type."""
        engine = RelationshipEngine(db_session)
        engine.create_manual_relationship(
            sample_files[0].id, sample_files[1].id, "first_type"
        )
        engine.create_manual_relationship(
            sample_files[0].id, sample_files[1].id, "second_type"
        )

        manual_rels = db_session.query(Relationship).filter(
            Relationship.is_manual == True  # noqa: E712
        ).all()
        assert len(manual_rels) == 1
        assert manual_rels[0].relationship_type == "second_type"

    def test_delete_relationship(self, db_session, sample_files):
        """Deleting a relationship removes it from the database."""
        engine = RelationshipEngine(db_session)
        rel = engine.create_manual_relationship(
            sample_files[0].id, sample_files[1].id, "test"
        )

        result = engine.delete_relationship(rel.id)
        assert result is True

        remaining = db_session.query(Relationship).all()
        assert len(remaining) == 0

    def test_delete_nonexistent_relationship(self, db_session, sample_files):
        """Deleting a nonexistent relationship returns False."""
        engine = RelationshipEngine(db_session)
        result = engine.delete_relationship(9999)
        assert result is False

    def test_get_all_relationships(self, db_session, sample_files):
        """get_all_relationships returns all relationships."""
        engine = RelationshipEngine(db_session)
        engine.create_manual_relationship(
            sample_files[0].id, sample_files[1].id, "manual_a"
        )
        engine.recalculate_for_file(sample_files[2].id)
        db_session.commit()

        rels = engine.get_all_relationships()
        assert len(rels) >= 1


class TestDeduplication:
    """Tests for relationship deduplication logic."""

    def test_no_duplicate_relationships(self, db_session, sample_files):
        """Running recalculate twice does not create duplicates."""
        engine = RelationshipEngine(db_session)
        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        count_first = db_session.query(Relationship).count()

        engine.recalculate_for_file(sample_files[0].id)
        db_session.commit()

        count_second = db_session.query(Relationship).count()
        assert count_first == count_second

    def test_recalculate_all_no_duplicates(self, db_session, sample_files):
        """Running recalculate_all twice does not create duplicates."""
        engine = RelationshipEngine(db_session)
        engine.recalculate_all()

        count_first = db_session.query(Relationship).count()

        engine.recalculate_all()

        count_second = db_session.query(Relationship).count()
        assert count_first == count_second
