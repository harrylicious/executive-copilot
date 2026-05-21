"""Pydantic schemas for relationship-related API requests and responses."""

from pydantic import BaseModel


class RelationshipCreateRequest(BaseModel):
    """Request schema for creating a manual relationship."""

    source_file_id: int
    target_file_id: int
    relationship_type: str


class RelationshipUpdateRequest(BaseModel):
    """Request schema for updating a relationship type."""

    relationship_type: str


class RelationshipResponse(BaseModel):
    """Response schema for a relationship."""

    model_config = {"from_attributes": True}

    id: int
    source_file_id: int
    target_file_id: int
    relationship_type: str
    is_manual: bool
