
# ai-enhancement Bugfix Design

## Overview

This document formalizes the fix strategy for seven defects in the eaip-layer1 executive-copilot AI feature. The defects span the backend AI pipeline (RAG chain, LangGraph agent workflow, retrieval service, service container) and the React frontend (MessageBubble.tsx). The fix approach is minimal and targeted: each change addresses exactly one defect, preserves all existing retrieval modes and streaming behavior, and is validated by the two-phase testing strategy described in the Testing Strategy section.

The seven defects and their fix locations are:

| # | Defect | Fix Location |
|---|--------|-------------|
| 1 | Shallow responses due to 'be concise' system prompt | rag_chain.py - _RAG_SYSTEM_PROMPT |
| 2 | No response_tone/nuance parameter | chat.py schema + rag_chain.py + agent_workflow.py |
| 3 | Fixed LLM model/temperature regardless of query complexity | dependencies.py + llm_provider.py + agent_workflow.py |
| 4 | SessionStore re-instantiated per request | dependencies.py (already fixed in ServiceContainer; AgentWorkflow lazy-init is the residual risk) |
| 5 | Indonesian product-lookup queries return errors | retriever.py + retrieval_service.py |
| 6 | No copy/regenerate buttons on MessageBubble | MessageBubble.tsx |
| 7 | No data-quality detection in RAG pipeline | rag_chain.py (new _check_data_quality step) |

---

## Glossary

- **Bug_Condition (C)**: The set of inputs or system states that trigger one of the seven defects.
- **Property (P)**: The desired correct behavior when the bug condition holds.
- **Preservation**: All existing behaviors that must remain unchanged after the fix (retrieval modes, streaming, session eviction, language selection, error handling).
- **_RAG_SYSTEM_PROMPT**: The module-level string constant in rag_chain.py that is injected as the SystemMessage for every LLM call in the RAG chain.
- **response_tone**: A new optional field on ChatRequest (and its frontend counterpart) that controls the verbosity and style of the generated answer (e.g., executive_summary, detailed_analysis, concise).
- **AdaptiveLLM**: A thin wrapper or factory that selects model name and temperature based on the query classification produced by AgentWorkflow._classify_query.
- **SessionStore**: The in-memory dict-based conversation history store in session_store.py. One instance is shared across all requests via ServiceContainer.session_store.
- **ServiceContainer**: The application-level singleton in dependencies.py that owns the shared SessionStore, LLM, and tracing service.
- **min_score**: The minimum cosine-similarity threshold in CustomRetriever / RetrievalService.local_search below which chunks are discarded.
- **DataQualityNotice**: A structured annotation appended to the RAG response when one or more retrieved chunks are detected as defective, incomplete, or ambiguous.
- **MessageBubble**: The React component in MessageBubble.tsx that renders a single chat message (user or assistant).
- **isBugCondition(input)**: Pseudocode predicate that returns true when the given input triggers one of the seven defects.
- **expectedBehavior(result)**: Pseudocode predicate that returns true when the result satisfies the correct post-fix behavior.

---

## Bug Details

### Bug Condition

The seven defects share a common structure: each is triggered by a specific input condition that the current code fails to handle correctly. The combined bug condition is:

```
FUNCTION isBugCondition(input)
  INPUT: input of type ChatRequest | UIEvent | RetrievalContext
  OUTPUT: boolean

  -- Defect 1: any query triggers shallow response
  IF input IS ChatRequest
    AND _RAG_SYSTEM_PROMPT contains 'Be concise and direct'
    RETURN true

  -- Defect 2: query submitted without tone control
  IF input IS ChatRequest
    AND input.response_tone IS NULL  -- field does not exist yet
    RETURN true

  -- Defect 3: query classified as multi_step or simple_retrieval
  IF input IS AgentState
    AND llm.model == settings.llm_model  -- same model for all classifications
    AND llm.temperature == settings.llm_temperature  -- same temperature always
    RETURN true

  -- Defect 4: second request in same session
  IF input IS ChatRequest
    AND input.session_id IS NOT NULL
    AND AgentWorkflow._session_store IS None  -- lazy-init creates new store
    RETURN true

  -- Defect 5: Indonesian product-lookup query
  IF input IS ChatRequest
    AND input.language == 'id'
    AND isProductLookupQuery(input.query)
    AND retriever.min_score >= 0.3  -- threshold too strict for Indonesian
    RETURN true

  -- Defect 6: user views assistant message in chat UI
  IF input IS UIEvent
    AND input.messageRole == 'assistant'
    AND MessageBubble renders no copy button
    AND MessageBubble renders no regenerate button
    RETURN true

  -- Defect 7: RAG retrieves chunks with defective data
  IF input IS RetrievalContext
    AND EXISTS chunk IN input.documents WHERE isDefectiveChunk(chunk)
    AND response contains no DataQualityNotice
    RETURN true

  RETURN false
END FUNCTION
```

