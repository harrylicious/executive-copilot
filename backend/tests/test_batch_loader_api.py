"""Unit tests for the Batch Loader API endpoints in the ingestion router."""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.batch_execution_log import BatchExecutionLog
from app.models.batch_loader_config import BatchLoaderConfig


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


@pytest.fixture
def sample_config(db_session):
    """Create a sample batch loader config in the database."""
    now = datetime.now(timezone.utc)
    config = BatchLoaderConfig(
        id=str(uuid.uuid4()),
        name="Test Batch Loader",
        source_path="/data/documents",
        source_type="local",
        cron_expression="0 2 * * *",
        department="Finance",
        subfolder="Reports",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


class TestCreateBatchConfig:
    """Tests for POST /api/ingestion/batch-configs."""

    def test_create_config_with_local_path(self, client):
        """Should create a batch config with a valid local path."""
        payload = {
            "name": "Local Docs Loader",
            "source_path": "/data/shared/documents",
            "source_type": "local",
            "cron_expression": "0 3 * * *",
            "department": "HR",
            "subfolder": "Policies",
        }
        response = client.post("/api/ingestion/batch-configs", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Local Docs Loader"
        assert data["sourcePath"] == "/data/shared/documents"
        assert data["sourceType"] == "local"
        assert data["cronExpression"] == "0 3 * * *"
        assert data["department"] == "HR"
        assert data["subfolder"] == "Policies"
        assert data["isActive"] is True
        assert "id" in data
        # Verify it's a valid UUID
        uuid.UUID(data["id"])

    def test_create_config_with_s3_uri(self, client):
        """Should create a batch config with a valid S3 URI."""
        payload = {
            "name": "S3 Loader",
            "source_path": "s3://my-bucket/documents/incoming",
            "source_type": "s3",
            "cron_expression": "30 1 * * *",
            "department": "Legal",
        }
        response = client.post("/api/ingestion/batch-configs", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert data["sourcePath"] == "s3://my-bucket/documents/incoming"
        assert data["sourceType"] == "s3"
        assert data["subfolder"] is None

    def test_create_config_invalid_source_path(self, client):
        """Should reject config with invalid source path."""
        payload = {
            "name": "Bad Loader",
            "source_path": "relative/path/here",
            "source_type": "local",
            "cron_expression": "0 0 * * *",
            "department": "IT",
        }
        response = client.post("/api/ingestion/batch-configs", json=payload)
        assert response.status_code == 422

    def test_create_config_missing_required_fields(self, client):
        """Should reject config with missing required fields."""
        payload = {
            "name": "Incomplete",
        }
        response = client.post("/api/ingestion/batch-configs", json=payload)
        assert response.status_code == 422


class TestListBatchConfigs:
    """Tests for GET /api/ingestion/batch-configs."""

    def test_list_empty(self, client):
        """Should return empty list when no configs exist."""
        response = client.get("/api/ingestion/batch-configs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_with_configs(self, client, sample_config):
        """Should return all configs."""
        response = client.get("/api/ingestion/batch-configs")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == sample_config.id
        assert data[0]["name"] == "Test Batch Loader"


class TestUpdateBatchConfig:
    """Tests for PUT /api/ingestion/batch-configs/{id}."""

    def test_update_name(self, client, sample_config):
        """Should update the config name."""
        payload = {"name": "Updated Name"}
        response = client.put(
            f"/api/ingestion/batch-configs/{sample_config.id}", json=payload
        )
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["sourcePath"] == sample_config.source_path

    def test_update_source_path_valid(self, client, sample_config):
        """Should update source path when valid."""
        payload = {"source_path": "/new/valid/path"}
        response = client.put(
            f"/api/ingestion/batch-configs/{sample_config.id}", json=payload
        )
        assert response.status_code == 200
        assert response.json()["sourcePath"] == "/new/valid/path"

    def test_update_source_path_invalid(self, client, sample_config):
        """Should reject update with invalid source path."""
        payload = {"source_path": "not-absolute"}
        response = client.put(
            f"/api/ingestion/batch-configs/{sample_config.id}", json=payload
        )
        assert response.status_code == 422

    def test_update_nonexistent_config(self, client):
        """Should return 404 for nonexistent config."""
        payload = {"name": "Ghost"}
        response = client.put(
            f"/api/ingestion/batch-configs/{uuid.uuid4()}", json=payload
        )
        assert response.status_code == 404


class TestDeactivateBatchConfig:
    """Tests for DELETE /api/ingestion/batch-configs/{id}."""

    def test_deactivate_config(self, client, sample_config, db_session):
        """Should soft-delete by setting is_active=False."""
        response = client.delete(
            f"/api/ingestion/batch-configs/{sample_config.id}"
        )
        assert response.status_code == 204

        # Verify in database
        db_session.refresh(sample_config)
        assert sample_config.is_active is False

    def test_deactivate_nonexistent_config(self, client):
        """Should return 404 for nonexistent config."""
        response = client.delete(
            f"/api/ingestion/batch-configs/{uuid.uuid4()}"
        )
        assert response.status_code == 404


class TestListBatchConfigExecutions:
    """Tests for GET /api/ingestion/batch-configs/{id}/executions."""

    def test_list_executions_empty(self, client, sample_config):
        """Should return empty list when no executions exist."""
        response = client.get(
            f"/api/ingestion/batch-configs/{sample_config.id}/executions"
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_list_executions_with_data(self, client, sample_config, db_session):
        """Should return execution history for the config."""
        now = datetime.now(timezone.utc)
        log = BatchExecutionLog(
            config_id=sample_config.id,
            started_at=now,
            completed_at=now,
            files_found=10,
            files_submitted=8,
            files_skipped=2,
            errors=None,
            status="completed",
        )
        db_session.add(log)
        db_session.commit()

        response = client.get(
            f"/api/ingestion/batch-configs/{sample_config.id}/executions"
        )
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 1
        assert data[0]["configId"] == sample_config.id
        assert data[0]["filesFound"] == 10
        assert data[0]["filesSubmitted"] == 8
        assert data[0]["filesSkipped"] == 2
        assert data[0]["status"] == "completed"

    def test_list_executions_nonexistent_config(self, client):
        """Should return 404 for nonexistent config."""
        response = client.get(
            f"/api/ingestion/batch-configs/{uuid.uuid4()}/executions"
        )
        assert response.status_code == 404
