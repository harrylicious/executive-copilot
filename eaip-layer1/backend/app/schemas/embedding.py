"""Pydantic schemas for embedding-related API requests and responses."""

from datetime import datetime

from pydantic import BaseModel


class EmbeddingJobRequest(BaseModel):
    """Optional filters for embedding job."""

    file_id: int | None = None


class EmbeddingJobResponse(BaseModel):
    """Response from an embedding job."""

    job_id: int
    files_processed: int
    chunks_generated: int
    errors: list[dict]
    status: str  # "success", "partial_success", "error"


class EmbeddingStatusResponse(BaseModel):
    """Current embedding status of the knowledge base."""

    total_files_embedded: int
    files_pending: int
    last_job_timestamp: datetime | None