### Examples

**Defect 1 - Shallow response:**
- Input: query='Jelaskan strategi ekspansi produk Sania untuk Q3', language='id'
- Actual: Two-sentence answer that ignores 80% of retrieved context
- Expected: Multi-paragraph executive-quality synthesis citing all relevant sources

**Defect 2 - No tone control:**
- Input: query='Ringkas kinerja Q2', response_tone='executive_summary' (field rejected by schema)
- Actual: HTTP 422 Unprocessable Entity (unknown field)
- Expected: Concise bullet-point executive summary

**Defect 3 - Fixed model/temperature:**
- Input: complex multi-step query classified as 'multi_step'
- Actual: Uses gpt-4o-mini at temperature=0.7 (same as simple lookup)
- Expected: Uses higher-capability model at lower temperature for deterministic reasoning

**Defect 4 - Session history lost:**
- Input: Two sequential requests with session_id='abc123'
- Actual: Second request has empty conversation_history (new SessionStore created)
- Expected: Second request sees first turn in conversation_history

**Defect 5 - Indonesian product lookup error:**
- Input: query='apa saja info untuk produk Sania Botol?', language='id'
- Actual: Error response or empty result (min_score=0.3 filters out all Indonesian-language chunks)
- Expected: Relevant product information retrieved and answered in Indonesian

**Defect 6 - No copy/regenerate buttons:**
- Input: User views any completed assistant message
- Actual: No action buttons visible on the message bubble
- Expected: Copy-to-clipboard and Regenerate buttons appear on hover/focus

**Defect 7 - No data quality notice:**
- Input: Query retrieves a chunk with missing required fields (e.g., product name is empty)
- Actual: Answer silently uses defective data with no warning
- Expected: Response includes a DataQualityNotice identifying the affected source and recommending remediation

---

## Expected Behavior

### Preservation Requirements

**Unchanged Behaviors:**
- All three retrieval modes (local, global, combined) must continue to work exactly as before (Requirements 3.1-3.3)
- The clarification query path in AgentWorkflow must continue to generate clarifying questions (Requirement 3.4)
- The multi-step decomposition and sub-question retrieval loop must continue to work (Requirement 3.5)
- HTTP 503 must still be returned when LLM is not configured (Requirement 3.6)
- HTTP 504 must still be returned on 60-second timeout (Requirement 3.7)
- SSE streaming must continue to emit token, sources, metadata, done, and suggestions events in order (Requirement 3.8)
- Language selection (id/en) must continue to control response language (Requirement 3.9)
- Follow-up suggestion clicks must continue to submit as new queries (Requirement 3.10)
- Session history eviction at 20 turns must continue to work (Requirement 3.11)
- Source attributions must continue to display in the SourceAttribution component (Requirement 3.12)

**Scope:**
All inputs that do NOT trigger one of the seven bug conditions must be completely unaffected by the fix. This includes:
- Queries in English (language='en') with no response_tone
- Queries using retrieval_mode='global' or 'local'
- Requests without a session_id
- Streaming requests via POST /api/chat/stream
- User messages in the chat UI (copy/regenerate only appear on assistant messages)
- Retrieval of chunks that pass all data-quality checks (no DataQualityNotice appended)

---

## Hypothesized Root Cause

### Defect 1 - Shallow Responses

**Root Cause**: Rule 5 in _RAG_SYSTEM_PROMPT (rag_chain.py line ~35) reads:
```
5. Be concise and direct in your answer.
```
This instruction overrides all other context and causes the model to truncate its response regardless of how much relevant information was retrieved. The fix is to replace this rule with guidance that instructs the model to be thorough and well-structured, appropriate for an executive audience.

### Defect 2 - No Tone Control

**Root Cause**: The ChatRequest Pydantic model in schemas/chat.py has no 
esponse_tone field. The _RAG_SYSTEM_PROMPT and _SYNTHESIS_PROMPT in rag_chain.py and agent_workflow.py have no tone-injection placeholder. The fix requires:
1. Adding `response_tone: Optional[ResponseTone]` to `ChatRequest`
2. Adding a `{tone_instruction}` placeholder to `_RAG_SYSTEM_PROMPT`
3. Passing `response_tone` through `build_workflow()` and `build_rag_chain()` to `RAGChain` and `AgentWorkflow`
4. Adding the corresponding `response_tone` field to the frontend `ChatRequest` type and `ChatConfig` component

### Defect 3 - Fixed Model/Temperature

