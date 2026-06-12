"""Knowledge graph router for graph visualization and relationship management."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.graph import (
    AutoReferenceResponse,
    CreateRelationshipRequest,
    GraphData,
    GraphEdge,
)
from app.services.graph_service import (
    auto_reference,
    create_relationship,
    delete_relationship,
    get_graph_data,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/", response_model=GraphData)
def get_graph(db: Session = Depends(get_db)):
    """Return the full knowledge graph with nodes and edges."""
    try:
        return get_graph_data(db)
    except Exception as e:
        logger.error("Failed to retrieve graph data: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Graph data could not be retrieved. Please try again later.",
        )


@router.post("/relationships", response_model=GraphEdge, status_code=201)
def create_graph_relationship(
    request: CreateRelationshipRequest, db: Session = Depends(get_db)
):
    """Create a new relationship between two files."""
    try:
        return create_relationship(
            source_id=request.source_id,
            target_id=request.target_id,
            relationship_type=request.relationship_type,
            db=db,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to create relationship: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Relationship could not be created. Please try again later.",
        )


@router.delete("/relationships/{relationship_id}", status_code=204)
def delete_graph_relationship(relationship_id: int, db: Session = Depends(get_db)):
    """Delete a relationship by its ID."""
    try:
        delete_relationship(relationship_id, db)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete relationship %d: %s", relationship_id, e)
        raise HTTPException(
            status_code=500,
            detail="Relationship could not be deleted. Please try again later.",
        )


@router.post("/auto-reference", response_model=AutoReferenceResponse)
def auto_reference_endpoint(db: Session = Depends(get_db)):
    """Auto-detect related files using embedding similarity."""
    try:
        return auto_reference(db)
    except Exception as e:
        logger.error("Failed to compute auto-references: %s", e)
        raise HTTPException(
            status_code=500,
            detail="Auto-reference detection failed. Please try again later.",
        )
