# Implementation Plan: LangChain Integration

## Overview

This plan implements the LangChain orchestration layer on top of the existing GraphRAG retrieval pipeline. The implementation adds LLM-powered generation (RAG), LLM-based entity extraction, multi-step agentic workflows via LangGraph, and observability via LangSmith. All new code lives under `app/services/langchain/` and exposes two new API endpoints (`/api/chat` and `/api/chat/stream`) while preserving existing retrieval endpoints unchanged.

## Tasks

- [x] 1. Set up package structure, dependencies, and configuration
  - [x] 1.1 Add LangChain dependencies to requirements.txt
    - Add `langchain`, `langchain-openai`, `langgraph`, `langsmith` with exact version pins (== operator)
    - Add `sse-starlette` for SSE streaming support
    - _Requirements: 9.1_

  - [x] 1.2 Create `app/services/langchain/` package with `__init__.py`
    - Create the package directory and `__init__.py` with lazy imports and availability check
    - Implement package-level import validation that logs package name and version for each successfully imported LangChain package
    - If any required package fails to import, log an error and expose a flag indicating LLM features are unavailable
    - _Requirements: 9.3, 9.4, 9.6_

  - [x] 1.3 Implement `LangChainSettings` in `app/services/langchain/config.py`
    - Create Pydantic `BaseSettings` class with `KB_` env prefix following existing `GraphRAGSettings` pattern
    - Add fields: `llm_provider`, `llm_model`, `llm_temperature`, `llm_max_tokens`, `llm_api_key`, `azure_openai_endpoint`, `azure_openai_api_version`, `langsmith_api_key`, `langsmith_project`, `langsmith_sample_rate`
    - Implement `field_validator` for `llm_temperature` (clamp to 0.0-2.0, log warning, apply default 0.7 if out of range)
    - Implement `field_validator` for `llm_max_tokens` (clamp to 1-32768, log warning, apply default 1024 if out of range)
    - Implement `field_validator` for `langsmith_sample_rate` (clamp to 0.0-1.0, log warning)
    - Implement `is_llm_configured()` helper method
    - _Requirements: 2.1, 2.4, 2.6, 2.7, 2.8, 9.7_

  - [x] 1.4 Implement LLM provider factory in `app/services/langchain/llm_provider.py`
    - Create `create_llm(settings: LangChainSettings) -> BaseChatModel | None` factory function
    - Support "openai" provider using `ChatOpenAI` from langchain-openai
    - Support "azure_openai" provider using `AzureChatOpenAI` with endpoint and API version
    - Return `None` and log warning if configuration is invalid or missing
    - _Requirements: 2.2, 2.3, 2.5_

- [x] 2. Implement Custom Retriever
  - [x] 2.1 Implement `CustomRetriever` in `app/services/langchain/retriever.py`
    - Extend LangChain `BaseRetriever` with `retrieval_service` as constructor parameter (dependency injection)
    - Implement `_get_relevant_documents` that delegates to `RetrievalService` based on `retrieval_mode`
    - Implement `_aget_relevant_documents` async variant
    - Support configurable retrieval mode ("local", "global", "combined") defaulting to "combined"
    - For "local" mode: pass `top_k` (default 5, range 1-50), `min_score` (default 0.5, range 0.0-1.0), `similarity_weight` (default 0.7, range 0.0-1.0)
    - For "global" mode: pass `num_communities` (default 3, range 1-20), `min_relevance` (default 0.1, range 0.0-1.0)
    - For "combined" mode: pass `max_tokens`, `top_k`, `num_communities`, `min_score`, `min_relevance`, `similarity_weight`
    - Map `SearchResult` chunks to `Document(page_content=text, metadata={file_id, file_name, department, chunk_index, score, source_type="chunk"})`
    - Map community summaries to `Document(page_content=summary, metadata={community_id, level, relevance_score, source_type="community_summary"})`
    - Propagate `ValueError` from `RetrievalService` without modification
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 1.10_

  - [ ]* 2.2 Write unit tests for `CustomRetriever`
    - Test each retrieval mode delegates correctly to `RetrievalService`
    - Test document mapping (chunks and community summaries)
    - Test parameter defaults and propagation
    - Test `ValueError` propagation
    - _Requirements: 1.1, 1.2, 1.3, 1.7, 1.8, 1.9_

