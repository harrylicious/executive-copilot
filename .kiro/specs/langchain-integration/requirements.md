# Requirements Document

## Introduction

This feature integrates LangChain, LangGraph, and LangSmith into the existing executive-copilot knowledge base manager. The integration adds an LLM-powered generation layer on top of the existing custom GraphRAG retrieval pipeline, enabling the copilot to produce natural language answers (not just retrieve documents). It wraps the existing `RetrievalService` as a LangChain-compatible retriever, implements LLM-based entity extraction using the already-configured "llm-based" method, introduces LangGraph for multi-step agentic workflows, and enables LangSmith for tracing, evaluation, and prompt versioning.

## Glossary

- **Orchestration_Layer**: The LangChain-based module that coordinates query processing, retrieval, and LLM generation into a unified pipeline
- **Custom_Retriever**: A LangChain BaseRetriever implementation that wraps the existing RetrievalService to expose local, global, and combined search as LangChain-compatible document retrieval
- **Generation_Chain**: A LangChain chain (prompt template + LLM + output parser) that takes retrieved context and a user query to produce a natural language answer
- **LLM_Entity_Extractor**: An entity extraction implementation using an LLM (via LangChain) to extract entities from text chunks, fulfilling the existing "llm-based" configuration option
- **Agent_Workflow**: A LangGraph StateGraph that implements multi-step reasoning workflows with conditional routing, tool use, and state management
- **Tracing_Service**: The LangSmith integration layer that provides observability, run tracing, evaluation datasets, and prompt versioning for all LangChain operations
- **LLM_Provider**: A configurable LLM backend (e.g., OpenAI, Azure OpenAI, Anthropic) accessed through LangChain's model abstraction layer
- **RAG_Chain**: A retrieval-augmented generation chain that combines the Custom_Retriever with the Generation_Chain to answer user queries grounded in knowledge base content
- **Callback_Handler**: A LangChain callback handler that routes trace data to LangSmith for monitoring and evaluation

## Requirements

### Requirement 1: Custom LangChain Retriever Wrapper

**User Story:** As a developer, I want the existing RetrievalService wrapped as a LangChain BaseRetriever, so that the retrieval pipeline integrates seamlessly with LangChain chains and agents.

#### Acceptance Criteria

1. THE Custom_Retriever SHALL implement the LangChain BaseRetriever interface with `_get_relevant_documents` and `_aget_relevant_documents` methods
2. WHEN a query is submitted to the Custom_Retriever, THE Custom_Retriever SHALL delegate to the existing RetrievalService method corresponding to the configured retrieval mode and return results as LangChain Document objects
3. THE Custom_Retriever SHALL support configurable retrieval mode selection (local, global, combined) via retriever constructor parameters, defaulting to "combined" when no mode is specified
4. WHEN the retrieval mode is "local", THE Custom_Retriever SHALL pass top_k (default 5, range 1-50), min_score (default 0.5, range 0.0-1.0), and similarity_weight (default 0.7, range 0.0-1.0) parameters to the underlying RetrievalService.local_search method
5. WHEN the retrieval mode is "global", THE Custom_Retriever SHALL pass num_communities (default 3, range 1-20) and min_relevance (default 0.1, range 0.0-1.0) parameters to the underlying RetrievalService.global_search method
6. WHEN the retrieval mode is "combined", THE Custom_Retriever SHALL pass max_tokens (default 4000, range 1000-16000), top_k (default 5, range 1-50), num_communities (default 3, range 1-20), min_score (default 0.5, range 0.0-1.0), min_relevance (default 0.1, range 0.0-1.0), and similarity_weight (default 0.7, range 0.0-1.0) parameters to the underlying RetrievalService.combined_search method
7. THE Custom_Retriever SHALL map each SearchResult chunk to a LangChain Document with page_content set to the chunk text and metadata containing file_id, file_name, department, chunk_index, and score
8. WHEN the RetrievalService returns community_summaries, THE Custom_Retriever SHALL include them as additional Document objects with page_content set to the community summary text and metadata containing community_id, level, relevance_score, and source_type set to "community_summary"
9. IF the underlying RetrievalService raises a ValueError, THEN THE Custom_Retriever SHALL propagate the ValueError to the caller without modification
10. THE Custom_Retriever SHALL accept a RetrievalService instance as a constructor parameter, enabling dependency injection for testing and reuse of existing database sessions

### Requirement 2: LLM Provider Configuration

**User Story:** As a developer, I want configurable LLM provider settings, so that the system can connect to different LLM backends without code changes.

