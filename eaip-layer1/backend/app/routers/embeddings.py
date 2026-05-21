"""Embedding router endpoints for triggering embedding jobs and checking status."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import graphrag_settings, settings
from app.database import get_db
from app.models.embedding_log import EmbeddingLog
from app.models.file import File
from app.schemas.embedding import EmbeddingJobResponse, EmbeddingStatusResponse
from app.services.embedding_engine import EmbeddingEngine

router = APIRouter(prefix="/embeddings", tags=["embeddings"])


@router.post("/run", response_model=EmbeddingJobResponse)
def run_incremental_embedding(db: Session = Depends(get_db)):
    """Trigger an incremental embedding job.

    Processes files with changed content_hash or no prior embedding.
    Returns a summary of files processed, chunks generated, and errors.
    """
    engine = EmbeddingEngine(db, graphrag_settings, settings.knowledge_base_path)
    result = engine.run_incremental()
    return EmbeddingJobResponse(
        job_id=result.job_id,
        files_processed=result.files_processed,
        chunks_generated=result.chunks_generated,
        errors=result.errors,
        status=result.status,
    )


@router.post("/run/full", response_model=EmbeddingJobResponse)
def run_full_embedding(db: Session = Depends(get_db)):
    """Trigger a full re-embedding of all indexed files.

    Processes every file in the index regardless of content_hash.
    Returns a summary of files processed, chunks generated, and errors.
    """
    engine = EmbeddingEngine(db, graphrag_settings, settings.knowledge_base_path)
    result = engine.run_full()
    return EmbeddingJobResponse(
        job_id=result.job_id,
        files_processed=result.files_processed,
        chunks_generated=result.chunks_generated,
        errors=result.errors,
        status=result.status,
    )


@router.post("/run/{file_id}", response_model=EmbeddingJobResponse)
def run_single_file_embedding(file_id: int, db: Session = Depends(get_db)):
    """Trigger embedding for a single file by its database ID.

    Args:
        file_id: The primary key of the file to embed.

    Returns:
        EmbeddingJobResponse with processing results.

    Raises:
        HTTPException: 404 if the file is not found.
    """
    file_exists = db.query(File).filter(File.id == file_id).first()
    if file_exists is None:
        raise HTTPException(status_code=404, detail=f"File with id {file_id} not found")

    engine = EmbeddingEngine(db, graphrag_settings, settings.knowledge_base_path)
    result = engine.run_single(file_id)
    return EmbeddingJobResponse(
        job_id=result.job_id,
        files_processed=result.files_processed,
        chunks_generated=result.chunks_generated,
        errors=result.errors,
        status=result.status,
    )


@router.get("/status", response_model=EmbeddingStatusResponse)
def get_embedding_status(db: Session = Depends(get_db)):
    """Get the current embedding status of the knowledge base.

    Returns total embedded files, pending files, and last job timestamp.
    """
    total_embedded = (
        db.query(func.count(File.id))
        .filter(File.embedding_status == "embedded")
        .scalar()
        or 0
    )
    files_pending = (
        db.query(func.count(File.id))
        .filter(
            (File.embedding_status == None) | (File.embedding_status == "pending")  # noqa: E711
        )
        .scalar()
        or 0
    )
    last_job = (
        db.query(EmbeddingLog.timestamp)
        .order_by(EmbeddingLog.timestamp.desc())
        .first()
    )
    last_job_timestamp = last_job[0] if last_job else None

    return EmbeddingStatusResponse(
        total_files_embedded=total_embedded,
        files_pending=files_pending,
        last_job_timestamp=last_job_timestamp,
    )
