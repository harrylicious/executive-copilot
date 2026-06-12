"""Pydantic schemas for the knowledge graph API."""

from pydantic import BaseModel, Field


class NodePosition(BaseModel):
    """X/Y coordinates for rendering a node on the graph canvas."""

    x: float = Field(..., description="Horizontal position of the node")
    y: float = Field(..., description="Vertical position of the node")


class GraphNode(BaseModel):
    """A single node in the knowledge graph visualization."""

    id: str = Field(..., description="Unique identifier for the node")
    label: str = Field(..., description="Display label for the node")
    type: str = Field(..., description="Node type (e.g. 'file', 'department')")
    position: NodePosition = Field(..., description="Canvas position of the node")
    data: dict = Field(default_factory=dict, description="Arbitrary metadata attached to the node")


class GraphEdge(BaseModel):
    """A directional edge connecting two nodes in the knowledge graph."""

    id: str = Field(..., description="Unique identifier for the edge")
    source: str = Field(..., description="ID of the source node")
    target: str = Field(..., description="ID of the target node")
    label: str = Field(..., description="Display label describing the relationship")
    type: str = Field(..., description="Edge type (e.g. 'references', 'depends_on')")


class GraphData(BaseModel):
    """Complete graph payload containing nodes and edges."""

    nodes: list[GraphNode] = Field(..., description="All nodes in the graph")
    edges: list[GraphEdge] = Field(..., description="All edges in the graph")


class CreateRelationshipRequest(BaseModel):
    """Request body for manually creating a file relationship."""

    source_id: int = Field(..., description="ID of the source file")
    target_id: int = Field(..., description="ID of the target file")
    relationship_type: str = Field(..., description="Type of relationship (e.g. 'references', 'depends_on')")


class AutoReferenceResponse(BaseModel):
    """Response from the auto-reference detection endpoint."""

    suggestions: list[GraphEdge] = Field(..., description="Suggested edges discovered by AI analysis")
    total_found: int = Field(..., description="Total number of relationships found")
