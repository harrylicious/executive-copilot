# Bugfix Requirements Document

## Introduction

The executive-copilot AI feature (eaip-layer1) has several defects and missing capabilities that degrade the user experience and reduce the usefulness of the RAG-based assistant. These issues span the backend AI pipeline (LangGraph agent, RAG chain, session store) and the React frontend (chat UI). The problems include: low-quality, shallow AI responses; no mechanism to control response tone or nuance; the AI always using the same reasoning depth regardless of query complexity; conversation context not persisting correctly within a session; hard errors returned for valid product-lookup queries in Indonesian; no copy or regenerate actions on messages; and no ability for the AI to detect and explain defective or ambiguous data in the knowledge base.

This document captures the current defective behaviors, the expected correct behaviors, and the existing behaviors that must be preserved after the fix.

---

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the user submits any query THEN the system returns responses that are shallow, lack detail, and do not fully leverage the retrieved context documents, because the RAG system prompt instructs the model to "be concise" without any guidance on depth or completeness.

1.2 WHEN the user submits a query THEN the system has no way to adjust the tone or nuance of the response (e.g., formal executive summary vs. detailed analytical report), because the `ChatRequest` schema and the RAG/agent prompts contain no `response_tone` or `nuance` parameter.

1.3 WHEN the agent classifies a query THEN the system always uses the same LLM model and temperature for both simple lookups and complex multi-step reasoning, because `KB_LLM_TEMPERATURE=0.7` and `KB_LLM_MODEL=gpt-4o-mini` are fixed globals with no per-query adaptive logic.

1.4 WHEN the user sends multiple messages in a session THEN the system does not reliably maintain conversational context, because the `SessionStore` is an in-memory dict that is re-instantiated per `AgentWorkflow` object (which is rebuilt on every request via `container.build_workflow()`), causing history to be lost between requests.

1.5 WHEN the user asks a product-lookup question in Indonesian such as "apa saja info untuk produk Sania Botol?" THEN the system returns an error response instead of a useful answer, because the retrieval pipeline fails to match Indonesian natural-language product queries against the knowledge base chunks (likely due to embedding mismatch or overly strict `min_score` threshold), and the error is surfaced to the user rather than gracefully handled.

1.6 WHEN the user receives an AI response in the chat UI THEN the system provides no copy-to-clipboard button and no regenerate button on the message bubble, because `MessageBubble.tsx` renders no action controls for assistant messages.

1.7 WHEN the AI retrieves knowledge base documents THEN the system does not detect or report defective, incomplete, or ambiguous data within those documents, because neither the RAG chain nor the agent workflow contains any data-quality analysis step or prompt.

---

### Expected Behavior (Correct)

2.1 WHEN the user submits a query THEN the system SHALL return a detailed, informative response that fully synthesizes all relevant retrieved context, with the RAG system prompt updated to instruct the model to provide thorough, well-structured answers appropriate for an executive audience.

2.2 WHEN the user submits a query with a specified `response_tone` (e.g., `"executive_summary"`, `"detailed_analysis"`, `"concise"`) THEN the system SHALL adjust the response style accordingly, by accepting a `response_tone` field in `ChatRequest` and injecting the corresponding tone instruction into the RAG and agent prompts.

2.3 WHEN the agent classifies a query as `"simple_retrieval"` THEN the system SHALL use a lower-temperature, faster model configuration, and WHEN the agent classifies a query as `"multi_step"` THEN the system SHALL use a higher-capability model configuration, so that reasoning depth is matched to query complexity.

2.4 WHEN the user sends multiple messages in a session with a valid `session_id` THEN the system SHALL maintain and correctly pass conversation history across requests, by persisting the `SessionStore` instance at the application level (e.g., as a singleton on the `ServiceContainer`) rather than recreating it per workflow build.

2.5 WHEN the user asks a product-lookup question in Indonesian such as "apa saja info untuk produk Sania Botol?" THEN the system SHALL return a useful answer by lowering the retrieval `min_score` threshold for Indonesian queries, applying query normalization or translation if needed, and returning a graceful "no information found" message (not an error) when the product genuinely does not exist in the knowledge base.

2.6 WHEN the user views an assistant message in the chat UI THEN the system SHALL display a copy-to-clipboard button and a regenerate button on the message bubble, allowing the user to copy the response text or re-submit the original query to get a new response.

2.7 WHEN the AI retrieves knowledge base documents and detects that one or more chunks contain defective data (e.g., missing required fields, contradictory values, ambiguous product names, or incomplete records) THEN the system SHALL include a data quality notice in the response that identifies the affected source(s) and provides a brief explanation and recommendation for remediation.

---

### Unchanged Behavior (Regression Prevention)

3.1 WHEN the user submits a query with `retrieval_mode="local"` THEN the system SHALL CONTINUE TO perform vector similarity search enriched with graph neighborhood and return ranked chunks.

3.2 WHEN the user submits a query with `retrieval_mode="global"` THEN the system SHALL CONTINUE TO perform community-summary-based thematic search and return ranked community summaries.

3.3 WHEN the user submits a query with `retrieval_mode="combined"` THEN the system SHALL CONTINUE TO merge local and global results within the configured token budget.

3.4 WHEN the agent classifies a query as `"clarification"` THEN the system SHALL CONTINUE TO generate a clarifying question and return it as the response without performing retrieval.

3.5 WHEN the agent classifies a query as `"multi_step"` THEN the system SHALL CONTINUE TO decompose the query into sub-questions, retrieve answers for each, and synthesize a final response.

3.6 WHEN the LLM is not configured or packages are missing THEN the system SHALL CONTINUE TO return HTTP 503 with an appropriate error message.

3.7 WHEN a request exceeds 60 seconds THEN the system SHALL CONTINUE TO return HTTP 504 with a timeout message.

3.8 WHEN the user streams a response via `POST /api/chat/stream` THEN the system SHALL CONTINUE TO emit `token`, `sources`, `metadata`, `done`, and `suggestions` SSE events in order.

3.9 WHEN the user selects a language (`id` or `en`) in the chat config THEN the system SHALL CONTINUE TO generate responses in the selected language.

3.10 WHEN the user clicks a follow-up suggestion THEN the system SHALL CONTINUE TO submit that suggestion as a new query.

3.11 WHEN the session history exceeds 20 turns THEN the system SHALL CONTINUE TO evict the oldest turns to stay within the limit.

3.12 WHEN source attributions are present in a response THEN the system SHALL CONTINUE TO display them in the `SourceAttribution` component below the message.
