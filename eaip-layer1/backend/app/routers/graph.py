"""Graph router endpoints for knowledge graph data and relationship management."""

import math
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.file import File
from app.models.relationship import Relationship
from app.schemas.graph import (
    GraphDataResponse,
    GraphEdgeResponse,
    GraphNodeData,
    GraphNodePosition,
    GraphNodeResponse,
)
from app.schemas.relationship import (
    RelationshipCreateRequest,
    RelationshipResponse,
    RelationshipUpdateRequest,
)
from app.services.relationship_engine import RelationshipEngine

router = APIRouter(prefix="/graph", tags=["graph"])


def _compute_radial_layout(files: list[File]) -> dict[int, GraphNodePosition]:
    if not files:
        return {}

    departments: dict[str, list[File]] = defaultdict(list)
    for file in files:
        departments[file.department].append(file)

    dept_names = sorted(departments.keys())
    num_departments = len(dept_names)

    if num_departments == 0:
        return {}

    center_x = 400.0
    center_y = 400.0
    base_radius = 200.0
    node_spacing = 80.0

    positions: dict[int, GraphNodePosition] = {}
    sector_angle = 2 * math.pi / num_departments

    for dept_index, dept_name in enumerate(dept_names):
        dept_files = departments[dept_name]
        num_files = len(dept_files)
        dept_angle = dept_index * sector_angle

        if num_files == 1:
            x = center_x + base_radius * math.cos(dept_angle)
            y = center_y + base_radius * math.sin(dept_angle)
            positions[dept_files[0].id] = GraphNodePosition(x=round(x, 1), y=round(y, 1))
        else:
            arc_spread = sector_angle * 0.7
            arc_start = dept_angle - arc_spread / 2
            max_per_ring = 5
            rings = math.ceil(num_files / max_per_ring)

            for file_index, file_obj in enumerate(dept_files):
                ring = file_index // max_per_ring
                pos_in_ring = file_index % max_per_ring
                files_in_this_ring = min(max_per_ring, num_files - ring * max_per_ring)
                radius = base_radius + ring * node_spacing

                if files_in_this_ring == 1:
                    angle = dept_angle
                else:
                    angle = arc_start + (pos_in_ring / (files_in_this_ring - 1)) * arc_spread

                x = center_x + radius * math.cos(angle)
                y = center_y + radius * math.sin(angle)
                positions[file_obj.id] = GraphNodePosition(x=round(x, 1), y=round(y, 1))

    return positions


@router.get("", response_model=GraphDataResponse)
def get_graph_data(db: Session = Depends(get_db)):
    files = db.query(File).all()
    relationships = db.query(Relationship).all()

    positions = _compute_radial_layout(files)

    nodes = []
    for file_obj in files:
        position = positions.get(file_obj.id, GraphNodePosition(x=0.0, y=0.0))
        node = GraphNodeResponse(
            id=str(file_obj.id),
            data=GraphNodeData(
                label=file_obj.name,
                department=file_obj.department,
                fileId=file_obj.id,
            ),
            position=position,
        )
        nodes.append(node)

    edges = []
    for rel in relationships:
        edge = GraphEdgeResponse(
            id=str(rel.id),
            source=str(rel.source_file_id),
            target=str(rel.target_file_id),
            label=rel.relationship_type,
        )
        edges.append(edge)

    return GraphDataResponse(nodes=nodes, edges=edges)


@router.post("/relationships", response_model=RelationshipResponse, status_code=201)
def create_relationship(
    body: RelationshipCreateRequest,
    db: Session = Depends(get_db),
):
    source = db.query(File).filter(File.id == body.source_file_id).first()
    if source is None:
        raise HTTPException(status_code=404, detail="Source file not found")

    target = db.query(File).filter(File.id == body.target_file_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Target file not found")

    engine = RelationshipEngine(db)
    relationship = engine.create_manual_relationship(
        body.source_file_id, body.target_file_id, body.relationship_type
    )
    return relationship


@router.put("/relationships/{relationship_id}", response_model=RelationshipResponse)
def update_relationship(
    relationship_id: int,
    body: RelationshipUpdateRequest,
    db: Session = Depends(get_db),
):
    relationship = (
        db.query(Relationship)
        .filter(Relationship.id == relationship_id)
        .first()
    )
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")

    relationship.relationship_type = body.relationship_type
    db.commit()
    db.refresh(relationship)
    return relationship


@router.delete("/relationships/{relationship_id}", status_code=204)
def delete_relationship(
    relationship_id: int,
    db: Session = Depends(get_db),
):
    engine = RelationshipEngine(db)
    deleted = engine.delete_relationship(relationship_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")
