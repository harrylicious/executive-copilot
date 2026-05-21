"""Chat router endpoints for LLM-powered generation and streaming.

Provides POST /api/chat for synchronous generation and POST /api/chat/stream
for Server-Sent Events streaming. Both endpoints validate LLM availability
before processing and return appropriate error responses when the LLM is
not configured.

Uses the ServiceContainer from app.services.langchain.dependencies for
dependency injection, graceful degradation, and TracingService callback
attachment to all LangChain operations.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.langchain.dependencies import get_service_container

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def _check_llm_available() -> None:
    """Check if LLM features are available and configured.

    Uses the ServiceContainer to determine availability, which accounts
    for both package availability and LLM configuration status.

    Raises:
        HTTPException: 503 if LangChain packages are missing or LLM is not configured.
    """
    container = get_service_container()
    if not container.is_llm_available:
        if not container._packages_available:
            raise HTTPException(
                status_code=503,
                detail="LLM service is not available: required packages are missing.",
            )
        raise HTTPException(
            status_code=503,
            detail="LLM service is not available: LLM provider is not configured.",
        )


@router.post("")
async def chat(body: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    """Generate a chat response using the Agent Workflow.

    Validates LLM availability, routes the query through the AgentWorkflow
    with a 60-second timeout, and returns a structured ChatResponse.

    Returns:
        ChatResponse with answer, source attributions, retrieval metadata,
        token usage, response type, and step limit flag.

    Raises:
        HTTPException 503: LLM not configured or packages missing.
        HTTPException 504: Request timed out after 60 seconds.
        HTTPException 500: Unrecoverable internal error.
    """
    _check_llm_available()

    container = get_service_container()

    try:
        workflow = container.build_workflow(
            db=db,
            retrieval_mode=body.retrieval_mode.value,
            top_k=body.top_k,
            max_tokens=body.max_tokens,
        )
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="LLM service is not available: failed to create LLM instance.",
        )
    except Exception:
        logger.exception("Failed to build agent workflow")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request.",
        )

    # Run the workflow with a 60-second timeout
    try:
        result = await asyncio.wait_for(
            workflow.ainvoke(
                query=body.query,
                session_id=body.session_id or "",
            ),
            timeout=60.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Request timed out. Please try a simpler query.",
        )
    except Exception:
        logger.exception("Agent workflow encountered an unrecoverable error")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request.",
        )

    # Build structured response from agent state
    source_attributions = []
    for attr in result.get("source_attributions", []):
        source_attributions.append({
            "file_id": attr.get("file_id", 0),
            "file_name": attr.get("file_name", ""),
            "department": attr.get("department", ""),
            "chunk_index": attr.get("chunk_index", 0),
        })

    token_usage = result.get("token_usage", {})
    retrieval_metadata = result.get("retrieval_metadata", {})

    return ChatResponse(
        answer=result.get("final_answer", ""),
        source_attributions=source_attributions,
        retrieval_metadata={
            "retrieval_mode": retrieval_metadata.get("retrieval_mode", body.retrieval_mode.value),
            "documents_retrieved": retrieval_metadata.get("documents_retrieved", 0),
            "query_time_ms": retrieval_metadata.get("query_time_ms", 0),
        },
        token_usage={
            "prompt_tokens": token_usage.get("prompt_tokens", 0),
            "completion_tokens": token_usage.get("completion_tokens", 0),
            "total_tokens": token_usage.get("total_tokens", 0),
        },
        response_type=result.get("response_type", "answer"),
        step_limit_reached=result.get("step_limit_reached", False),
    )


@router.post("/stream")
async def chat_stream(
    body: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> EventSourceResponse:
    """Stream a chat response as Server-Sent Events.

    Validates LLM availability before opening the stream. Streams tokens
    as "token" events, followed by "sources", "metadata", and "done" events.
    On error, emits an "error" event and closes the stream. Handles client
    disconnection by cancelling in-progress generation.

    Returns:
        EventSourceResponse with SSE event stream.

    Raises:
        HTTPException 503: LLM not configured or packages missing.
    """
    _check_llm_available()

    container = get_service_container()

    try:
        rag_chain, retriever = container.build_rag_chain(
            db=db,
            retrieval_mode=body.retrieval_mode.value,
            top_k=body.top_k,
            max_tokens=body.max_tokens,
        )
    except RuntimeError:
        raise HTTPException(
            status_code=503,
            detail="LLM service is not available: failed to create LLM instance.",
        )
    except Exception:
        logger.exception("Failed to build RAG chain for streaming")
        raise HTTPException(
            status_code=500,
            detail="An error occurred processing your request.",
        )

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from the RAG chain streaming response."""
        try:
            # First, retrieve documents for source attributions and metadata
            documents = await retriever.ainvoke(body.query)

            # Extract source attributions from retrieved documents
            source_attributions = []
            seen_file_ids: set = set()
            for doc in documents:
                metadata = doc.metadata
                if metadata.get("source_type") != "chunk":
                    continue
                file_id = metadata.get("file_id")
                if file_id in seen_file_ids:
                    continue
                seen_file_ids.add(file_id)
                source_attributions.append({
                    "file_id": file_id,
                    "file_name": metadata.get("file_name", ""),
                    "department": metadata.get("department", ""),
                    "chunk_index": metadata.get("chunk_index", 0),
                })

            # Stream tokens from the RAG chain
            token_count = 0
            try:
                async for token in rag_chain.astream(body.query):
                    # Check for client disconnection
                    if await request.is_disconnected():
                        logger.info("Client disconnected during streaming, cancelling generation")
                        return

                    token_count += 1
                    yield {
                        "event": "token",
                        "data": json.dumps({"content": token}),
                    }
            except asyncio.CancelledError:
                logger.info("Stream cancelled due to client disconnection")
                return

            # Emit sources event
            yield {
                "event": "sources",
                "data": json.dumps({"source_attributions": source_attributions}),
            }

            # Emit metadata event
            yield {
                "event": "metadata",
                "data": json.dumps({
                    "retrieval_mode": getattr(retriever, "retrieval_mode", "combined"),
                    "documents_retrieved": len(documents),
                    "token_usage": {
                        "prompt_tokens": 0,
                        "completion_tokens": token_count,
                        "total_tokens": token_count,
                    },
                }),
            }

            # Emit done event
            yield {
                "event": "done",
                "data": json.dumps({}),
            }

        except asyncio.CancelledError:
            logger.info("Stream generation cancelled")
            return
        except Exception:
            logger.exception("Error during streaming generation")
            yield {
                "event": "error",
                "data": json.dumps({"message": "An error occurred processing your request."}),
            }

    return EventSourceResponse(
        event_generator(),
        media_type="text/event-stream",
    )