- [x] 3. Implement RAG Generation Chain
  - [x] 3.1 Implement `RAGChain` in `app/services/langchain/rag_chain.py`
    - Create `RAGResponse` dataclass with `answer`, `source_attributions`, `retrieval_metadata`, `token_usage`
    - Implement `RAGChain` class with `llm`, `retriever`, and `max_context_tokens` constructor params
    - Build prompt template instructing LLM to answer based solely on provided context and attribute claims to sources
    - Implement `_truncate_context` that removes lowest-scored documents first when context exceeds token limit
    - Implement `invoke(query)` that retrieves documents, builds prompt, calls LLM, and returns structured `RAGResponse`
    - Implement `ainvoke(query)` async variant
    - Implement `astream(query)` that yields tokens as they are generated
    - When retriever returns zero documents, return a message indicating no relevant information found (no hallucination)
    - On LLM failure or unparseable response, return error indication without exposing internal details
    - Include source attributions with `file_id`, `file_name`, `department` for each contributing document
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [ ]* 3.2 Write unit tests for `RAGChain`
    - Test context truncation logic (lowest-scored removed first)
    - Test zero-document handling
    - Test source attribution extraction
    - Test error handling on LLM failure
    - _Requirements: 3.3, 3.5, 3.6, 3.8_

- [x] 4. Implement LLM-Based Entity Extraction
  - [x] 4.1 Implement `LLMEntityExtractor` in `app/services/langchain/entity_extractor.py`
    - Create class with `llm: BaseChatModel` constructor parameter
    - Implement structured output prompt that returns entities in JSON format with fields: `name`, `entity_type`, `description`
    - Implement `extract(chunk_text, chunk_id)` and `aextract(chunk_text, chunk_id)` methods
    - Return `ExtractedEntity` objects compatible with existing `EntityExtractor` interface
    - Validate entity types against allowed set: person, organization, concept, location, event, document — discard invalid types
    - Normalize entity names using existing `_normalize_name` function
    - Deduplicate entities within a chunk by composite key `(normalized_name, entity_type)`, keeping first occurrence
    - Truncate entity name to 512 characters and description to 2000 characters
    - Cap at 50 entities per chunk (retain first 50 in LLM return order)
    - Return empty list for empty/whitespace-only chunk text without invoking LLM
    - On LLM failure or unparseable output, log error and return empty list
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 4.11_

  - [ ]* 4.2 Write unit tests for `LLMEntityExtractor`
    - Test entity type validation and filtering
    - Test name normalization and deduplication
    - Test truncation limits (name 512, description 2000, max 50 entities)
    - Test empty/whitespace input handling
    - Test LLM failure graceful handling
    - _Requirements: 4.3, 4.4, 4.7, 4.8, 4.9, 4.10, 4.11_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement LangGraph Agent Workflow
  - [x] 6.1 Implement session store in `app/services/langchain/session_store.py`
    - Create `SessionStore` class with in-memory dict storage
    - Implement `get_history(session_id)` returning list of `{role, content}` dicts
    - Implement `add_turn(session_id, role, content)` with max 20 turns per session (evict oldest when exceeded)
    - Implement `clear(session_id)` method
    - _Requirements: 5.8_

  - [x] 6.2 Implement `AgentWorkflow` in `app/services/langchain/agent_workflow.py`
    - Define `AgentState` TypedDict with all required fields (query, session_id, conversation_history, retrieved_context, intermediate_steps, sub_questions, final_answer, source_attributions, retrieval_metadata, token_usage, response_type, step_count, step_limit_reached)
    - Implement `AgentWorkflow` class with `llm`, `rag_chain` constructor params and `MAX_STEPS=5`, `MAX_HISTORY_TURNS=20`
    - Implement `_classify_query` node: uses LLM to classify query as simple_retrieval, multi_step, or clarification
    - Implement `_simple_retrieval` node: routes to RAG chain and returns answer
    - Implement `_decompose_query` node: decomposes query into max 5 sub-questions
    - Implement `_retrieve_sub_question` node: retrieves context for each sub-question via RAG chain
    - Implement `_synthesize_answer` node: synthesizes combined answer from intermediate results
    - Implement `_generate_clarification` node: returns clarifying question with response_type="clarification"
    - Implement `_route_after_classification` conditional edge
    - Implement `_should_continue_reasoning` conditional edge with step_count check (max 5)
    - If max steps exceeded, return last intermediate answer with `step_limit_reached=True`
    - Implement `compile()` returning a runnable LangGraph application
    - Implement `invoke(query, session_id)` and `ainvoke(query, session_id)` methods
    - Integrate `SessionStore` for conversation history across turns
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [ ]* 6.3 Write unit tests for `AgentWorkflow`
    - Test query classification routing (simple, multi-step, clarification)
    - Test max step limit enforcement
    - Test session history management (max 20 turns)
    - Test clarification response type
    - _Requirements: 5.2, 5.5, 5.6, 5.7, 5.8_

