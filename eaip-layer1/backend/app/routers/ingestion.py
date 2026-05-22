"""Ingestion pipeline router for file upload and job management endpoints."""

import logging
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.config import ingestion_settings
from app.database import SessionLocal, get_db
from app.models.batch_execution_log import BatchExecutionLog
from app.models.batch_loader_config import BatchLoaderConfig
from app.models.ingestion_job import IngestionJob
from app.models.ingestion_stage_log import IngestionStageLog
from app.schemas.batch_loader import (
    BatchExecutionLogResponse,
    BatchLoaderConfigCreate,
    BatchLoaderConfigResponse,
    BatchLoaderConfigUpdate,
)
from app.schemas.ingestion import (
    BatchUploadResponse,
    ErrorResponse,
    IngestionJobResponse,
    JobListResponse,
    StageLogResponse,
    UploadResponse,
)
from app.services.ingestion.scheduler import BatchScheduler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

MAX_FILE_SIZE_BYTES = ingestion_settings.max_file_size_mb * 1024 * 1024


def _run_pipeline_background(job_id: str) -> None:
    """Run the ingestion pipeline in a background task with its own DB session.

    Args:
        job_id: The UUID of the IngestionJob to process.
    """
    from app.services.ingestion.orchestrator import IngestionOrchestrator

    db = SessionLocal()
    try:
        orchestrator = IngestionOrchestrator(db)
        orchestrator.run_pipeline(job_id)
    except Exception as e:
        logger.exception(f"Background pipeline failed for job {job_id}: {e}")
    finally:
        db.close()


def _store_file_in_staging(file: UploadFile, job_id: str) -> tuple[Path, int]:
    """Store an uploaded file in the staging area.

    Args:
        file: The uploaded file.
        job_id: The job ID used to create a unique staging subdirectory.

    Returns:
        Tuple of (staging file path, file size in bytes).

    Raises:
        HTTPException: If the file exceeds the maximum allowed size.
    """
    staging_dir = Path(ingestion_settings.staging_path) / job_id
    staging_dir.mkdir(parents=True, exist_ok=True)

    staging_path = staging_dir / (file.filename or "unnamed_file")

    # Write file to staging and track size
    file_size = 0
    with open(staging_path, "wb") as buffer:
        while chunk := file.file.read(8192):
            file_size += len(chunk)
            if file_size > MAX_FILE_SIZE_BYTES:
                # Clean up partial file
                buffer.close()
                shutil.rmtree(staging_dir, ignore_errors=True)
                raise HTTPException(
                    status_code=413,
                    detail={
                        "error_code": "FILE_TOO_LARGE",
                        "message": (
                            f"File exceeds maximum allowed size of "
                            f"{ingestion_settings.max_file_size_mb}MB"
                        ),
                        "details": {
                            "max_size_mb": ingestion_settings.max_file_size_mb,
                        },
                    },
                )
            buffer.write(chunk)

    return staging_path, file_size


