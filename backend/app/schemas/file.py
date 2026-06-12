"""Pydantic schemas for file-related API requests and responses."""

from datetime import datetime

from pydantic import BaseModel


class FileResponse(BaseModel):
    id: int
    name: str
    path: str
    department: str
    subfolder: str | None = None
    file_type: str | None = None
    size: int
    tags: list[str] = []
    created_at: datetime
    modified_at: datetime
    indexed_at: datetime | None = None
    sync_status: str | None = "synced"
    sensitivity_level: str | None = "Internal"
    is_deleted: bool = False

    class Config:
        from_attributes = True


class TagUpdateRequest(BaseModel):
    tags: list[str]


class FileUpdateRequest(BaseModel):
    name: str | None = None
