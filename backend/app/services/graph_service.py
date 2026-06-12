"""Graph service for knowledge graph operations.

Provides methods for building graph data from files and relationships,
creating/deleting relationships, and auto-detecting references via
embedding cosine similarity.
"""

import logging
import math

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.file import File
from app.models.file_relationship import FileRelationship
from app.schemas.graph import (
    AutoReferenceResponse,
    GraphData,
    GraphEdge,
    GraphNode,
    NodePosition,
)

logger = logging.getLogger(__name__)


def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two vectors.

    Returns 0.0 if either vector is zero-length or they differ in dimension.
    """
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0

    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def _compute_circular_positions(count: int, radius: float = 300.0) -> list[NodePosition]:
    """Compute circular layout positions for nodes.

    Distributes nodes evenly around a circle centered at (radius, radius).
    """
    positions: list[NodePosition] = []
    for i in range(count):
        angle = (2 * math.pi * i) / max(count, 1)
        x = radius + radius * math.cos(angle)
        y = radius + radius * math.sin(angle)
        positions.append(NodePosition(x=round(x, 2), y=round(y, 2)))
    return positions


def _compute_document_embedding(chunks: list[Chunk]) -> list[float] | None:
    """Compute document-level embedding as element-wise mean of chunk embeddings.

    Returns None if no chunks have embeddings.
    """
    embeddings = [c.embedding for c in chunks if c.embedding]
    if not embeddings:
        return None

    dimension = len(embeddings[0])
    n = len(embeddings)

    mean_embedding = [0.0] * dimension
    for embedding in embeddings:
        if len(embedding) != dimension:
            continue
        for i in range(dimension):
            mean_embedding[i] += embedding[i]

    for i in range(dimension):
        mean_embedding[i] /= n

    return mean_embedding


def get_graph_data(db: Session) -> GraphData:
    """Build the full knowledge graph from files and relationships.

    Queries all non-deleted files to create nodes and all FileRelationship
    records to create edges. Computes circular layout positions for nodes.

    Args:
        db: SQLAlchemy database session.

    Returns:
        GraphData containing all nodes and edges.
    """
    # Query all non-deleted files
    files = (
        db.query(File)
        .filter((File.is_deleted == False) | (File.is_deleted == None))  # noqa: E711, E712
        .all()
    )

    # Compute circular layout positions
    positions = _compute_circular_positions(len(files))

    # Build nodes
    nodes: list[GraphNode] = []
    for i, file in enumerate(files):
        node = GraphNode(
            id=str(file.id),
            label=file.name,
            type=file.file_type or "file",
            position=positions[i],
            data={
                "department": file.department,
                "path": file.path,
            },
        )
        nodes.append(node)

    # Query all relationships
    relationships = db.query(FileRelationship).all()

    # Build edges
    edges: list[GraphEdge] = []
    for rel in relationships:
        edge = GraphEdge(
            id=str(rel.id),
            source=str(rel.source_file_id),
            target=str(rel.target_file_id),
            label=rel.relationship_type,
            type=rel.relationship_type,
        )
        edges.append(edge)

    return GraphData(nodes=nodes, edges=edges)


def create_relationship(
    source_id: int, target_id: int, relationship_type: str, db: Session
) -> GraphEdge:
    """Create a new file relationship and return it as a GraphEdge.

    Args:
        source_id: ID of the source file.
        target_id: ID of the target file.
        relationship_type: Type of relationship (e.g. 'references', 'depends_on').
        db: SQLAlchemy database session.

    Returns:
        GraphEdge representing the new relationship.
    """
    relationship = FileRelationship(
        source_file_id=source_id,
        target_file_id=target_id,
        relationship_type=relationship_type,
    )
    db.add(relationship)
    db.commit()
    db.refresh(relationship)

    return GraphEdge(
        id=str(relationship.id),
        source=str(relationship.source_file_id),
        target=str(relationship.target_file_id),
        label=relationship.relationship_type,
        type=relationship.relationship_type,
    )


def delete_relationship(relationship_id: int, db: Session) -> None:
    """Delete a file relationship by ID.

    Args:
        relationship_id: ID of the FileRelationship to delete.
        db: SQLAlchemy database session.

    Raises:
        HTTPException: 404 if relationship not found.
    """
    relationship = (
        db.query(FileRelationship)
        .filter(FileRelationship.id == relationship_id)
        .first()
    )
    if relationship is None:
        raise HTTPException(status_code=404, detail="Relationship not found")

    db.delete(relationship)
    db.commit()


def auto_reference(db: Session, embedding_model=None) -> AutoReferenceResponse:
    """Auto-detect related files using embedding cosine similarity.

    Computes document-level embeddings from chunk embeddings, then finds
    file pairs with cosine similarity > 0.7 that don't already have a
    relationship.

    Args:
        db: SQLAlchemy database session.
        embedding_model: Optional embedding model (unused for now as we use
            pre-computed chunk embeddings).

    Returns:
        AutoReferenceResponse with suggested edges and total count.
    """
    # Get files with embedded status
    files = (
        db.query(File)
        .filter(
            (File.is_deleted == False) | (File.is_deleted == None),  # noqa: E711, E712
            File.embedding_status == "embedded",
        )
        .all()
    )

    if not files:
        return AutoReferenceResponse(suggestions=[], total_found=0)

    # Compute document-level embeddings from chunks
    file_embeddings: dict[int, list[float]] = {}
    for file in files:
        chunks = db.query(Chunk).filter(Chunk.file_id == file.id).all()
        doc_embedding = _compute_document_embedding(chunks)
        if doc_embedding:
            file_embeddings[file.id] = doc_embedding

    if len(file_embeddings) < 2:
        return AutoReferenceResponse(suggestions=[], total_found=0)

    # Get existing relationships to exclude
    existing_relationships = db.query(FileRelationship).all()
    existing_pairs: set[tuple[int, int]] = set()
    for rel in existing_relationships:
        existing_pairs.add((rel.source_file_id, rel.target_file_id))
        existing_pairs.add((rel.target_file_id, rel.source_file_id))

    # Compare all pairs and find similar files
    file_ids = list(file_embeddings.keys())
    suggestions: list[GraphEdge] = []
    suggestion_id = 0

    for i in range(len(file_ids)):
        for j in range(i + 1, len(file_ids)):
            source_id = file_ids[i]
            target_id = file_ids[j]

            # Skip if relationship already exists
            if (source_id, target_id) in existing_pairs:
                continue

            similarity = _cosine_similarity(
                file_embeddings[source_id],
                file_embeddings[target_id],
            )

            if similarity > 0.7:
                suggestion_id += 1
                edge = GraphEdge(
                    id=f"suggestion-{suggestion_id}",
                    source=str(source_id),
                    target=str(target_id),
                    label="related_to",
                    type="related_to",
                )
                suggestions.append(edge)

    return AutoReferenceResponse(
        suggestions=suggestions,
        total_found=len(suggestions),
    )