def _create_ingestion_job(
    db: Session,
    file_name: str,
    file_size: int,
    department: str,
    subfolder: str | None,
    staging_path: Path,
) -> IngestionJob:
    """Create an IngestionJob record in the database.

    Args:
        db: Database session.
        file_name: Original file name.
        file_size: File size in bytes.
        department: Target department.
        subfolder: Optional target subfolder.
        staging_path: Path to the staged file.

    Returns:
        The created IngestionJob instance.
    """
    now = datetime.now(timezone.utc)
    job = IngestionJob(
        id=str(uuid.uuid4()),
        file_name=file_name,
        file_size=file_size,
        department=department,
        subfolder=subfolder,
        status="queued",
        staging_path=str(staging_path),
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=202,
    responses={413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    department: str = Form(default=None),
    subfolder: str | None = Form(default=None),
    tags: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    """Upload a single file for ingestion.

    Validates file size and required metadata, creates an IngestionJob,
    stores the file in the staging area, and dispatches the pipeline
    orchestrator as a background task.

    Returns 202 Accepted with the job ID on success.
    """
    # Validate required metadata
    if not department or not department.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "MISSING_METADATA",
                "message": "Required metadata field 'department' is missing or empty",
                "details": {"missing_fields": ["department"]},
            },
        )

    department = department.strip()
    subfolder = subfolder.strip() if subfolder else None

    # Generate job ID
    job_id = str(uuid.uuid4())

    # Store file in staging area (validates size during write)
    staging_path, file_size = _store_file_in_staging(file, job_id)

    # Create IngestionJob
    job = IngestionJob(
        id=job_id,
        file_name=file.filename or "unnamed_file",
        file_size=file_size,
        department=department,
        subfolder=subfolder,
        status="queued",
        staging_path=str(staging_path),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Dispatch pipeline in background
    background_tasks.add_task(_run_pipeline_background, job.id)

    return UploadResponse(
        job_id=job.id,
        file_name=job.file_name,
        status=job.status,
        created_at=job.created_at,
    )


@router.post(
    "/upload/batch",
    response_model=BatchUploadResponse,
    status_code=202,
    responses={413: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def upload_batch(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    department: str = Form(default=None),
    subfolder: str | None = Form(default=None),
    tags: list[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    """Upload multiple files for ingestion in a single request.

    Creates one IngestionJob per file. All files share the same
    department/subfolder metadata. Returns all job IDs.

    Returns 202 Accepted with all job details on success.
    """
    # Validate required metadata
    if not department or not department.strip():
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "MISSING_METADATA",
                "message": "Required metadata field 'department' is missing or empty",
                "details": {"missing_fields": ["department"]},
            },
        )

    department = department.strip()
    subfolder = subfolder.strip() if subfolder else None

    jobs: list[UploadResponse] = []

    for file in files:
        job_id = str(uuid.uuid4())

        # Store file in staging area (validates size during write)
        staging_path, file_size = _store_file_in_staging(file, job_id)

        # Create IngestionJob
        now = datetime.now(timezone.utc)
        job = IngestionJob(
            id=job_id,
            file_name=file.filename or "unnamed_file",
            file_size=file_size,
            department=department,
            subfolder=subfolder,
            status="queued",
            staging_path=str(staging_path),
            created_at=now,
            updated_at=now,
        )
        db.add(job)
        db.commit()
        db.refresh(job)

        # Dispatch pipeline in background for each file
        background_tasks.add_task(_run_pipeline_background, job.id)

        jobs.append(
            UploadResponse(
                job_id=job.id,
                file_name=job.file_name,
                status=job.status,
                created_at=job.created_at,
            )
        )

    return BatchUploadResponse(jobs=jobs, total=len(jobs))


@router.get("/jobs", response_model=JobListResponse)
def list_jobs(
    status: str | None = Query(default=None, description="Filter by job status"),
    department: str | None = Query(default=None, description="Filter by department"),
    date_from: datetime | None = Query(default=None, description="Filter jobs created after this date"),
    date_to: datetime | None = Query(default=None, description="Filter jobs created before this date"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
):
    """List ingestion jobs with optional filtering and pagination.

    Supports filtering by status, department, and date range.
    Returns paginated results with total count.
    """
    query = db.query(IngestionJob)

    # Apply filters
    if status:
        query = query.filter(IngestionJob.status == status)
    if department:
        query = query.filter(IngestionJob.department == department)
    if date_from:
        query = query.filter(IngestionJob.created_at >= date_from)
    if date_to:
        query = query.filter(IngestionJob.created_at <= date_to)

    # Get total count before pagination
    total = query.count()

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    jobs = (
        query.order_by(IngestionJob.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    # Build response with stage history for each job
    job_responses = []
    for job in jobs:
        stages = (
            db.query(IngestionStageLog)
            .filter(IngestionStageLog.job_id == job.id)
            .order_by(IngestionStageLog.started_at)
            .all()
        )
        job_responses.append(
            IngestionJobResponse(
                id=job.id,
                file_name=job.file_name,
                file_size=job.file_size,
                department=job.department,
                subfolder=job.subfolder,
                status=job.status,
                current_stage=job.current_stage,
                error_code=job.error_code,
                error_message=job.error_message,
                failure_stage=job.failure_stage,
                content_hash=job.content_hash,
                sensitivity_level=job.sensitivity_level,
                created_at=job.created_at,
                updated_at=job.updated_at,
                completed_at=job.completed_at,
                stages=[
                    StageLogResponse(
                        stage=s.stage,
                        status=s.status,
                        started_at=s.started_at,
                        completed_at=s.completed_at,
                        details=s.details,
                    )
                    for s in stages
                ],
            )
        )

    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=IngestionJobResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_job_detail(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Get full details of an ingestion job including stage history.

    Returns the job with all pipeline stage log entries.
    """
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "JOB_NOT_FOUND",
                "message": f"Ingestion job '{job_id}' not found",
            },
        )

    # Fetch stage history
    stages = (
        db.query(IngestionStageLog)
        .filter(IngestionStageLog.job_id == job.id)
        .order_by(IngestionStageLog.started_at)
        .all()
    )

    return IngestionJobResponse(
        id=job.id,
        file_name=job.file_name,
        file_size=job.file_size,
        department=job.department,
        subfolder=job.subfolder,
        status=job.status,
        current_stage=job.current_stage,
        error_code=job.error_code,
        error_message=job.error_message,
        failure_stage=job.failure_stage,
        content_hash=job.content_hash,
        sensitivity_level=job.sensitivity_level,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        stages=[
            StageLogResponse(
                stage=s.stage,
                status=s.status,
                started_at=s.started_at,
                completed_at=s.completed_at,
                details=s.details,
            )
            for s in stages
        ],
    )


# --- Batch Loader Configuration Endpoints ---

_batch_scheduler = BatchScheduler()


@router.post(
    "/batch-configs",
    response_model=BatchLoaderConfigResponse,
    status_code=201,
    responses={422: {"model": ErrorResponse}},
)
def create_batch_config(
    config_data: BatchLoaderConfigCreate,
    db: Session = Depends(get_db),
):
    """Create a new batch loader configuration.

    Validates the source path format using BatchScheduler.configure(),
    generates a UUID for the config ID, and persists the configuration.
    """
    # Validate source path format
    try:
        BatchScheduler.configure(config_data.source_path)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INVALID_SOURCE_PATH",
                "message": str(e),
                "details": {"source_path": config_data.source_path},
            },
        )

    now = datetime.now(timezone.utc)
    config = BatchLoaderConfig(
        id=str(uuid.uuid4()),
        name=config_data.name,
        source_path=config_data.source_path,
        source_type=config_data.source_type,
        cron_expression=config_data.cron_expression,
        department=config_data.department,
        subfolder=config_data.subfolder,
        is_active=config_data.is_active,
        created_at=now,
        updated_at=now,
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    # Compute next execution time from scheduler
    next_execution_at = _batch_scheduler.get_next_run(config.id)

    return BatchLoaderConfigResponse(
        id=config.id,
        name=config.name,
        source_path=config.source_path,
        source_type=config.source_type,
        cron_expression=config.cron_expression,
        department=config.department,
        subfolder=config.subfolder,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_execution_at=config.last_execution_at,
        last_execution_status=config.last_execution_status,
        next_execution_at=next_execution_at,
    )


@router.get(
    "/batch-configs",
    response_model=list[BatchLoaderConfigResponse],
)
def list_batch_configs(
    db: Session = Depends(get_db),
):
    """List all batch loader configurations.

    Returns all configurations regardless of active status.
    """
    configs = (
        db.query(BatchLoaderConfig)
        .order_by(BatchLoaderConfig.created_at.desc())
        .all()
    )

    results = []
    for config in configs:
        next_execution_at = _batch_scheduler.get_next_run(config.id)
        results.append(
            BatchLoaderConfigResponse(
                id=config.id,
                name=config.name,
                source_path=config.source_path,
                source_type=config.source_type,
                cron_expression=config.cron_expression,
                department=config.department,
                subfolder=config.subfolder,
                is_active=config.is_active,
                created_at=config.created_at,
                updated_at=config.updated_at,
                last_execution_at=config.last_execution_at,
                last_execution_status=config.last_execution_status,
                next_execution_at=next_execution_at,
            )
        )

    return results


@router.put(
    "/batch-configs/{config_id}",
    response_model=BatchLoaderConfigResponse,
    responses={404: {"model": ErrorResponse}, 422: {"model": ErrorResponse}},
)
def update_batch_config(
    config_id: str,
    update_data: BatchLoaderConfigUpdate,
    db: Session = Depends(get_db),
):
    """Update an existing batch loader configuration.

    Accepts partial update fields. Only provided (non-None) fields are updated.
    If source_path is updated, it is re-validated.
    """
    config = (
        db.query(BatchLoaderConfig)
        .filter(BatchLoaderConfig.id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "CONFIG_NOT_FOUND",
                "message": f"Batch loader config '{config_id}' not found",
            },
        )

    # If source_path is being updated, validate the new path
    update_fields = update_data.model_dump(exclude_unset=True)
    if "source_path" in update_fields and update_fields["source_path"] is not None:
        try:
            BatchScheduler.configure(update_fields["source_path"])
        except ValueError as e:
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "INVALID_SOURCE_PATH",
                    "message": str(e),
                    "details": {"source_path": update_fields["source_path"]},
                },
            )

    # Apply updates
    for field, value in update_fields.items():
        if value is not None:
            setattr(config, field, value)

    config.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)

    next_execution_at = _batch_scheduler.get_next_run(config.id)

    return BatchLoaderConfigResponse(
        id=config.id,
        name=config.name,
        source_path=config.source_path,
        source_type=config.source_type,
        cron_expression=config.cron_expression,
        department=config.department,
        subfolder=config.subfolder,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
        last_execution_at=config.last_execution_at,
        last_execution_status=config.last_execution_status,
        next_execution_at=next_execution_at,
    )


@router.delete(
    "/batch-configs/{config_id}",
    status_code=204,
    responses={404: {"model": ErrorResponse}},
)
def deactivate_batch_config(
    config_id: str,
    db: Session = Depends(get_db),
):
    """Soft-delete a batch loader configuration by setting is_active=False.

    Returns 204 No Content on success.
    """
    config = (
        db.query(BatchLoaderConfig)
        .filter(BatchLoaderConfig.id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "CONFIG_NOT_FOUND",
                "message": f"Batch loader config '{config_id}' not found",
            },
        )

    config.is_active = False
    config.updated_at = datetime.now(timezone.utc)
    db.commit()

    return Response(status_code=204)


@router.get(
    "/batch-configs/{config_id}/executions",
    response_model=list[BatchExecutionLogResponse],
    responses={404: {"model": ErrorResponse}},
)
def list_batch_config_executions(
    config_id: str,
    db: Session = Depends(get_db),
):
    """Get execution history for a batch loader configuration.

    Returns all execution log entries for the specified config,
    ordered by most recent first.
    """
    # Verify config exists
    config = (
        db.query(BatchLoaderConfig)
        .filter(BatchLoaderConfig.id == config_id)
        .first()
    )
    if not config:
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "CONFIG_NOT_FOUND",
                "message": f"Batch loader config '{config_id}' not found",
            },
        )

    executions = (
        db.query(BatchExecutionLog)
        .filter(BatchExecutionLog.config_id == config_id)
        .order_by(BatchExecutionLog.started_at.desc())
        .all()
    )

    return [
        BatchExecutionLogResponse(
            id=ex.id,
            config_id=ex.config_id,
            started_at=ex.started_at,
            completed_at=ex.completed_at,
            files_found=ex.files_found,
            files_submitted=ex.files_submitted,
            files_skipped=ex.files_skipped,
            errors=ex.errors,
            status=ex.status,
        )
        for ex in executions
    ]
