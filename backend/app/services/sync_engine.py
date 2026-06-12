"""Sync engine service for reconciling filesystem state with the database index."""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import hashlib

from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.file import File
from app.models.sync_log import SyncLog
from app.utils.department_config import auto_detect_tags, get_subfolder_sensitivity


@dataclass
class SyncResult:
    files_added: int
    files_updated: int
    files_removed: int
    status: str
    timestamp: datetime


class SyncEngine:
    def __init__(self, db_session: Session, kb_path: str):
        self.db = db_session
        self.kb_path = Path(kb_path)

    def execute_sync(self) -> SyncResult:
        timestamp = datetime.now(timezone.utc)

        try:
            fs_files = self._scan_filesystem()
            db_files = self._get_indexed_files()

            fs_paths = set(fs_files.keys())
            db_paths = set(db_files.keys())

            new_paths = fs_paths - db_paths
            deleted_paths = db_paths - fs_paths
            common_paths = fs_paths & db_paths

            modified_paths = {
                path for path in common_paths
                if fs_files[path]["content_hash"] != db_files[path].content_hash
            }

            added = self._add_new_files(fs_files, new_paths)
            updated = self._update_modified_files(fs_files, db_files, modified_paths)
            removed = self._remove_deleted_files(db_files, deleted_paths)

            self.db.commit()

            result = SyncResult(
                files_added=added,
                files_updated=updated,
                files_removed=removed,
                status="success",
                timestamp=timestamp,
            )
        except Exception as e:
            self.db.rollback()
            result = SyncResult(
                files_added=0,
                files_updated=0,
                files_removed=0,
                status="error",
                timestamp=timestamp,
            )
            self._log_sync(result, summary=str(e))
            raise

        self._log_sync(result)
        return result

    def _scan_filesystem(self) -> dict[str, dict]:
        files: dict[str, dict] = {}

        if not self.kb_path.exists():
            return files

        for file_path in self.kb_path.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(self.kb_path)).replace("\\", "/")
                stat = file_path.stat()
                parts = rel_path.split("/")
                dept = parts[0] if len(parts) >= 1 else ""
                sub = parts[1] if len(parts) >= 2 else ""
                file_ext = file_path.suffix.lower()

                files[rel_path] = {
                    "name": file_path.name,
                    "path": rel_path,
                    "department": dept,
                    "subfolder": sub,
                    "file_type": file_ext,
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime),
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "content_hash": self._compute_hash(file_path),
                }
        return files

    def _get_indexed_files(self) -> dict[str, File]:
        files = self.db.query(File).all()
        return {f.path: f for f in files}

    def _add_new_files(
        self, fs_files: dict[str, dict], new_paths: set[str]
    ) -> int:
        now = datetime.now(timezone.utc)
        for path in new_paths:
            meta = fs_files[path]
            checksum = meta["content_hash"]
            file_record = File(
                name=meta["name"],
                path=meta["path"],
                department=meta["department"],
                subfolder=meta.get("subfolder", ""),
                file_type=meta.get("file_type", ""),
                size=meta["size"],
                tags=auto_detect_tags(meta["name"]),
                created_at=meta["created_at"],
                modified_at=meta["modified_at"],
                indexed_at=now,
                content_hash=checksum,
                checksum_md5=checksum,
                sync_status="synced",
                sensitivity_level=get_subfolder_sensitivity(meta.get("subfolder", "")),
                is_deleted=False,
                embedding_status="pending",
            )
            self.db.add(file_record)
        return len(new_paths)

    def _update_modified_files(
        self,
        fs_files: dict[str, dict],
        db_files: dict[str, File],
        modified_paths: set[str],
    ) -> int:
        for path in modified_paths:
            meta = fs_files[path]
            db_file = db_files[path]
            db_file.size = meta["size"]
            db_file.content_hash = meta["content_hash"]
            db_file.checksum_md5 = meta["content_hash"]
            db_file.modified_at = meta["modified_at"]
            db_file.sync_status = "modified"
            db_file.embedding_status = "pending"
        return len(modified_paths)

    def _remove_deleted_files(
        self, db_files: dict[str, File], deleted_paths: set[str]
    ) -> int:
        for path in deleted_paths:
            db_file = db_files[path]

            try:
                self._cleanup_file_data(db_file.id)
            except Exception:
                db_file.embedding_status = "removal_failed"
                self.db.flush()
                continue

            db_file.is_deleted = True
            db_file.sync_status = "deleted"
        return len(deleted_paths)

    def _cleanup_file_data(self, file_id: int) -> None:
        """Remove chunks associated with a deleted file."""
        self.db.query(Chunk).filter(Chunk.file_id == file_id).delete(
            synchronize_session="fetch"
        )

    def _log_sync(self, result: SyncResult, summary: str | None = None) -> None:
        if summary is None:
            summary = (
                f"Added {result.files_added}, "
                f"updated {result.files_updated}, "
                f"removed {result.files_removed}"
            )

        log_entry = SyncLog(
            timestamp=result.timestamp,
            files_added=result.files_added,
            files_updated=result.files_updated,
            files_removed=result.files_removed,
            status=result.status,
            summary=summary,
        )
        self.db.add(log_entry)
        self.db.commit()

    def _extract_department(self, rel_path: str) -> str:
        return rel_path.split("/")[0]

    def _compute_hash(self, file_path: Path) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
