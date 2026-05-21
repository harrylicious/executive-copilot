"""Property-based tests for database schema creation.

**Validates: Requirements 11.6**

Property 26: Additive schema creation preserves existing tables and data.
When Base.metadata.create_all() is called, existing tables (files, relationships, sync_log)
and their data are preserved. New GraphRAG tables (chunks, entities, entity_relationships,
communities, embedding_log) are created alongside existing ones. Data in existing tables
is not modified or deleted.
"""

from datetime import datetime

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.file import File
from app.models.relationship import Relationship
from app.models.sync_log import SyncLog
from app.models.chunk import Chunk
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship
from app.models.community import Community
from app.models.embedding_log import EmbeddingLog


# --- Strategies ---

# Strategy for generating file records
file_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip() != "")

departments = st.sampled_from(["Finance", "HR", "Executive", "IT", "Legal", "Supply_Chain"])

file_records_st = st.lists(
    st.fixed_dictionaries({
        "name": file_names,
        "department": departments,
        "size": st.integers(min_value=1, max_value=100000),
        "content_hash": st.text(alphabet="abcdef0123456789", min_size=8, max_size=32),
    }),
    min_size=1,
    max_size=5,
)

relationship_types = st.sampled_from(["department", "tag", "manual"])

sync_statuses = st.sampled_from(["success", "error"])

sync_log_records_st = st.lists(
    st.fixed_dictionaries({
        "files_added": st.integers(min_value=0, max_value=100),
        "files_updated": st.integers(min_value=0, max_value=100),
        "files_removed": st.integers(min_value=0, max_value=100),
        "status": sync_statuses,
    }),
    min_size=0,
    max_size=3,
)


# --- Property Test ---


class TestAdditiveSchemaCreation:
    """Property 26: Additive schema creation preserves existing tables and data."""

    @given(
        file_records=file_records_st,
        sync_logs=sync_log_records_st,
        rel_type=relationship_types,
    )
    @settings(max_examples=50, deadline=None)
    def test_create_all_preserves_existing_tables_and_data(
        self, file_records, sync_logs, rel_type
    ):
        """
        **Validates: Requirements 11.6**

        Given a database with existing tables (files, relationships, sync_log) containing data,
        when Base.metadata.create_all() is called (simulating app startup),
        then:
        1. Existing tables still exist
        2. All data in existing tables is preserved (not modified or deleted)
        3. New GraphRAG tables (chunks, entities, entity_relationships, communities, embedding_log)
           are created alongside existing ones
        """
        # Step 1: Create a fresh in-memory database with ONLY the pre-existing tables
        engine = create_engine("sqlite:///:memory:", echo=False)

        # Create only the "legacy" tables first (files, relationships, sync_log)
        File.__table__.create(engine, checkfirst=True)
        Relationship.__table__.create(engine, checkfirst=True)
        SyncLog.__table__.create(engine, checkfirst=True)

        Session = sessionmaker(bind=engine)
        session = Session()

        # Step 2: Insert data into existing tables
        now = datetime.utcnow()
        inserted_files = []
        for i, rec in enumerate(file_records):
            f = File(
                name=rec["name"],
                path=f"{rec['department']}/folder/file_{i}.txt",
                department=rec["department"],
                size=rec["size"],
                content_hash=rec["content_hash"],
                created_at=now,
                modified_at=now,
            )
            session.add(f)
            inserted_files.append(rec)
        session.flush()

        # Add relationships between files if we have at least 2
        file_ids = [f.id for f in session.query(File).all()]
        inserted_relationships = []
        if len(file_ids) >= 2:
            rel = Relationship(
                source_file_id=file_ids[0],
                target_file_id=file_ids[1],
                relationship_type=rel_type,
                is_manual=(rel_type == "manual"),
            )
            session.add(rel)
            inserted_relationships.append(rel)

        # Add sync log entries
        inserted_sync_logs = []
        for log_rec in sync_logs:
            log = SyncLog(
                timestamp=now,
                files_added=log_rec["files_added"],
                files_updated=log_rec["files_updated"],
                files_removed=log_rec["files_removed"],
                status=log_rec["status"],
            )
            session.add(log)
            inserted_sync_logs.append(log_rec)

        session.commit()

        # Record pre-create_all state
        pre_file_count = session.query(File).count()
        pre_rel_count = session.query(Relationship).count()
        pre_sync_count = session.query(SyncLog).count()
        pre_file_data = [
            (f.name, f.path, f.department, f.size, f.content_hash)
            for f in session.query(File).order_by(File.id).all()
        ]
        pre_rel_data = [
            (r.source_file_id, r.target_file_id, r.relationship_type, r.is_manual)
            for r in session.query(Relationship).order_by(Relationship.id).all()
        ]
        pre_sync_data = [
            (s.files_added, s.files_updated, s.files_removed, s.status)
            for s in session.query(SyncLog).order_by(SyncLog.id).all()
        ]

        # Step 3: Call Base.metadata.create_all() — this is what the app does on startup
        Base.metadata.create_all(engine)

        # Step 4: Verify existing tables still exist
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        assert "files" in table_names, "files table should still exist"
        assert "relationships" in table_names, "relationships table should still exist"
        assert "sync_log" in table_names, "sync_log table should still exist"

        # Step 5: Verify new GraphRAG tables were created
        assert "chunks" in table_names, "chunks table should be created"
        assert "entities" in table_names, "entities table should be created"
        assert "entity_relationships" in table_names, "entity_relationships table should be created"
        assert "communities" in table_names, "communities table should be created"
        assert "embedding_log" in table_names, "embedding_log table should be created"

        # Step 6: Verify data in existing tables is preserved (not modified or deleted)
        post_file_count = session.query(File).count()
        post_rel_count = session.query(Relationship).count()
        post_sync_count = session.query(SyncLog).count()

        assert post_file_count == pre_file_count, (
            f"File count changed: {pre_file_count} -> {post_file_count}"
        )
        assert post_rel_count == pre_rel_count, (
            f"Relationship count changed: {pre_rel_count} -> {post_rel_count}"
        )
        assert post_sync_count == pre_sync_count, (
            f"SyncLog count changed: {pre_sync_count} -> {post_sync_count}"
        )

        # Verify actual data content is unchanged
        post_file_data = [
            (f.name, f.path, f.department, f.size, f.content_hash)
            for f in session.query(File).order_by(File.id).all()
        ]
        post_rel_data = [
            (r.source_file_id, r.target_file_id, r.relationship_type, r.is_manual)
            for r in session.query(Relationship).order_by(Relationship.id).all()
        ]
        post_sync_data = [
            (s.files_added, s.files_updated, s.files_removed, s.status)
            for s in session.query(SyncLog).order_by(SyncLog.id).all()
        ]

        assert post_file_data == pre_file_data, "File data was modified after create_all()"
        assert post_rel_data == pre_rel_data, "Relationship data was modified after create_all()"
        assert post_sync_data == pre_sync_data, "SyncLog data was modified after create_all()"

        # Step 7: Verify new tables are empty (no spurious data)
        assert session.query(Chunk).count() == 0, "chunks table should be empty after creation"
        assert session.query(Entity).count() == 0, "entities table should be empty after creation"
        assert session.query(EntityRelationship).count() == 0, (
            "entity_relationships table should be empty after creation"
        )
        assert session.query(Community).count() == 0, "communities table should be empty after creation"
        assert session.query(EmbeddingLog).count() == 0, (
            "embedding_log table should be empty after creation"
        )

        session.close()
        engine.dispose()
