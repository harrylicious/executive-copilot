"""Department router endpoint for listing departments with folder hierarchy."""

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
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


class CreateFolderRequest(BaseModel):
    department: str
    name: str


@router.post("/folders", status_code=201)
def create_folder(body: CreateFolderRequest):
    if body.department not in DEPARTMENTS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid department '{body.department}'. Valid: {', '.join(DEPARTMENTS.keys())}",
        )

    if body.name in DEPARTMENTS[body.department]:
        raise HTTPException(
            status_code=409,
            detail=f"Folder '{body.name}' already exists in department '{body.department}'",
        )

    folder_path = Path(settings.knowledge_base_path) / body.department / body.name
    folder_path.mkdir(parents=True, exist_ok=True)

    DEPARTMENTS[body.department].append(body.name)
    DEPARTMENTS[body.department].sort()

    return {"department": body.department, "name": body.name, "path": str(folder_path)}


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

    # ─── Master Data section ──────────────────────────────────────────────────
    master_files = [
        f for f in files
        if f.department == "master" and not f.path.replace("\\", "/").startswith("staging")
    ]
    if master_files:
        # Group by subfolder — files directly in master/ have filename as subfolder
        master_subfolders: dict[str, list[File]] = {}
        for f in master_files:
            # Determine actual subfolder from path
            parts = f.path.replace("\\", "/").split("/")
            if len(parts) >= 3:
                # e.g. master/data/file.xlsx → subfolder = "data"
                sub = parts[1]
            else:
                # e.g. master/file.xlsx → no real subfolder
                sub = "general"
            if sub not in master_subfolders:
                master_subfolders[sub] = []
            master_subfolders[sub].append(f)

        master_children: list[TreeNode] = []
        for subfolder_name in sorted(master_subfolders.keys()):
            sub_files = master_subfolders[subfolder_name]
            file_nodes = [
                TreeNode(
                    id=f"file-{f.id}",
                    name=f.name,
                    type="file",
                    fileId=f.id,
                )
                for f in sub_files
            ]
            folder_node = TreeNode(
                id=f"folder-master-{subfolder_name}",
                name=subfolder_name.replace("_", " ").title(),
                type="folder",
                children=file_nodes,
                sensitivity="Internal",
            )
            master_children.append(folder_node)

        master_node = TreeNode(
            id="dept-master",
            name="Master Data",
            type="department",
            children=master_children,
            color="blue",
            description="Data master: barang, outlet, distributor",
            outputs=["barang", "outlet", "distributor"],
        )
        tree.append(master_node)

    # ─── Department sections ──────────────────────────────────────────────────
    for dept_id, subfolders in DEPARTMENTS.items():
        meta = DEPARTMENT_META.get(dept_id, {})
        folder_children: list[TreeNode] = []
        for subfolder in subfolders:
            # Look up files stored as "<dept_id>/<subfolder>/..." or "departments/<dept_id>/<subfolder>/..."
            dept_subfolder_files = file_lookup.get((dept_id, subfolder), [])

            # Also check nested "departments/<dept_id>/<subfolder>" structure
            nested_files = [
                f for f in files
                if f.path.replace("\\", "/").startswith(f"departments/{dept_id}/{subfolder}/")
            ]
            seen_ids = {f.id for f in dept_subfolder_files}
            for f in nested_files:
                if f.id not in seen_ids:
                    dept_subfolder_files.append(f)

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