- [x] 7. Implement LangSmith Tracing
  - [x] 7.1 Implement `TracingService` and `TracingCallbackHandler` in `app/services/langchain/tracing.py`
    - Create `TracingService` class that configures LangSmith environment variables when API key is present
    - Implement `is_enabled()` check based on `KB_LANGSMITH_API_KEY` presence
    - Implement `get_callbacks()` returning list of callback handlers when tracing is enabled
    - Implement `configure_environment()` to set `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` env vars
    - Create `TracingCallbackHandler` extending `BaseCallbackHandler`
    - Implement sampling logic based on `langsmith_sample_rate`
    - Enrich traces with retrieval_mode, documents_retrieved, total_token_count as run metadata
    - Log informational message at startup if tracing is disabled (no API key)
    - Handle LangSmith API errors gracefully (log warning, continue operation)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 7.2 Write unit tests for `TracingService`
    - Test enabled/disabled state based on API key
    - Test environment variable configuration
    - Test sample rate clamping
    - Test graceful error handling
    - _Requirements: 6.1, 6.3, 6.5, 6.7_

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement API Endpoints
  - [x] 9.1 Create API schemas in `app/schemas/chat.py`
    - Define `RetrievalMode` enum (local, global, combined)
    - Define `ChatRequest` model with `query` (1-2000 chars), optional `session_id` (max 128 chars), optional `retrieval_mode` (default combined), optional `top_k` (1-50), optional `max_tokens` (1000-16000)
    - Define `SourceAttribution`, `TokenUsage`, `RetrievalMetadata` models
    - Define `ChatResponse` model with `answer`, `source_attributions`, `retrieval_metadata`, `token_usage`, `response_type`, `step_limit_reached`
    - _Requirements: 7.1, 7.3, 7.6, 7.7_

  - [x] 9.2 Implement chat router in `app/routers/chat.py`
    - Create `APIRouter` with prefix `/api/chat`
    - Implement `POST /api/chat` endpoint:
      - Validate request body (422 for invalid query length, invalid retrieval_mode)
      - Check LLM availability (503 if not configured)
      - Route through `AgentWorkflow` with 60-second timeout
      - Return structured `ChatResponse` JSON
      - Return 504 on timeout, 500 on unrecoverable error (no internal details exposed)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.8, 7.9, 7.10_

  - [x] 9.3 Implement streaming endpoint in `app/routers/chat.py`
    - Implement `POST /api/chat/stream` endpoint returning SSE stream
    - Check LLM availability (503 if not configured) before opening stream
    - Stream tokens via LangChain streaming callbacks as "token" events
    - Emit "sources" event with source attributions after generation completes
    - Emit "metadata" event with retrieval mode, documents retrieved, token usage
    - Emit "done" event as end-of-stream signal
    - Emit "error" event on failure (no internal details) then close stream
    - Handle client disconnection: cancel in-progress LLM generation and release resources within 5 seconds
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 9.4 Register chat router in `app/main.py`
    - Import and include the chat router in the FastAPI application
    - Add startup logic to log LangChain package versions and LLM configuration status
    - Ensure existing retrieval endpoints remain operational when LLM is not configured
    - _Requirements: 9.2, 9.3, 9.4, 9.5_

- [x] 10. Integration wiring and graceful degradation
  - [x] 10.1 Wire all components together with dependency injection
    - Create a service initialization module that instantiates `LangChainSettings`, `create_llm`, `CustomRetriever`, `RAGChain`, `AgentWorkflow`, `TracingService`, and `SessionStore`
    - Implement graceful degradation: if LLM not configured or packages missing, disable LLM-dependent features while keeping retrieval operational
    - Ensure `TracingService` callbacks are attached to all LangChain operations when enabled
    - _Requirements: 2.5, 9.2, 9.4, 9.5_

  - [ ]* 10.2 Write integration tests for the chat endpoints
    - Test POST /api/chat with valid query returns structured response
    - Test POST /api/chat returns 503 when LLM not configured
    - Test POST /api/chat returns 422 for invalid inputs (empty query, too long query, invalid retrieval_mode)
    - Test POST /api/chat/stream returns SSE events in correct order
    - Test graceful degradation (existing search endpoints work without LLM config)
    - _Requirements: 7.1, 7.4, 7.5, 7.8, 7.9, 8.1, 8.6, 9.2_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- No property-based tests are included since the design does not define Correctness Properties
- Unit tests validate specific examples and edge cases
- The design explicitly uses Python — all implementations use Python with FastAPI, Pydantic, and LangChain
- Existing services (`RetrievalService`, `GraphRAGEngine`, `EntityExtractor`) are NOT modified (Requirement 9.5)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3"] },
    { "id": 1, "tasks": ["1.4"] },
    { "id": 2, "tasks": ["2.1", "6.1", "7.1", "9.1"] },
    { "id": 3, "tasks": ["2.2", "3.1", "4.1", "7.2"] },
    { "id": 4, "tasks": ["3.2", "4.2", "6.2"] },
    { "id": 5, "tasks": ["6.3", "9.2", "9.3"] },
    { "id": 6, "tasks": ["9.4", "10.1"] },
    { "id": 7, "tasks": ["10.2"] }
  ]
}
```