**Root Cause**: `ServiceContainer.__init__` creates a single `self.llm` instance using `settings.llm_model` and `settings.llm_temperature`. This same instance is passed to both `RAGChain` and `AgentWorkflow` regardless of query classification. The fix is to create two LLM configurations in `ServiceContainer`:
- `self.llm_simple`: lower-capability, lower-temperature (fast, deterministic lookups)
- `self.llm_complex`: higher-capability, slightly higher temperature (multi-step reasoning)

Then in `AgentWorkflow._simple_retrieval`, use `llm_simple`; in `_synthesize_answer` and `_decompose_query`, use `llm_complex`.

### Defect 4 - SessionStore Lost Between Requests

**Root Cause**: `AgentWorkflow.__init__` sets `self._session_store = None`. The `session_store` property lazy-initializes a **new** `SessionStore()` if `_session_store is None`. Although `ServiceContainer.build_workflow()` correctly injects `workflow.session_store = self.session_store` after construction, there is a window where the lazy-init fires before injection if any code path accesses `self.session_store` during `__init__` or `compile()`. The safer fix is to remove the lazy-init entirely: `AgentWorkflow.__init__` should require a `session_store` parameter and store it directly, eliminating the None-check path.

### Defect 5 - Indonesian Product-Lookup Errors

**Root Cause**: Two compounding issues:
1. **Embedding mismatch**: The embedding model encodes Indonesian natural-language queries differently from the English-biased product-name chunks in the vector store, producing lower cosine similarity scores.
2. **Strict min_score threshold**: `CustomRetriever.min_score = 0.3` (default in retriever.py). For Indonesian queries, valid product chunks may score 0.15-0.28, falling below the threshold and returning zero results, which triggers the error response path.

The fix is to lower `min_score` to `0.15` for Indonesian-language queries and add a graceful 'no information found' fallback that returns a user-friendly message instead of an error when zero chunks are retrieved.

### Defect 6 - No Copy/Regenerate Buttons

**Root Cause**: `MessageBubble.tsx` renders no action controls for assistant messages. The component has no state for hover/focus visibility and no handlers for clipboard write or query re-submission. The fix adds a button group that appears when the user hovers over or focuses a completed assistant message bubble.

### Defect 7 - No Data Quality Detection

**Root Cause**: `RAGChain._build_messages()` passes all retrieved documents to the LLM without any pre-processing step to inspect document quality. The fix adds a `_check_data_quality(documents)` method that scans each chunk's metadata and content for known defect patterns (empty text, missing file_name, suspiciously short content, contradictory field values) and returns a list of `DataQualityIssue` objects. If any issues are found, a structured notice is appended to the final answer.


---

## Correctness Properties

Property 1: Bug Condition - Thorough, Tone-Aware, Adaptive AI Responses

_For any_ ChatRequest where the bug condition holds (isBugCondition returns true for any of defects 1-5 or 7), the fixed backend SHALL return a response that:
- Contains a detailed, well-structured answer that fully synthesizes all relevant retrieved context (defect 1)
- Applies the requested response_tone style when response_tone is specified (defect 2)
- Uses the model and temperature configuration appropriate for the classified query type (defect 3)
- Includes the correct conversation history from the shared SessionStore (defect 4)
- Returns a useful answer or a graceful "no information found" message for Indonesian product queries (defect 5)
- Appends a DataQualityNotice when defective chunks are detected in the retrieved context (defect 7)

**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 2.7**

Property 2: Bug Condition - Copy and Regenerate UI Actions

_For any_ UIEvent where the user views a completed assistant message (defect 6), the fixed MessageBubble component SHALL render a copy-to-clipboard button and a regenerate button that are accessible and functional.

**Validates: Requirements 2.6**

Property 3: Preservation - All Non-Buggy Inputs Unchanged

_For any_ input where the bug condition does NOT hold (isBugCondition returns false), the fixed code SHALL produce exactly the same behavior as the original code, preserving all retrieval modes, streaming behavior, session eviction, language selection, error handling, and source attribution display.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12**

---

## Fix Implementation

### Changes Required

The following changes are organized by file. Each change is minimal and targeted.

---

### File: `app/services/langchain/rag_chain.py`

**Change 1 - Replace concise instruction with thorough-response instruction (Defect 1)**

Replace rule 5 in `_RAG_SYSTEM_PROMPT`:

