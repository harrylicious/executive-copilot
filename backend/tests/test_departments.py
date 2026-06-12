"""Unit tests for the departments router."""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models.file import File


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database session for testing.

    Uses StaticPool and check_same_thread=False to allow the same
    in-memory database to be shared across threads (required for
    FastAPI TestClient which runs endpoints in a separate thread).
    """
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


class TestGetDepartments:
    """Tests for GET /api/departments endpoint."""

    def test_returns_all_departments(self, client):
        """Should return all six departments as root nodes."""
        response = client.get("/api/departments")
        assert response.status_code == 200

        data = response.json()
        assert len(data) == 6

        dept_names = {node["name"] for node in data}
        assert dept_names == {
            "Finance",
            "Retail_Operations",
            "HR",
            "Supply_Chain",
            "Executive",
            "IT_Audit",
        }

    def test_department_nodes_have_correct_type(self, client):
        """Department root nodes should have type 'department'."""
        response = client.get("/api/departments")
        data = response.json()

        for node in data:
            assert node["type"] == "department"

    def test_departments_have_subfolder_children(self, client):
        """Each department should have its predefined subfolders as children."""
        response = client.get("/api/departments")
        data = response.json()

        # Find Finance department
        finance = next(n for n in data if n["name"] == "Finance")
        subfolder_names = [child["name"] for child in finance["children"]]
        assert subfolder_names == ["Budgets", "Reports", "Invoices"]

        # All subfolder children should have type 'folder'
        for child in finance["children"]:
            assert child["type"] == "folder"

    def test_files_nested_under_subfolders(self, client, db_session):
        """Files should appear as children of their subfolder."""
        # Add a file to the database
        file = File(
            name="budget_2024.xlsx",
            path="Finance/Budgets/budget_2024.xlsx",
            department="Finance",
            size=1024,
            tags=[],
            created_at=datetime(2024, 1, 1),
            modified_at=datetime(2024, 1, 15),
            content_hash="abc123",
        )
        db_session.add(file)
        db_session.commit()

        response = client.get("/api/departments")
        data = response.json()

        # Navigate to Finance > Budgets
        finance = next(n for n in data if n["name"] == "Finance")
        budgets = next(c for c in finance["children"] if c["name"] == "Budgets")

        assert len(budgets["children"]) == 1
        file_node = budgets["children"][0]
        assert file_node["name"] == "budget_2024.xlsx"
        assert file_node["type"] == "file"
        assert file_node["fileId"] == file.id

    def test_empty_subfolders_have_empty_children(self, client):
        """Subfolders with no files should have an empty children list."""
        response = client.get("/api/departments")
        data = response.json()

        finance = next(n for n in data if n["name"] == "Finance")
        for subfolder in finance["children"]:
            assert subfolder["children"] == []

    def test_multiple_files_in_same_subfolder(self, client, db_session):
        """Multiple files in the same subfolder should all appear."""
        files = [
            File(
                name="report_q1.pdf",
                path="Finance/Reports/report_q1.pdf",
                department="Finance",
                size=2048,
                tags=[],
                created_at=datetime(2024, 3, 1),
                modified_at=datetime(2024, 3, 1),
                content_hash="hash1",
            ),
            File(
                name="report_q2.pdf",
                path="Finance/Reports/report_q2.pdf",
                department="Finance",
                size=3072,
                tags=[],
                created_at=datetime(2024, 6, 1),
                modified_at=datetime(2024, 6, 1),
                content_hash="hash2",
            ),
        ]
        db_session.add_all(files)
        db_session.commit()

        response = client.get("/api/departments")
        data = response.json()

        finance = next(n for n in data if n["name"] == "Finance")
        reports = next(c for c in finance["children"] if c["name"] == "Reports")

        assert len(reports["children"]) == 2
        file_names = {f["name"] for f in reports["children"]}
        assert file_names == {"report_q1.pdf", "report_q2.pdf"}
