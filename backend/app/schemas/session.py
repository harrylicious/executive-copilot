"""Pydantic schemas for chat session API requests and responses."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MessageSchema(BaseModel):
    """Schema for a single chat message."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    session_id: str = Field(alias="sessionId", default="")
    role: str
    content: str = ""
    sources: Optional[list] = None
    metadata_json: Optional[dict] = Field(alias="metadataJson", default=None)
    error: Optional[str] = None
    timestamp: float


class SessionSchema(BaseModel):
    """Schema for a chat session (without messages)."""

    id: str
    title: Optional[str] = None
    retrieval_mode: Optional[str] = "combined"
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PaginatedSessionsResponse(BaseModel):
    """Paginated response for listing sessions."""

    items: list[SessionSchema]
    total: int
    has_more: bool


class SessionWithMessagesSchema(SessionSchema):
    """Schema for a chat session including its messages."""

    messages: list[MessageSchema] = []


class SaveSessionRequest(BaseModel):
    """Request body for saving/updating a session with its messages."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: Optional[str] = None
    retrieval_mode: Optional[str] = Field(alias="retrievalMode", default="combined")
    top_k: Optional[int] = Field(alias="topK", default=None)
    max_tokens: Optional[int] = Field(alias="maxTokens", default=None)
    messages: list[MessageSchema] = []


class UpdateSessionTitleRequest(BaseModel):
    """Request body for updating a session title."""

    title: str = Field(..., min_length=1, max_length=200)
