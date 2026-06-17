"""File service for CRUD operations on indexed file metadata."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.models.file import File
from app.utils.department_config import (
    DEPARTMENTS,
    auto_detect_tags,
    get_subfolder_sensitivity,
)


def list_files(
    db: Session,
    department: str | None = None,
    subfolder: str | None = None,
    file_type: str | None = None,
    sync_status: str | None = None,
) -> list[File]:
    query = db.query(File).filter(File.is_deleted == False)
    if department:
        query = query.filter(File.department == department)
    if subfolder:
        query = query.filter(File.subfolder == subfolder)
    if file_type:
        query = query.filter(File.file_type == file_type)
    if sync_status:
        query = query.filter(File.sync_status == sync_status)
    return query.all()


def get_file(db: Session, file_id: int) -> File:
    file = db.query(File).filter(File.id == file_id).first()
    if file is None:
        raise HTTPException(status_code=404, detail="File not found")
    return file


def get_file_content(db: Session, file_id: int) -> Path:
    file = get_file(db, file_id)
    file_path = Path(settings.knowledge_base_path) / file.path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File missing from disk")

    return file_path


def update_tags(db: Session, file_id: int, tags: list[str]) -> File:
    file = get_file(db, file_id)
    file.tags = tags
    db.commit()
    db.refresh(file)
    return file


def delete_file(db: Session, file_id: int) -> None:
    file = get_file(db, file_id)
    file.is_deleted = True
    file.sync_status = "deleted"
    db.commit()


def remove_from_index(db: Session, file_id: int) -> None:
    file = get_file(db, file_id)
    db.delete(file)
    db.commit()


def upload_file(
    db: Session,
    file: UploadFile,
    department: str,
    subfolder: str,
) -> File:
    if department not in DEPARTMENTS:
        valid = list(DEPARTMENTS.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Invalid department '{department}'. Valid: {', '.join(valid)}",
        )

    valid_subfolders = DEPARTMENTS[department]
    if subfolder not in valid_subfolders:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid subfolder '{subfolder}' for {department}. Valid: {', '.join(valid_subfolders)}",
        )

    rel_path = f"{department}/{subfolder}/{file.filename}"
    dest_dir = Path(settings.knowledge_base_path) / department / subfolder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / file.filename

    existing = db.query(File).filter(File.path == rel_path).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"File '{rel_path}' already exists in the index",
        )

    content = file.file.read()
    with open(dest_path, "wb") as f:
        f.write(content)

    now = datetime.now(timezone.utc)
    checksum_md5 = hashlib.md5(content).hexdigest()
    file_ext = Path(file.filename).suffix.lower()

    file_record = File(
        name=file.filename,
        path=rel_path,
        department=department,
        subfolder=subfolder,
        file_type=file_ext,
        size=len(content),
        tags=auto_detect_tags(file.filename),
        created_at=now,
        modified_at=now,
        indexed_at=now,
        content_hash=checksum_md5,
        checksum_md5=checksum_md5,
        sync_status="synced",
        sensitivity_level=get_subfolder_sensitivity(subfolder),
        is_deleted=False,
        embedding_status="pending",
    )
    db.add(file_record)
    db.commit()
    db.refresh(file_record)

    return file_record