```python
# BEFORE
_RAG_SYSTEM_PROMPT = """\
You are a knowledge base assistant. Answer the user's question based ONLY on \
the provided context documents. Follow these rules strictly:

1. Only use information from the provided context to answer the question.
2. If the context does not contain enough information to answer, say so clearly.
3. Attribute claims to their source documents by referencing the source number \
(e.g., [Source 1], [Source 2]).
4. Do not fabricate, hallucinate, or infer information beyond what is explicitly \
stated in the context.
5. Be concise and direct in your answer.
6. {language_instruction}
"""

# AFTER
_RAG_SYSTEM_PROMPT = """\
You are an executive knowledge base assistant. Answer the user's question based ONLY on \
the provided context documents. Follow these rules strictly:

1. Only use information from the provided context to answer the question.
2. If the context does not contain enough information to answer, say so clearly.
3. Attribute claims to their source documents by referencing the source number \
(e.g., [Source 1], [Source 2]).
4. Do not fabricate, hallucinate, or infer information beyond what is explicitly \
stated in the context.
5. Provide a thorough, well-structured answer that fully synthesizes all relevant \
information from the context. Use headings, bullet points, or numbered lists where \
appropriate to improve readability for an executive audience.
6. {tone_instruction}
7. {language_instruction}
"""
```

**Change 2 - Add tone instruction map and inject into prompt (Defect 2)**

```python
_TONE_INSTRUCTIONS = {
    "executive_summary": (
        "Format your response as a concise executive summary: lead with the key "
        "finding or recommendation, then provide supporting evidence in 2-3 bullet points."
    ),
    "detailed_analysis": (
        "Format your response as a detailed analytical report: include background context, "
        "key findings with evidence, implications, and recommendations."
    ),
    "concise": (
        "Be concise and direct. Provide the essential answer in 1-3 sentences."
    ),
    "default": (
        "Structure your response clearly with appropriate headings and bullet points "
        "to make it easy to scan and understand."
    ),
}
```

Update `RAGChain.__init__` to accept `response_tone: str = "default"` and store it.
Update `_build_messages` to inject `_TONE_INSTRUCTIONS.get(self.response_tone, _TONE_INSTRUCTIONS["default"])` as `{tone_instruction}`.

**Change 3 - Add data quality check step (Defect 7)**

Add a new method `_check_data_quality(documents: list[Document]) -> list[dict]` that returns a list of issue dicts:

```python
def _check_data_quality(self, documents: list[Document]) -> list[dict]:
    """Scan retrieved documents for defective, incomplete, or ambiguous data.

    Checks each chunk-type document for:
    - Empty or near-empty page_content (< 20 characters)
    - Missing file_name in metadata
    - Missing or zero file_id in metadata
    - Suspiciously short content that may indicate a truncated or corrupt chunk

    Returns:
        List of issue dicts with keys: source_number, file_name, issue_type, recommendation
    """
    issues = []
    for i, doc in enumerate(documents, 1):
        if doc.metadata.get("source_type") != "chunk":
            continue
        content = doc.page_content.strip()
        file_name = doc.metadata.get("file_name", "")
        file_id = doc.metadata.get("file_id")

        if not content or len(content) < 20:
            issues.append({
                "source_number": i,
                "file_name": file_name or "unknown",
                "issue_type": "empty_or_truncated_content",
                "recommendation": "Re-ingest or re-chunk this document to ensure content is captured correctly.",
            })
        elif not file_name:
            issues.append({
                "source_number": i,
                "file_name": "unknown",
                "issue_type": "missing_file_name",
                "recommendation": "Check the file metadata in the knowledge base and re-index if necessary.",
            })
        elif not file_id:
            issues.append({
                "source_number": i,
                "file_name": file_name,
                "issue_type": "missing_file_id",
                "recommendation": "Re-index this document to restore its file association.",
            })
    return issues
```

Call `_check_data_quality` in both `invoke` and `ainvoke` after truncation. If issues are found, append a `DataQualityNotice` section to the LLM answer:

```python
FUNCTION appendDataQualityNotice(answer, issues)
  IF issues is empty THEN RETURN answer
  notice = "\n\n---\n**Data Quality Notice**\n"
  FOR EACH issue IN issues DO
    notice += f"- Source {issue.source_number} ({issue.file_name}): "
    notice += f"{issue.issue_type}. {issue.recommendation}\n"
  END FOR
  RETURN answer + notice
END FUNCTION
```

---

### File: `app/schemas/chat.py`

**Change 4 - Add ResponseTone enum and response_tone field to ChatRequest (Defect 2)**

```python
class ResponseTone(str, Enum):
    executive_summary = "executive_summary"
    detailed_analysis = "detailed_analysis"
    concise = "concise"
    default = "default"

class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=128)
    retrieval_mode: RetrievalMode = RetrievalMode.combined
    top_k: Optional[int] = Field(None, ge=1, le=50)
    max_tokens: Optional[int] = Field(None, ge=1000, le=16000)
    language: Language = Language.id
    response_tone: ResponseTone = ResponseTone.default  # NEW
```

---

### File: `app/services/langchain/dependencies.py`

**Change 5 - Add adaptive LLM support (Defect 3)**

Add two LLM instances to `ServiceContainer.__init__`:

