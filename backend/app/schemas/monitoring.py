"""Pydantic schemas for monitoring API requests and responses."""

from datetime import datetime

from pydantic import BaseModel


class FileStatusResponse(BaseModel):
    id: int
    name: str
    path: str
    department: str
    embedding_status: str | None
    current_version: int | None
    modified_at: datetime
    file_size: int


class FileVersionResponse(BaseModel):
    version_number: int
    content_hash: str
    file_size: int
    timestamp: datetime
    is_restore: bool
    restored_from_version: int | None


class DiffRequest(BaseModel):
    version_a: int
    version_b: int


class DiffOperationResponse(BaseModel):
    operation: str
    line_number: int
    content: str
    old_content: str | None = None


class DiffResponse(BaseModel):
    operations: list[DiffOperationResponse]
    summary: dict  # {lines_added, lines_deleted, lines_modified}


class EmbeddingStatusResponse(BaseModel):
    pending: int
    embedding: int
    embedded: int
    failed: int
    stale: int


class ActivityEventResponse(BaseModel):
    id: int
    timestamp: str
    event_type: str
    file_name: str | None
    actor: str
    details: dict | None


class RestoreRequest(BaseModel):
    confirmed: bool = False  # Must be True to execute


class WSMessage(BaseModel):
    event_type: str
    payload: dict
    timestamp: str
    event_id: int
