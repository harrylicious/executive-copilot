"""Pydantic schemas for graph-related API responses."""

from pydantic import BaseModel


class GraphNodePosition(BaseModel):
    """Position coordinates for a graph node."""

    x: float
    y: float


class GraphNodeData(BaseModel):
    """Data payload for a graph node."""

    label: str
    department: str
    fileId: int


class GraphNodeResponse(BaseModel):
    """Response schema for a single graph node."""

    id: str
    data: GraphNodeData
    position: GraphNodePosition


class GraphEdgeResponse(BaseModel):
    """Response schema for a single graph edge."""

    id: str
    source: str
    target: str
    label: str | None = None


class GraphDataResponse(BaseModel):
    """Response schema for the full graph data (nodes + edges)."""

    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]