```python
# Simple retrieval LLM: fast, deterministic
self.llm_simple: BaseChatModel | None = None
# Complex reasoning LLM: higher capability
self.llm_complex: BaseChatModel | None = None

if self._packages_available and self.settings.is_llm_configured():
    self.llm = self._create_llm()          # default (backward compat)
    self.llm_simple = self._create_llm_simple()
    self.llm_complex = self._create_llm_complex()
```

Add factory methods:

```python
def _create_llm_simple(self) -> BaseChatModel | None:
    """Create a fast, low-temperature LLM for simple retrieval queries."""
    # Uses same provider as self.llm but with:
    # - model: settings.llm_model (e.g., gpt-4o-mini)
    # - temperature: 0.0 (deterministic)
    # - max_tokens: settings.llm_max_tokens
    ...

def _create_llm_complex(self) -> BaseChatModel | None:
    """Create a higher-capability LLM for multi-step reasoning queries."""
    # Uses same provider as self.llm but with:
    # - model: settings.llm_complex_model (new env var KB_LLM_COMPLEX_MODEL,
    #          defaults to settings.llm_model if not set)
    # - temperature: settings.llm_complex_temperature (new env var
    #          KB_LLM_COMPLEX_TEMPERATURE, defaults to 0.3)
    # - max_tokens: settings.llm_max_tokens
    ...
```

Add two new settings fields to `LangChainSettings`:

```python
llm_complex_model: str = ""          # KB_LLM_COMPLEX_MODEL; defaults to llm_model
llm_complex_temperature: float = 0.3  # KB_LLM_COMPLEX_TEMPERATURE
```

Update `build_workflow` to pass both LLMs to `AgentWorkflow`:

```python
workflow = AgentWorkflow(
    llm=self.llm,
    llm_simple=self.llm_simple or self.llm,
    llm_complex=self.llm_complex or self.llm,
    rag_chain=rag_chain,
    language=language,
    session_store=self.session_store,   # Change 6: pass directly
)
```

**Change 6 - Pass session_store directly to AgentWorkflow (Defect 4)**

In `build_workflow`, replace:
```python
workflow = AgentWorkflow(llm=self.llm, rag_chain=rag_chain, language=language)
workflow.session_store = self.session_store
```
With:
```python
workflow = AgentWorkflow(
    llm=self.llm,
    rag_chain=rag_chain,
    language=language,
    session_store=self.session_store,
)
```

**Change 7 - Pass response_tone through build_workflow and build_rag_chain (Defect 2)**

Add `response_tone: str = "default"` parameter to both `build_workflow` and `build_rag_chain`, and forward it to `RAGChain(response_tone=response_tone, ...)`.

---

### File: `app/services/langchain/agent_workflow.py`

**Change 8 - Remove lazy-init; require session_store in constructor (Defect 4)**

```python
# BEFORE
def __init__(self, llm, rag_chain, language="id"):
    self.llm = llm
    self.rag_chain = rag_chain
    self.language = language
    self._session_store = None   # lazy-init
    self._graph = self.compile()

@property
def session_store(self):
    if self._session_store is None:
        from app.services.langchain.session_store import SessionStore
        self._session_store = SessionStore()
    return self._session_store

# AFTER
def __init__(self, llm, rag_chain, language="id", session_store=None,
             llm_simple=None, llm_complex=None):
    self.llm = llm
    self.llm_simple = llm_simple or llm
    self.llm_complex = llm_complex or llm
    self.rag_chain = rag_chain
    self.language = language
    # Require explicit injection; fall back to new store only as last resort
    if session_store is None:
        from app.services.langchain.session_store import SessionStore
        session_store = SessionStore()
    self.session_store = session_store
    self._graph = self.compile()
```

**Change 9 - Use adaptive LLM in classification and synthesis nodes (Defect 3)**

In `_classify_query`: use `self.llm` (classification is lightweight, keep as-is).
In `_simple_retrieval`: the RAGChain already uses `llm_simple` (passed via `build_workflow`).
In `_decompose_query`: use `self.llm_complex` for decomposition.
In `_synthesize_answer`: use `self.llm_complex` for synthesis.
In `_generate_clarification`: use `self.llm` (lightweight).

---

### File: `app/services/langchain/retriever.py`

**Change 10 - Lower min_score for Indonesian queries (Defect 5)**

Add a `language` field to `CustomRetriever` and override `min_score` when language is 'id':

```python
class CustomRetriever(BaseRetriever):
    retrieval_service: Any
    retrieval_mode: str = "combined"
    top_k: int = 10
    min_score: float = 0.3
    similarity_weight: float = 0.7
    num_communities: int = 3
    min_relevance: float = 0.1
    max_tokens: int = 4000
    language: str = "id"   # NEW

    _INDONESIAN_MIN_SCORE: ClassVar[float] = 0.15

    def _effective_min_score(self) -> float:
        """Return the effective min_score, lowered for Indonesian queries."""
        if self.language == "id":
            return self._INDONESIAN_MIN_SCORE
        return self.min_score
```

