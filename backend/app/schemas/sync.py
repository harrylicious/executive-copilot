"""Pydantic schemas for sync-related API responses."""

from datetime import datetime

from pydantic import BaseModel


class SyncResultResponse(BaseModel):
    files_added: int
    files_updated: int
    files_removed: int
    status: str
    timestamp: datetime


class IndexStatusResponse(BaseModel):
    total_files: int
    last_sync_timestamp: datetime | None
    pending_count: int = 0


class SyncLogEntry(BaseModel):
    id: int
    timestamp: datetime
    files_added: int
    files_updated: int
    files_removed: int
    status: str
    summary: str | None

    class Config:
        from_attributes = True
