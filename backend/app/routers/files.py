"""File router endpoints for CRUD operations on indexed files."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, Form, Query
from fastapi import File as FastAPIFile
from fastapi.responses import FileResponse as StarletteFileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.file import File as FileModel
from app.schemas.file import FileResponse, FileUpdateRequest, TagUpdateRequest
from app.services.file_service import (
    delete_file,
    get_file,
    get_file_content,
    list_files,
    remove_from_index,
    update_tags,
    upload_file,
)
from app.services.ai_suggestion_service import suggest_rename, suggest_tags

router = APIRouter(prefix="/files", tags=["files"])


@router.get("", response_model=list[FileResponse])
def get_files(
    db: Session = Depends(get_db),
    department: str | None = Query(None),
    subfolder: str | None = Query(None),
    file_type: str | None = Query(None),
    sync_status: str | None = Query(None),
):
    return list_files(
        db,
        department=department,
        subfolder=subfolder,
        file_type=file_type,
        sync_status=sync_status,
    )


@router.post("/upload", response_model=FileResponse, status_code=201)
def upload_file_endpoint(
    file: UploadFile = FastAPIFile(...),
    department: str = Form(...),
    subfolder: str = Form(...),
    db: Session = Depends(get_db),
):
    return upload_file(db, file, department, subfolder)


@router.get("/{file_id}", response_model=FileResponse)
def get_file_by_id(file_id: int, db: Session = Depends(get_db)):
    return get_file(db, file_id)


@router.patch("/{file_id}", response_model=FileResponse)
def update_file(file_id: int, body: FileUpdateRequest, db: Session = Depends(get_db)):
    """Update a file's metadata (e.g., rename)."""
    file_obj = db.query(FileModel).filter(
        FileModel.id == file_id, FileModel.is_deleted == False
    ).first()
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")
    if body.name is not None:
        file_obj.name = body.name
    db.commit()
    db.refresh(file_obj)
    return file_obj


@router.get("/{file_id}/content")
def get_file_content_by_id(file_id: int, db: Session = Depends(get_db)):
    file_path = get_file_content(db, file_id)
    return StarletteFileResponse(path=str(file_path), filename=file_path.name)


@router.patch("/{file_id}/tags", response_model=FileResponse)
def update_file_tags(
    file_id: int,
    body: TagUpdateRequest,
    db: Session = Depends(get_db),
):
    return update_tags(db, file_id, body.tags)


@router.post("/{file_id}/suggest-tags", response_model=list[str])
def suggest_file_tags(file_id: int, db: Session = Depends(get_db)):
    """Suggest up to 5 AI-generated tags for a file based on its content."""
    # Verify the file exists before calling the suggestion service
    file_obj = db.query(FileModel).filter(
        FileModel.id == file_id, FileModel.is_deleted == False
    ).first()
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")

    tags = suggest_tags(file_id, db)
    return tags


@router.post("/{file_id}/suggest-rename", response_model=list[str])
def suggest_file_rename(file_id: int, db: Session = Depends(get_db)):
    """Suggest up to 3 AI-generated file names following [department]_[topic]_[date].[ext] pattern."""
    file_obj = db.query(FileModel).filter(
        FileModel.id == file_id, FileModel.is_deleted == False
    ).first()
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File not found")

    suggestions = suggest_rename(file_id, db)
    return suggestions


@router.delete("/{file_id}", status_code=204)
def delete_file_by_id(file_id: int, db: Session = Depends(get_db)):
    delete_file(db, file_id)


@router.delete("/{file_id}/index", status_code=204)
def remove_file_from_index(file_id: int, db: Session = Depends(get_db)):
    remove_from_index(db, file_id)


@router.post("/{file_id}/reveal", status_code=200)
def reveal_file_in_explorer(file_id: int, db: Session = Depends(get_db)):
    """Open Windows Explorer and select/reveal the file."""
    import subprocess
    import os
    from pathlib import Path
    from fastapi import HTTPException

    file_obj = get_file(db, file_id)
    if not file_obj:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = Path(file_obj.path)
    if not file_path.exists():
        # Try relative to knowledge_base_path
        from app.config import settings
        file_path = Path(settings.knowledge_base_path) / file_obj.path
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File path not found on disk")

    abs_path = str(file_path.resolve())

    try:
        if os.name == "nt":
            # Windows: open explorer and select the file
            subprocess.Popen(["explorer", "/select,", abs_path])
        else:
            # Linux/Mac: open the containing folder
            folder = str(file_path.parent.resolve())
            subprocess.Popen(["xdg-open", folder])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open explorer: {e}")

    return {"status": "ok", "path": abs_path}