Use `self._effective_min_score()` in `_execute_search` instead of `self.min_score`.

Update `ServiceContainer.build_workflow` and `build_rag_chain` to pass `language` to `CustomRetriever`.

**Change 11 - Graceful fallback for zero-result Indonesian queries (Defect 5)**

In `RAGChain.invoke` and `ainvoke`, when `documents` is empty and `language == 'id'`, return a localized "no information found" message instead of the generic English error:

```python
_NO_DOCUMENTS_RESPONSE_ID = (
    "Maaf, saya tidak dapat menemukan informasi yang relevan di basis pengetahuan "
    "untuk pertanyaan Anda. Coba ubah kata kunci atau tanyakan topik lain."
)
```

---

### File: `app/routers/chat.py`

**Change 12 - Forward response_tone to build_workflow and build_rag_chain (Defect 2)**

```python
workflow = container.build_workflow(
    db=db,
    retrieval_mode=body.retrieval_mode.value,
    top_k=body.top_k,
    max_tokens=body.max_tokens,
    language=body.language.value,
    response_tone=body.response_tone.value,   # NEW
)
```

Similarly for `build_rag_chain` in the streaming endpoint.

---

### File: `frontend/src/types/index.ts`

**Change 13 - Add response_tone to frontend ChatRequest type (Defect 2)**

```typescript
export type ResponseTone = "executive_summary" | "detailed_analysis" | "concise" | "default";

export interface ChatRequest {
  query: string;
  sessionId?: string;
  retrievalMode?: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
  language?: "id" | "en";
  responseTone?: ResponseTone;   // NEW
}

export interface ChatConfig {
  retrievalMode: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
  language: "id" | "en";
  responseTone?: ResponseTone;   // NEW
}
```

---

### File: `frontend/src/components/Chat/MessageBubble.tsx`

**Change 14 - Add copy-to-clipboard and regenerate buttons (Defect 6)**

Add `onRegenerate?: () => void` to `MessageBubbleProps`.
Add `useState<boolean>` for hover state.
Add a button group that renders only for completed, non-streaming assistant messages:

```tsx
// New props
interface MessageBubbleProps {
  message: ChatMessage;
  onSuggestionClick?: (suggestion: string) => void;
  onRegenerate?: () => void;   // NEW
}

// New state
const [showActions, setShowActions] = useState(false);
const [copied, setCopied] = useState(false);

// Copy handler
const handleCopy = useCallback(async () => {
  if (!message.content) return;
  await navigator.clipboard.writeText(message.content);
  setCopied(true);
  setTimeout(() => setCopied(false), 2000);
}, [message.content]);

// Render action buttons for completed assistant messages
{!isUser && message.isComplete && !message.isStreaming && (
  <div
    className={cn(
      "flex items-center gap-1 mt-1 transition-opacity",
      showActions ? "opacity-100" : "opacity-0"
    )}
    role="toolbar"
    aria-label="Message actions"
  >
    <button
      onClick={handleCopy}
      className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
      title={copied ? "Copied!" : "Copy to clipboard"}
      aria-label={copied ? "Copied!" : "Copy message to clipboard"}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </button>
    {onRegenerate && (
      <button
        onClick={onRegenerate}
        className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
        title="Regenerate response"
        aria-label="Regenerate this response"
      >
        <RefreshCw className="size-3.5" />
      </button>
    )}
  </div>
)}
```

Wrap the assistant message content div with `onMouseEnter`/`onMouseLeave` and `onFocus`/`onBlur` handlers that set `showActions`.

Import `Copy`, `Check`, `RefreshCw` from `lucide-react`.

---

### File: `frontend/src/components/Chat/MessageList.tsx`

**Change 15 - Wire onRegenerate from MessageList to MessageBubble (Defect 6)**

Pass an `onRegenerate` callback to each `MessageBubble` for assistant messages. The callback should re-submit the preceding user message's content as a new query.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate each bug on unfixed code (exploratory checking), then verify the fix works correctly and preserves all existing behavior (fix checking and preservation checking).

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate each of the seven bugs BEFORE implementing the fix. Confirm or refute the root cause analysis.

**Test Plan**: Write tests that exercise each bug condition against the UNFIXED code and assert the defective behavior is observable. These tests are expected to FAIL on unfixed code and PASS after the fix.

**Test Cases**:

1. **Shallow Response Test** (Defect 1): Submit a query with 5+ relevant retrieved documents and assert that the response length exceeds 200 words and references at least 2 sources. Will fail on unfixed code because the "be concise" rule truncates the response.

