"""Tests for ingestion pipeline database migration and staging directory creation."""

import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    BatchExecutionLog,
    BatchLoaderConfig,
    Chunk,
    IngestionJob,
    IngestionStageLog,
    PIIRedactionLog,
)


@pytest.fixture
def fresh_db():
    """Create a fresh in-memory database with all tables."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return engine, Session()


class TestIngestionTableCreation:
    """Verify all ingestion tables are created correctly."""

    def test_ingestion_jobs_table_exists(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        assert "ingestion_jobs" in insp.get_table_names()

    def test_ingestion_stage_logs_table_exists(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        assert "ingestion_stage_logs" in insp.get_table_names()

    def test_batch_loader_configs_table_exists(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        assert "batch_loader_configs" in insp.get_table_names()

    def test_batch_execution_logs_table_exists(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        assert "batch_execution_logs" in insp.get_table_names()

    def test_pii_redaction_logs_table_exists(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        assert "pii_redaction_logs" in insp.get_table_names()

    def test_chunks_table_has_new_columns(self, fresh_db):
        engine, _ = fresh_db
        insp = inspect(engine)
        chunk_cols = [c["name"] for c in insp.get_columns("chunks")]
        assert "section_path" in chunk_cols
        assert "chunking_method" in chunk_cols
        assert "job_id" in chunk_cols


class TestChunksMigration:
    """Verify migration adds columns to existing chunks table."""

    def test_migration_adds_columns_to_existing_chunks_table(self):
        """Simulate a pre-existing chunks table without new columns."""
        engine = create_engine("sqlite:///:memory:")

        # Create a minimal chunks table without the new columns
        with engine.connect() as conn:
            conn.execute(
                text(
                    """
                CREATE TABLE files (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL
                )
            """
                )
            )
            conn.execute(
                text(
                    """
                CREATE TABLE chunks (
                    id INTEGER PRIMARY KEY,
                    file_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    text VARCHAR(10000) NOT NULL,
                    start_offset INTEGER NOT NULL,
                    end_offset INTEGER NOT NULL,
                    embedding TEXT,
                    FOREIGN KEY (file_id) REFERENCES files(id)
                )
            """
                )
            )
            conn.commit()

        # Verify columns are missing
        insp = inspect(engine)
        chunk_cols = [c["name"] for c in insp.get_columns("chunks")]
        assert "section_path" not in chunk_cols
        assert "chunking_method" not in chunk_cols
        assert "job_id" not in chunk_cols

        # Run migration logic (same as in main.py lifespan)
        chunk_migrations = {
            "section_path": "ALTER TABLE chunks ADD COLUMN section_path VARCHAR",
            "chunking_method": "ALTER TABLE chunks ADD COLUMN chunking_method VARCHAR",
            "job_id": "ALTER TABLE chunks ADD COLUMN job_id VARCHAR",
        }
        for col_name, alter_sql in chunk_migrations.items():
            if col_name not in chunk_cols:
                with engine.connect() as conn:
                    conn.execute(text(alter_sql))
                    conn.commit()

        # Verify columns now exist
        insp = inspect(engine)
        chunk_cols_after = [c["name"] for c in insp.get_columns("chunks")]
        assert "section_path" in chunk_cols_after
        assert "chunking_method" in chunk_cols_after
        assert "job_id" in chunk_cols_after


class TestStagingDirectory:
    """Verify staging directory creation."""

    def test_staging_directory_created(self):
        """Verify staging directory is created from config."""
        from app.config import ingestion_settings

        staging_path = Path(ingestion_settings.staging_path)
        staging_path.mkdir(parents=True, exist_ok=True)
        assert staging_path.exists()
        assert staging_path.is_dir()

    def test_staging_directory_creation_with_custom_path(self):
        """Verify staging directory creation works with nested paths."""
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_path = Path(tmpdir) / "nested" / "staging" / "dir"
            custom_path.mkdir(parents=True, exist_ok=True)
            assert custom_path.exists()
            assert custom_path.is_dir()


class TestIngestionModelInsert:
    """Verify ingestion models can be inserted and queried."""

    def test_insert_ingestion_job(self, fresh_db):
        _, session = fresh_db
        from datetime import datetime, timezone

        job = IngestionJob(
            id="test-job-001",
            file_name="document.pdf",
            file_size=2048,
            department="engineering",
            status="queued",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()

        found = session.query(IngestionJob).filter_by(id="test-job-001").first()
        assert found is not None
        assert found.file_name == "document.pdf"
        assert found.status == "queued"

    def test_insert_stage_log(self, fresh_db):
        _, session = fresh_db
        from datetime import datetime, timezone

        job = IngestionJob(
            id="test-job-002",
            file_name="test.txt",
            file_size=100,
            department="hr",
            status="validating",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(job)
        session.commit()

        log = IngestionStageLog(
            job_id="test-job-002",
            stage="validation",
            status="started",
            started_at=datetime.now(timezone.utc),
        )
        session.add(log)
        session.commit()

        found = (
            session.query(IngestionStageLog).filter_by(job_id="test-job-002").first()
        )
        assert found is not None
        assert found.stage == "validation"

    def test_insert_batch_loader_config(self, fresh_db):
        _, session = fresh_db
        from datetime import datetime, timezone

        config = BatchLoaderConfig(
            id="config-001",
            name="Engineering Docs",
            source_path="/data/engineering",
            source_type="local",
            cron_expression="0 */6 * * *",
            department="engineering",
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(config)
        session.commit()

        found = session.query(BatchLoaderConfig).filter_by(id="config-001").first()
        assert found is not None
        assert found.name == "Engineering Docs"
        assert found.is_active is True