#### Acceptance Criteria

1. THE Orchestration_Layer SHALL support configuration of LLM provider via environment variables with the KB_ prefix (consistent with existing settings pattern)
2. THE Orchestration_Layer SHALL support at minimum OpenAI and Azure OpenAI as LLM_Provider backends through LangChain's ChatModel abstraction
3. WHEN the KB_LLM_PROVIDER environment variable is set to "openai" or "azure_openai", THE Orchestration_Layer SHALL instantiate the corresponding LangChain ChatModel class
4. THE Orchestration_Layer SHALL support configuration of model name (KB_LLM_MODEL), temperature (KB_LLM_TEMPERATURE, range 0.0 to 2.0, default 0.7), max tokens (KB_LLM_MAX_TOKENS, range 1 to 32768, default 1024), and API key (KB_LLM_API_KEY) via environment variables
5. IF an invalid or missing LLM_Provider configuration is detected at startup, THEN THE Orchestration_Layer SHALL log a warning identifying the specific configuration error and disable LLM-dependent features (generation, LLM-based entity extraction, agent workflows) while keeping retrieval-only features (local search, global search, combined search) operational
6. THE Orchestration_Layer SHALL expose LLM configuration through a Pydantic settings class following the existing GraphRAGSettings pattern (BaseSettings with env_prefix="KB_", field validators that apply defaults for out-of-range values)
7. WHEN the KB_LLM_PROVIDER is set to "azure_openai", THE Orchestration_Layer SHALL require KB_AZURE_OPENAI_ENDPOINT and KB_AZURE_OPENAI_API_VERSION environment variables in addition to the common LLM settings
8. IF KB_LLM_TEMPERATURE or KB_LLM_MAX_TOKENS is set to a value outside its valid range, THEN THE Orchestration_Layer SHALL apply the default value and log a warning identifying the rejected value

### Requirement 3: RAG Generation Chain

**User Story:** As a user, I want the copilot to generate natural language answers grounded in retrieved knowledge base content, so that I receive synthesized answers rather than raw document chunks.

#### Acceptance Criteria

1. WHEN a user query of 1 to 1000 characters is submitted, THE RAG_Chain SHALL pass it to the Custom_Retriever and produce a natural language answer containing only claims supported by the retrieved context
2. THE RAG_Chain SHALL use a prompt template that instructs the LLM to answer based solely on provided context and to attribute claims to source documents
3. WHEN the Custom_Retriever returns zero relevant documents, THE RAG_Chain SHALL respond with a message indicating no relevant information was found rather than hallucinating an answer
4. THE RAG_Chain SHALL include source attributions in the response, where each attribution contains the file_id, file_name, and department of a document whose content contributed to the answer
5. THE RAG_Chain SHALL respect a configurable maximum context token limit (range: 1000 to 16000 tokens, default: 4000) when assembling retrieved documents into the prompt
6. WHEN the assembled context exceeds the token limit, THE RAG_Chain SHALL truncate by removing lowest-scored documents first (consistent with existing combined_search truncation behavior)
7. THE Generation_Chain SHALL expose the response as a structured output containing the answer text (maximum 4000 tokens), source attributions, and retrieval metadata including retrieval_mode, number of documents retrieved, and query_time_ms
8. IF the LLM call fails or returns an unparseable response, THEN THE RAG_Chain SHALL return an error indication to the caller without exposing internal details, and SHALL NOT return a fabricated answer

### Requirement 4: LLM-Based Entity Extraction

**User Story:** As a developer, I want the "llm-based" entity extraction method implemented using LangChain, so that entity extraction quality improves over the rule-based spaCy approach.

#### Acceptance Criteria

1. WHEN the entity_extraction_method configuration is set to "llm-based", THE LLM_Entity_Extractor SHALL use a LangChain LLM chain to extract entities from chunk text
2. THE LLM_Entity_Extractor SHALL produce ExtractedEntity objects compatible with the existing EntityExtractor interface (name, normalized_name, entity_type, description, source_chunk_id)
3. THE LLM_Entity_Extractor SHALL extract entities matching the existing allowed type set: person, organization, concept, location, event, document
4. WHEN the LLM returns more than 50 entities for a single chunk, THE LLM_Entity_Extractor SHALL retain only the first 50 entities in the order returned by the LLM and discard the remainder
5. THE LLM_Entity_Extractor SHALL use a structured output prompt that returns entities in JSON format with fields: name, entity_type, and description
6. IF the LLM call fails or returns unparseable output, THEN THE LLM_Entity_Extractor SHALL log the error and return an empty entity list for that chunk
7. THE LLM_Entity_Extractor SHALL normalize entity names using the existing _normalize_name function (case-folding, whitespace collapsing, and stripping)
8. THE LLM_Entity_Extractor SHALL deduplicate entities within a chunk by the composite key (normalized_name, entity_type), keeping the first occurrence
9. IF the LLM returns an entity with an entity_type not in the allowed type set, THEN THE LLM_Entity_Extractor SHALL discard that entity
10. WHEN the chunk_text is empty or contains only whitespace, THE LLM_Entity_Extractor SHALL return an empty entity list without invoking the LLM
11. THE LLM_Entity_Extractor SHALL truncate entity name to 512 characters and description to 2000 characters to match existing schema limits

