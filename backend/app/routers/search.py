"""Search router endpoints for local, global, and combined knowledge base search."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import turbovec_settings
from app.database import get_db
from app.schemas.search import (
    CombinedSearchRequest,
    GlobalSearchRequest,
    LocalSearchRequest,
    SearchResponse,
)
from app.services.retrieval_service import RetrievalService
from app.services.retrieval_dependencies import get_retrieval_service

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/local", response_model=SearchResponse)
def local_search(body: LocalSearchRequest, db: Session = Depends(get_db)):
    """Perform a local (vector similarity) search.

    Generates a query embedding, searches against stored chunks,
    and ranks results by similarity score.
    """
    service = get_retrieval_service()
    try:
        result = service.local_search(
            query=body.query,
            top_k=body.top_k,
            min_score=body.min_score,
            similarity_weight=body.similarity_weight,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SearchResponse(
        chunks=result.chunks,
        entities=result.entities,
        relationships=result.relationships,
        community_summaries=result.community_summaries,
        source_attributions=result.source_attributions,
        metadata=result.metadata,
    )


@router.post("/global", response_model=SearchResponse)
def global_search(body: GlobalSearchRequest, db: Session = Depends(get_db)):
    """Perform a global search.

    Performs vector search using intent routing logic.
    """
    service = get_retrieval_service()
    result = service.global_search(
        query=body.query,
        num_communities=body.num_communities,
        min_relevance=body.min_relevance,
    )

    return SearchResponse(
        chunks=result.chunks,
        entities=result.entities,
        relationships=result.relationships,
        community_summaries=result.community_summaries,
        source_attributions=result.source_attributions,
        metadata=result.metadata,
    )


@router.post("/combined", response_model=SearchResponse)
def combined_search(body: CombinedSearchRequest, db: Session = Depends(get_db)):
    """Perform a combined local + global search within a token budget.

    Merges local and global results interleaved by descending relevance score,
    then truncates to fit within the configured maximum token limit.
    """
    service = get_retrieval_service()
    result = service.combined_search(
        query=body.query,
        max_tokens=body.max_tokens,
        top_k=body.top_k,
        num_communities=body.num_communities,
    )

    return SearchResponse(
        chunks=result.chunks,
        entities=result.entities,
        relationships=result.relationships,
        community_summaries=result.community_summaries,
        source_attributions=result.source_attributions,
        metadata=result.metadata,
    )
