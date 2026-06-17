"""Monitoring router endpoints for file status, version management, and real-time updates."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.file import File
from app.schemas.monitoring import (
    ActivityEventResponse,
    DiffRequest,
    DiffResponse,
    DiffOperationResponse,
    EmbeddingStatusResponse,
    FileStatusResponse,
    FileVersionResponse,
    RestoreRequest,
)
from app.services.audit_logger import AuditLogger
from app.services.diff_engine import DiffEngine
from app.services.text_extractor import TextExtractor
from app.services.version_restore import (
    FileDeletedError,
    FileNotFoundRestoreError,
    VersionNotFoundError,
    VersionRestoreError,
    VersionRestoreService,
)
from app.services.version_store import VersionStoreService
from app.services.embedding_queue import EmbeddingQueueService
from app.services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/monitoring", tags=["monitoring"])

# Singleton WebSocketManager instance shared across the module
_ws_manager = WebSocketManager()


def get_ws_manager() -> WebSocketManager:
    """Return the shared WebSocketManager instance."""
    return _ws_manager


@router.get("/files", response_model=list[FileStatusResponse])
def get_files(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Paginated file list with embedding status, version, and file size.

    Returns non-deleted files sorted by modified_at descending.
    """
    offset = (page - 1) * page_size
    files = (
        db.query(File)
        .filter(File.is_deleted == False)  # noqa: E712
        .order_by(File.modified_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return [
        FileStatusResponse(
            id=f.id,
            name=f.name,
            path=f.path,
            department=f.department,
            embedding_status=f.embedding_status,
            current_version=f.current_version,
            modified_at=f.modified_at,
            file_size=f.size,
        )
        for f in files
    ]


@router.get("/files/{file_id}/versions", response_model=list[FileVersionResponse])
def get_file_versions(
    file_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Paginated version history for a file, ordered by version_number descending."""
    from app.config import settings

    # Verify file exists
    file_record = db.query(File).filter(File.id == file_id).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found.")

    archive_dir = f"{settings.knowledge_base_path}/.versions"
    version_store = VersionStoreService(db=db, archive_dir=archive_dir)
    versions = version_store.get_versions(file_id, page=page, page_size=page_size)

    return [
        FileVersionResponse(
            version_number=v.version_number,
            content_hash=v.content_hash,
            file_size=v.file_size,
            timestamp=v.timestamp,
            is_restore=v.is_restore,
            restored_from_version=v.restored_from_version,
        )
        for v in versions
    ]


@router.post("/files/{file_id}/versions/diff", response_model=DiffResponse)
def compute_diff(
    file_id: int,
    body: DiffRequest,
    db: Session = Depends(get_db),
):
    """Compute line-level diff between two versions of a file."""
    from app.config import settings

    # Verify file exists
    file_record = db.query(File).filter(File.id == file_id).first()
    if file_record is None:
        raise HTTPException(status_code=404, detail=f"File {file_id} not found.")

    archive_dir = f"{settings.knowledge_base_path}/.versions"
    version_store = VersionStoreService(db=db, archive_dir=archive_dir)
    text_extractor = TextExtractor()
    diff_engine = DiffEngine(text_extractor=text_extractor, version_store=version_store)

    try:
        result = diff_engine.compute_diff(file_id, body.version_a, body.version_b)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    operations = [
        DiffOperationResponse(
            operation=op.operation,
            line_number=op.line_number,
            content=op.content,
            old_content=op.old_content,
        )
        for op in result.operations
    ]
    summary = {
        "lines_added": result.summary.lines_added,
        "lines_deleted": result.summary.lines_deleted,
        "lines_modified": result.summary.lines_modified,
    }
    return DiffResponse(operations=operations, summary=summary)


@router.post(
    "/files/{file_id}/versions/{version}/restore",
    response_model=FileVersionResponse,
)
async def restore_version(
    file_id: int,
    version: int,
    body: RestoreRequest,
    db: Session = Depends(get_db),
):
    """Restore a file to a specific historical version.

    Requires confirmed=True in the request body to proceed.
    """
    if not body.confirmed:
        raise HTTPException(
            status_code=400,
            detail="Restore not confirmed. Set confirmed=True to proceed.",
        )

    from app.config import settings

    archive_dir = f"{settings.knowledge_base_path}/.versions"
    kb_path = settings.knowledge_base_path

    version_store = VersionStoreService(db=db, archive_dir=archive_dir)
    embedding_queue = EmbeddingQueueService()
    audit_logger = AuditLogger(db=db)

    restore_service = VersionRestoreService(
        db=db,
        version_store=version_store,
        embedding_queue=embedding_queue,
        audit_logger=audit_logger,
        kb_path=kb_path,
    )

    try:
        result = await restore_service.restore_version(
            file_id=file_id,
            version_number=version,
            actor="user",
        )
    except FileNotFoundRestoreError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except FileDeletedError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except VersionNotFoundError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    except VersionRestoreError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return FileVersionResponse(
        version_number=result.version_number,
        content_hash=result.content_hash,
        file_size=result.file_size,
        timestamp=result.timestamp,
        is_restore=result.is_restore,
        restored_from_version=result.restored_from_version,
    )


@router.get("/embedding-status", response_model=EmbeddingStatusResponse)
def get_embedding_status(db: Session = Depends(get_db)):
    """Current embedding status counts across all non-deleted files."""
    results = (
        db.query(File.embedding_status, func.count(File.id))
        .filter(File.is_deleted == False)  # noqa: E712
        .group_by(File.embedding_status)
        .all()
    )

    counts = {
        "pending": 0,
        "embedding": 0,
        "embedded": 0,
        "failed": 0,
        "stale": 0,
    }
    for status, count in results:
        if status in counts:
            counts[status] = count

    return EmbeddingStatusResponse(**counts)


@router.get("/activity", response_model=list[ActivityEventResponse])
def get_activity(db: Session = Depends(get_db)):
    """Last 50 activity events ordered by timestamp descending."""
    audit_logger = AuditLogger(db=db)
    records = audit_logger.get_recent_events(limit=50)

    events = []
    for record in records:
        # Resolve file name from file_id if available
        file_name = None
        if record.file_id is not None:
            file_record = db.query(File).filter(File.id == record.file_id).first()
            if file_record:
                file_name = file_record.name

        events.append(
            ActivityEventResponse(
                id=record.id,
                timestamp=record.timestamp,
                event_type=record.event_type,
                file_name=file_name,
                actor=record.actor,
                details=record.details,
            )
        )

    return events


@router.websocket("/ws/embedding-status")
async def websocket_embedding_status(websocket: WebSocket):
    """WebSocket endpoint for real-time embedding status updates.

    Supports reconnection replay via last_event_id sent in client messages.
    The full path will be /api/monitoring/ws/embedding-status when mounted.
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            # Handle reconnection: client sends last_event_id for replay
            if "last_event_id" in data:
                last_event_id = int(data["last_event_id"])
                await ws_manager.send_missed_events(websocket, last_event_id)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# Also expose a top-level WebSocket route at /ws/embedding-status
# This can be registered directly on the app by the caller if needed.
ws_router = APIRouter()


@ws_router.websocket("/ws/embedding-status")
async def websocket_embedding_status_root(websocket: WebSocket):
    """WebSocket endpoint at /ws/embedding-status (root-level).

    Same functionality as the monitoring-prefixed endpoint.
    Supports reconnection replay via last_event_id sent in client messages.
    """
    ws_manager = get_ws_manager()
    await ws_manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            # Handle reconnection: client sends last_event_id for replay
            if "last_event_id" in data:
                last_event_id = int(data["last_event_id"])
                await ws_manager.send_missed_events(websocket, last_event_id)
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)