### Requirement 5: LangGraph Agent Workflow

**User Story:** As a developer, I want a LangGraph-based agent workflow, so that the copilot can handle complex multi-step reasoning tasks with conditional routing.

#### Acceptance Criteria

1. THE Agent_Workflow SHALL be implemented as a LangGraph StateGraph with typed state containing the query, retrieved context, intermediate reasoning steps, and final answer
2. THE Agent_Workflow SHALL include a routing node that uses the LLM_Provider to classify a query into one of three categories: simple retrieval, multi-step reasoning, or clarification, based on the query text and available conversation history
3. WHEN a query is classified as requiring simple retrieval, THE Agent_Workflow SHALL route directly to the RAG_Chain and return the answer
4. WHEN a query is classified as requiring multi-step reasoning, THE Agent_Workflow SHALL decompose the query into a maximum of 5 sub-questions, retrieve context for each via the RAG_Chain, and synthesize a combined answer
5. THE Agent_Workflow SHALL support a maximum of 5 reasoning steps to prevent infinite loops
6. IF the Agent_Workflow exceeds the maximum reasoning steps, THEN THE Agent_Workflow SHALL return the last synthesized intermediate answer accumulated up to that point, with a metadata flag indicating the step limit was reached
7. WHEN a query is classified as requiring clarification, THE Agent_Workflow SHALL return a response containing a clarifying question to the user without invoking the RAG_Chain, and set a metadata flag indicating the response type is "clarification"
8. THE Agent_Workflow SHALL maintain conversation state across turns within a session, retaining a maximum of 20 prior turns of conversation history per session
9. THE Agent_Workflow SHALL expose a compile method that returns a runnable LangGraph application

### Requirement 6: LangSmith Tracing and Evaluation

**User Story:** As a developer, I want LangSmith integration for tracing and evaluation, so that I can monitor LLM performance, debug issues, and version prompts.

#### Acceptance Criteria

1. WHEN the KB_LANGSMITH_API_KEY environment variable is set, THE Tracing_Service SHALL enable LangSmith tracing for all LangChain operations including retriever, chain, and LLM invocations
2. WHEN LangSmith tracing is enabled, THE Callback_Handler SHALL record run traces including input, output, latency, token usage, and retrieval metadata for each chain invocation
3. IF the KB_LANGSMITH_API_KEY is not set, THEN THE Tracing_Service SHALL operate without tracing and log an informational message at startup
4. THE Tracing_Service SHALL tag traces with the project name configurable via KB_LANGSMITH_PROJECT environment variable, defaulting to "kb-copilot" when the variable is not set
5. THE Tracing_Service SHALL support configurable trace sampling rate via KB_LANGSMITH_SAMPLE_RATE (0.0 to 1.0, default 1.0), and IF the value is outside the 0.0 to 1.0 range, THEN THE Tracing_Service SHALL clamp it to the nearest bound and log a warning
6. WHEN a trace is recorded, THE Callback_Handler SHALL include the retrieval mode, number of documents retrieved, and total token count as run metadata
7. IF the LangSmith API is unreachable or returns an error during trace submission, THEN THE Tracing_Service SHALL log a warning and continue operation without interrupting the primary request pipeline

### Requirement 7: API Endpoint for Generation

**User Story:** As a user, I want an API endpoint that accepts a question and returns a generated answer with sources, so that I can interact with the copilot through the existing FastAPI application.

#### Acceptance Criteria

