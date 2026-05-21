"""Pydantic schemas for chat session API requests and responses."""

from typing import Optional

from pydantic import BaseModel, Field


class MessageSchema(BaseModel):
    """Schema for a single chat message."""

    id: str
    session_id: str
    role: str
    content: str = ""
    sources: Optional[list] = None
    metadata_json: Optional[dict] = None
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


class SessionWithMessagesSchema(SessionSchema):
    """Schema for a chat session including its messages."""

    messages: list[MessageSchema] = []


class SaveSessionRequest(BaseModel):
    """Request body for saving/updating a session with its messages."""

    id: str
    title: Optional[str] = None
    retrieval_mode: Optional[str] = "combined"
    top_k: Optional[int] = None
    max_tokens: Optional[int] = None
    messages: list[MessageSchema] = []


class UpdateSessionTitleRequest(BaseModel):
    """Request body for updating a session title."""

    title: str = Field(..., min_length=1, max_length=200)