2. **Tone Rejection Test** (Defect 2): Submit a `ChatRequest` JSON with `response_tone="executive_summary"` and assert HTTP 200 (not 422). Will fail on unfixed code because the field is not in the schema.

3. **Fixed Model Test** (Defect 3): Classify a query as `multi_step`, then assert that the LLM used for synthesis has a different model/temperature than the LLM used for simple retrieval. Will fail on unfixed code because both use the same instance.

4. **Session History Loss Test** (Defect 4): Send two sequential requests with the same `session_id`. Assert that the second request's `conversation_history` contains the first turn. Will fail on unfixed code if the lazy-init creates a new SessionStore.

5. **Indonesian Product Lookup Test** (Defect 5): Submit `query="apa saja info untuk produk Sania Botol?"` with `language="id"`. Assert that the response is not an error message and contains product-related content. Will fail on unfixed code due to min_score filtering.

6. **Missing Action Buttons Test** (Defect 6): Render `MessageBubble` with a completed assistant message and assert that a copy button and regenerate button are present in the DOM. Will fail on unfixed code because no action buttons are rendered.

7. **Silent Defective Data Test** (Defect 7): Inject a document with empty `page_content` into the retrieval context and assert that the response contains a "Data Quality Notice" section. Will fail on unfixed code because no quality check exists.

**Expected Counterexamples**:
- Defect 1: Response is 1-3 sentences despite 5 relevant documents being retrieved
- Defect 2: HTTP 422 with "extra fields not permitted" validation error
- Defect 3: `workflow.llm is workflow.rag_chain.llm` evaluates to True (same object)
- Defect 4: `conversation_history` is `[]` on the second request
- Defect 5: Response is `_ERROR_RESPONSE` or `_NO_DOCUMENTS_RESPONSE` for a valid Indonesian product query
- Defect 6: `queryAllByRole('button', {name: /copy/i})` returns empty array
- Defect 7: Response text does not contain "Data Quality Notice"

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds, the fixed code produces the expected behavior.

**Pseudocode:**
```
FOR ALL input WHERE isBugCondition(input) DO
  result := fixedFunction(input)
  ASSERT expectedBehavior(result)
END FOR
```

**Specific assertions per defect:**

```
-- Defect 1
FOR ALL query WITH retrieved_documents.count >= 3 DO
  response := rag_chain_fixed.invoke(query)
  ASSERT word_count(response.answer) > 100
  ASSERT source_citation_count(response.answer) >= 1
END FOR

-- Defect 2
FOR ALL tone IN ["executive_summary", "detailed_analysis", "concise", "default"] DO
  request := ChatRequest(query="test", response_tone=tone)
  ASSERT request IS VALID (no schema error)
  response := chat_endpoint_fixed(request)
  ASSERT response.status == 200
END FOR

-- Defect 3
FOR ALL query_type IN ["simple_retrieval", "multi_step"] DO
  workflow := build_workflow_fixed(...)
  IF query_type == "simple_retrieval" THEN
    ASSERT workflow.llm_simple.temperature == 0.0
  ELSE
    ASSERT workflow.llm_complex.temperature == 0.3
  END IF
END FOR

-- Defect 4
session_id := "test-session-123"
send_request(query="first question", session_id=session_id)
result := send_request(query="second question", session_id=session_id)
ASSERT result.conversation_history.length == 2

-- Defect 5
response := chat_endpoint_fixed(query="apa saja info untuk produk Sania Botol?", language="id")
ASSERT response.answer NOT IN [_ERROR_RESPONSE, _NO_DOCUMENTS_RESPONSE_EN]
ASSERT response.answer contains product information OR graceful Indonesian no-results message

-- Defect 6
render MessageBubble(message={role:"assistant", isComplete:true, content:"test"})
ASSERT queryByRole("button", {name:/copy/i}) IS NOT NULL
ASSERT queryByRole("button", {name:/regenerate/i}) IS NOT NULL

-- Defect 7
documents := [Document(page_content="", metadata={source_type:"chunk", file_name:"bad.pdf"})]
response := rag_chain_fixed._check_data_quality(documents)
ASSERT response.length == 1
ASSERT response[0].issue_type == "empty_or_truncated_content"
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold, the fixed code produces the same result as the original code.

**Pseudocode:**
```
FOR ALL input WHERE NOT isBugCondition(input) DO
  ASSERT originalFunction(input) = fixedFunction(input)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because it generates many test cases automatically across the input domain, catches edge cases that manual unit tests might miss, and provides strong guarantees that behavior is unchanged for all non-buggy inputs.

**Test Plan**: Observe behavior on UNFIXED code first for non-buggy inputs, then write property-based tests capturing that behavior.

