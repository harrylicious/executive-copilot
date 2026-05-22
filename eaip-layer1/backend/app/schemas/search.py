"""Pydantic schemas for search-related API requests and responses."""

from pydantic import BaseModel, Field


class LocalSearchRequest(BaseModel):
    """Request schema for local (vector similarity) search."""

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=50)
    min_score: float = Field(default=0.3, ge=0.0, le=1.0)
    similarity_weight: float = Field(default=0.7, ge=0.0, le=1.0)


class GlobalSearchRequest(BaseModel):
    """Request schema for global (community-based) search."""

    query: str = Field(..., min_length=1, max_length=1000)
    num_communities: int = Field(default=3, ge=1, le=20)
    min_relevance: float = Field(default=0.1, ge=0.0, le=1.0)


class CombinedSearchRequest(BaseModel):
    """Request schema for combined local + global search."""

    query: str = Field(..., min_length=1, max_length=1000)
    max_tokens: int = Field(default=4000, ge=1000, le=16000)
    top_k: int = Field(default=5, ge=1, le=50)
    num_communities: int = Field(default=3, ge=1, le=20)


class ChunkResult(BaseModel):
    """A single chunk result from a search query."""

    text: str
    score: float
    file_id: int
    file_name: str
    department: str
    file_path: str
    chunk_index: int
    entities: list[dict]
    relationships: list[dict]


class CommunityResult(BaseModel):
    """A single community result from a global search query."""

    community_id: int
    level: int
    summary: str
    relevance_score: float
    member_entities: list[dict]
    document_references: list[dict]  # up to 3


class SearchResponse(BaseModel):
    """Structured response for all search endpoints."""

    chunks: list[ChunkResult]
    entities: list[dict]
    relationships: list[dict]
    community_summaries: list[CommunityResult]
    source_attributions: list[dict]
    metadata: dict  # {query_time_ms, total_chunks_searched, retrieval_mode}
