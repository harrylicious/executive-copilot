"""Pydantic schemas for ingestion pipeline API requests and responses."""

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    """Request metadata for a single file upload (sent as form fields alongside the file)."""

    department: str = Field(..., min_length=1, description="Target department for the uploaded file")
    subfolder: str | None = Field(default=None, description="Target subfolder within the department")
    tags: list[str] = Field(default_factory=list, description="Optional tags for the uploaded file")


class UploadResponse(BaseModel):
    """Response for a single file upload, returning the created ingestion job."""

    job_id: str
    file_name: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BatchUploadResponse(BaseModel):
    """Response for a batch upload, returning all created ingestion jobs."""

    jobs: list[UploadResponse]
    total: int = Field(description="Total number of jobs created")


class StageLogResponse(BaseModel):
    """Response schema for a single pipeline stage log entry."""

    stage: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    details: dict | None = None

    class Config:
        from_attributes = True


class IngestionJobResponse(BaseModel):
    """Full response for an ingestion job including stage history."""

    id: str
    file_name: str
    file_size: int
    department: str
    subfolder: str | None = None
    status: str
    current_stage: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    failure_stage: str | None = None
    content_hash: str | None = None
    sensitivity_level: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    stages: list[StageLogResponse] = []

    class Config:
        from_attributes = True


class JobListResponse(BaseModel):
    """Paginated response for listing ingestion jobs with filtering."""

    jobs: list[IngestionJobResponse]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    """Standardized error response for ingestion API endpoints."""

    error_code: str = Field(description="Machine-readable error code (e.g., FILE_TOO_LARGE)")
    message: str = Field(description="Human-readable error description")
    details: dict | None = Field(default=None, description="Additional context about the error")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
