"""Pydantic schemas for chat API requests and responses."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RetrievalMode(str, Enum):
    """Supported retrieval modes for the chat endpoint."""

    local = "local"
    global_ = "global"
    combined = "combined"


class ChatRequest(BaseModel):
    """Request schema for the chat generation endpoint."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=128)
    retrieval_mode: RetrievalMode = RetrievalMode.combined
    top_k: Optional[int] = Field(None, ge=1, le=50)
    max_tokens: Optional[int] = Field(None, ge=1000, le=16000)


class SourceAttribution(BaseModel):
    """Source attribution for a document that contributed to the answer."""

    file_id: int
    file_name: str
    department: str
    chunk_index: int


class TokenUsage(BaseModel):
    """Token usage statistics for the LLM call."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class RetrievalMetadata(BaseModel):
    """Metadata about the retrieval step of the chat request."""

    retrieval_mode: str
    documents_retrieved: int
    query_time_ms: int


class ChatResponse(BaseModel):
    """Response schema for the chat generation endpoint."""

    answer: str
    source_attributions: list[SourceAttribution]
    retrieval_metadata: RetrievalMetadata
    token_usage: TokenUsage
    response_type: str = "answer"
    step_limit_reached: bool = False
