"""Department router endpoint for listing departments with folder hierarchy."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.file import File
from app.utils.department_config import DEPARTMENTS, DEPARTMENT_META, SENSITIVITY_MATRIX

router = APIRouter(prefix="/departments", tags=["departments"])


class TreeNode(BaseModel):
    id: str
    name: str
    type: str
    children: list["TreeNode"] | None = None
    fileId: int | None = None
    color: str | None = None
    description: str | None = None
    outputs: list[str] | None = None
    sensitivity: str | None = None


@router.get("", response_model=list[TreeNode])
def get_departments(db: Session = Depends(get_db)):
    files = db.query(File).all()

    file_lookup: dict[tuple[str, str], list[File]] = {}
    for file in files:
        parts = file.path.replace("\\", "/").split("/")
        if len(parts) >= 2:
            dept = parts[0]
            subfolder = parts[1]
            key = (dept, subfolder)
            if key not in file_lookup:
                file_lookup[key] = []
            file_lookup[key].append(file)

    tree: list[TreeNode] = []
    for dept_id, subfolders in DEPARTMENTS.items():
        meta = DEPARTMENT_META.get(dept_id, {})
        folder_children: list[TreeNode] = []
        for subfolder in subfolders:
            dept_subfolder_files = file_lookup.get((dept_id, subfolder), [])
            file_nodes = [
                TreeNode(
                    id=f"file-{f.id}",
                    name=f.name,
                    type="file",
                    fileId=f.id,
                )
                for f in dept_subfolder_files
            ]

            sensitivity = ""
            for level, folders in SENSITIVITY_MATRIX.items():
                if subfolder in folders:
                    sensitivity = level
                    break

            folder_node = TreeNode(
                id=f"folder-{dept_id}-{subfolder}",
                name=subfolder.replace("_", " ").title(),
                type="folder",
                children=file_nodes if file_nodes else [],
                sensitivity=sensitivity,
            )
            folder_children.append(folder_node)

        dept_node = TreeNode(
            id=f"dept-{dept_id}",
            name=meta.get("name", dept_id),
            type="department",
            children=folder_children,
            color=meta.get("color"),
            description=meta.get("description"),
            outputs=meta.get("outputs"),
        )
        tree.append(dept_node)

    return tree
