"""Sync router endpoints for triggering sync, checking status, and viewing logs."""

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.file import File
from app.models.sync_log import SyncLog
from app.schemas.sync import IndexStatusResponse, SyncLogEntry, SyncResultResponse
from app.services.sync_engine import SyncEngine

router = APIRouter(prefix="/sync", tags=["sync"])

_auto_sync_enabled: bool = True


@router.post("", response_model=SyncResultResponse)
def trigger_sync(db: Session = Depends(get_db)):
    sync_engine = SyncEngine(db, settings.knowledge_base_path)
    result = sync_engine.execute_sync()
    return SyncResultResponse(
        files_added=result.files_added,
        files_updated=result.files_updated,
        files_removed=result.files_removed,
        status=result.status,
        timestamp=result.timestamp,
    )


@router.post("/{file_id}", response_model=SyncResultResponse)
def trigger_sync_single(file_id: int, db: Session = Depends(get_db)):
    sync_engine = SyncEngine(db, settings.knowledge_base_path)
    result = sync_engine.execute_sync()
    return SyncResultResponse(
        files_added=result.files_added,
        files_updated=result.files_updated,
        files_removed=result.files_removed,
        status=result.status,
        timestamp=result.timestamp,
    )


@router.get("/status", response_model=IndexStatusResponse)
def get_index_status(db: Session = Depends(get_db)):
    total_files = db.query(func.count(File.id)).scalar() or 0
    last_sync = (
        db.query(SyncLog.timestamp)
        .order_by(SyncLog.timestamp.desc())
        .first()
    )
    last_sync_timestamp = last_sync[0] if last_sync else None

    pending_count = (
        db.query(func.count(File.id))
        .filter(File.sync_status.in_(["pending", "modified"]))
        .scalar()
        or 0
    )

    return IndexStatusResponse(
        total_files=total_files,
        last_sync_timestamp=last_sync_timestamp,
        pending_count=pending_count,
    )


@router.post("/toggle")
def toggle_auto_sync():
    global _auto_sync_enabled
    _auto_sync_enabled = not _auto_sync_enabled
    return {"auto_sync": _auto_sync_enabled}


@router.get("/logs", response_model=list[SyncLogEntry])
def get_sync_logs(db: Session = Depends(get_db)):
    logs = db.query(SyncLog).order_by(SyncLog.timestamp.desc()).all()
    return logs