1. THE Orchestration_Layer SHALL expose a POST /api/chat endpoint that accepts a JSON request body containing a required query string (1 to 2000 characters) and optional parameters: session_id, retrieval_mode, and configuration overrides for top_k and max_tokens
2. WHEN a chat request is received with a valid query, THE Orchestration_Layer SHALL route it through the Agent_Workflow and return the generated answer with source attributions within 60 seconds
3. THE POST /api/chat endpoint SHALL return a structured JSON response containing: answer (string), source_attributions (list of objects each containing file_id, file_name, and chunk_index), retrieval_metadata (mode, documents_retrieved count, query_time_ms), and token_usage (prompt_tokens, completion_tokens, total_tokens)
4. IF the LLM_Provider is not configured, THEN THE POST /api/chat endpoint SHALL return a 503 Service Unavailable response with an error message indicating that the LLM service is not available
5. IF the Agent_Workflow encounters an unrecoverable error, THEN THE POST /api/chat endpoint SHALL return a 500 Internal Server Error with an error message that does not expose internal stack traces, model names, or configuration details
6. THE POST /api/chat endpoint SHALL accept an optional session_id parameter (string, max 128 characters) to enable multi-turn conversation state
7. THE POST /api/chat endpoint SHALL accept an optional retrieval_mode parameter (local, global, combined) defaulting to "combined"
8. IF the query parameter is missing or empty or exceeds 2000 characters, THEN THE POST /api/chat endpoint SHALL return a 422 Unprocessable Entity response with an error message indicating the validation failure
9. IF the retrieval_mode parameter is provided with a value other than "local", "global", or "combined", THEN THE POST /api/chat endpoint SHALL return a 422 Unprocessable Entity response with an error message indicating the allowed values
10. IF the Agent_Workflow does not complete within 60 seconds, THEN THE POST /api/chat endpoint SHALL abort the request and return a 504 Gateway Timeout response with an error message indicating the request timed out

### Requirement 8: Streaming Response Support

**User Story:** As a user, I want streaming responses from the copilot, so that I see partial answers as they are generated rather than waiting for the full response.

#### Acceptance Criteria

1. THE Orchestration_Layer SHALL expose a POST /api/chat/stream endpoint that returns a Server-Sent Events (SSE) stream
2. WHEN a streaming chat request is received, THE Orchestration_Layer SHALL stream LLM tokens as they are generated using LangChain's streaming callback mechanism
3. THE SSE stream SHALL emit events in the following fixed order: zero or more "token" events (each containing partial answer text), followed by one "sources" event (source attributions), followed by one "metadata" event (retrieval mode, documents retrieved count, and token usage), followed by one "done" event (end of stream signal)
4. IF an error occurs during streaming, THEN THE Orchestration_Layer SHALL emit an "error" event containing an error message that does not expose internal stack traces, file paths, or configuration details, and then close the stream
5. THE streaming endpoint SHALL support the same parameters as the non-streaming /api/chat endpoint (query, session_id, retrieval_mode)
6. IF the LLM_Provider is not configured when a streaming request is received, THEN THE Orchestration_Layer SHALL return a 503 Service Unavailable response without opening an SSE stream
7. IF the client disconnects during an active stream, THEN THE Orchestration_Layer SHALL cancel the in-progress LLM generation and release associated resources within 5 seconds of detecting the disconnection

### Requirement 9: Dependency and Configuration Management

**User Story:** As a developer, I want LangChain dependencies properly managed and configured, so that the integration does not break existing functionality.

#### Acceptance Criteria

1. THE Orchestration_Layer SHALL add langchain, langchain-openai, langgraph, and langsmith as dependencies in requirements.txt with exact version pins (using == operator)
2. IF LLM-related environment variables (KB_LLM_PROVIDER, KB_LLM_API_KEY) are not configured, THEN THE Orchestration_Layer SHALL continue to serve all existing retrieval endpoints (local_search, global_search, combined_search) without error and log a warning indicating LLM features are disabled
3. WHEN the application starts, THE Orchestration_Layer SHALL attempt to import each required LangChain package (langchain, langchain-openai, langgraph, langsmith) and log the package name and version for each successfully imported package
4. IF any required LangChain package fails to import at startup, THEN THE Orchestration_Layer SHALL log an error identifying the missing package and disable LLM-dependent features while keeping retrieval-only features operational
5. THE Orchestration_Layer SHALL not modify the existing RetrievalService, GraphRAGEngine, or EntityExtractor classes (the rule-based path remains unchanged)
6. THE Orchestration_Layer SHALL organize new code under an `app/services/langchain/` package to maintain separation from existing services
7. THE Orchestration_Layer SHALL add all new configuration settings to a LangChainSettings Pydantic class with KB_ prefix environment variables, following the existing GraphRAGSettings pattern (using pydantic-settings BaseSettings with field validators that log warnings and apply defaults for invalid values)