**Test Cases**:

1. **Retrieval Mode Preservation**: Generate random queries with `retrieval_mode` in ["local", "global", "combined"] and verify that the retrieval service returns the same result structure before and after the fix.

2. **Streaming Event Order Preservation**: Verify that the SSE stream continues to emit events in the order: token(s)  sources  metadata  done  suggestions (optional).

3. **Session Eviction Preservation**: Add 21 turns to a session and verify that only the 20 most recent turns are retained (MAX_TURNS=20 behavior unchanged).

4. **Language Selection Preservation**: Submit queries with `language="en"` and verify responses are in English; submit with `language="id"` and verify responses are in Indonesian.

5. **Error Handling Preservation**: Verify HTTP 503 is returned when LLM is not configured; verify HTTP 504 is returned when the workflow exceeds 60 seconds.

6. **Source Attribution Preservation**: Verify that `SourceAttribution` objects continue to be returned and displayed for queries that retrieve chunk-type documents.

7. **Clarification Path Preservation**: Submit an ambiguous query and verify the agent still returns `response_type="clarification"` with a clarifying question.

8. **Copy Button Absent for User Messages**: Render `MessageBubble` with `role="user"` and verify no copy or regenerate buttons are rendered (buttons are only for assistant messages).

9. **No DataQualityNotice for Clean Chunks**: Invoke `_check_data_quality` with well-formed documents and verify an empty list is returned (no notice appended).

---

### Unit Tests

- Test `_RAG_SYSTEM_PROMPT` no longer contains "Be concise and direct" (Defect 1)
- Test `_TONE_INSTRUCTIONS` map contains all four tone keys (Defect 2)
- Test `ChatRequest` accepts `response_tone` field with all valid enum values (Defect 2)
- Test `ChatRequest` rejects invalid `response_tone` values (Defect 2)
- Test `ServiceContainer` creates `llm_simple` and `llm_complex` as distinct instances (Defect 3)
- Test `AgentWorkflow.__init__` stores the injected `session_store` directly without lazy-init (Defect 4)
- Test `CustomRetriever._effective_min_score()` returns 0.15 for language='id' and 0.3 for language='en' (Defect 5)
- Test `RAGChain._check_data_quality` returns issues for empty content, missing file_name, missing file_id (Defect 7)
- Test `RAGChain._check_data_quality` returns empty list for well-formed documents (Defect 7)
- Test `MessageBubble` renders copy and regenerate buttons for completed assistant messages (Defect 6)
- Test `MessageBubble` does NOT render action buttons for user messages (Defect 6, preservation)
- Test `MessageBubble` does NOT render action buttons for streaming messages (Defect 6, preservation)
- Test copy button writes message content to clipboard (Defect 6)
- Test regenerate button calls `onRegenerate` callback (Defect 6)

---

### Property-Based Tests

- **Tone injection property**: For any `response_tone` value in the `ResponseTone` enum, the formatted `_RAG_SYSTEM_PROMPT` must contain the corresponding tone instruction string and must not contain the old "Be concise and direct" text.
- **Session store identity property**: For any sequence of N requests with the same `session_id`, the `session_store` instance used by each `AgentWorkflow` must be the same object (identity check), and `get_history(session_id)` must return all turns up to MAX_TURNS.
- **min_score language property**: For any query string and language in ["id", "en"], `CustomRetriever._effective_min_score()` must return 0.15 when language='id' and the configured `min_score` (default 0.3) when language='en'.
- **Data quality detection property**: For any list of documents where at least one chunk has `page_content` with fewer than 20 characters, `_check_data_quality` must return a non-empty list containing at least one issue with `issue_type="empty_or_truncated_content"`.
- **Preservation of retrieval modes**: For any query and retrieval_mode in ["local", "global", "combined"], the fixed `CustomRetriever` must return the same document structure as the original (same fields, same ordering logic) when no bug condition is triggered.

---

### Integration Tests

- Submit a full chat request with `response_tone="executive_summary"` and verify the response is formatted as a bullet-point summary (Defect 2)
- Submit a multi-step query and verify the synthesis step uses `llm_complex` (Defect 3)
- Submit two sequential requests with the same `session_id` and verify the second response references context from the first (Defect 4)
- Submit an Indonesian product-lookup query and verify a useful answer is returned (Defect 5)
- Render the full `ChatPlayground` with a completed assistant message and verify copy/regenerate buttons are accessible via keyboard (Defect 6)
- Submit a query that retrieves a defective chunk and verify the response includes a DataQualityNotice (Defect 7)
- Submit a query with `retrieval_mode="global"` and verify community summaries are still returned (Preservation 3.2)
- Verify the SSE stream endpoint still emits all five event types in the correct order (Preservation 3.8)
