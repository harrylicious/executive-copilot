# Implementation Plan

- [x] 1. Write bug condition exploration tests (BEFORE implementing any fix)
  - **Property 1: Bug Condition** - Seven Defects in AI Pipeline and Chat UI
  - **CRITICAL**: These tests MUST FAIL on unfixed code — failure confirms each bug exists
  - **DO NOT attempt to fix the tests or the code when they fail**
  - **NOTE**: These tests encode the expected behavior — they will validate the fix when they pass after implementation
  - **GOAL**: Surface counterexamples that demonstrate each of the seven bugs
  - **Scoped PBT Approach**: For deterministic bugs (defects 2, 3, 4, 5, 6, 7), scope each property to the concrete failing case(s) to ensure reproducibility
  - **Backend tests** (Hypothesis, `pytest`): create `eaip-layer1/backend/tests/test_bug_condition.py`
    - Defect 1 — Shallow response: for any query with 3+ retrieved documents, assert `word_count(response.answer) > 100` and `source_citation_count >= 1`; run against unfixed `_RAG_SYSTEM_PROMPT` — expect FAIL (response is 1-3 sentences)
    - Defect 2 — Tone rejection: assert `ChatRequest(query="test", response_tone="executive_summary")` does not raise a Pydantic `ValidationError`; run against unfixed schema — expect FAIL (HTTP 422 / extra fields not permitted)
    - Defect 3 — Fixed model: build workflow, classify a `multi_step` query, assert `workflow.llm_simple is not workflow.llm_complex`; run against unfixed `ServiceContainer` — expect FAIL (`workflow.llm is workflow.rag_chain.llm` is True)
    - Defect 4 — Session history loss: send two sequential requests with `session_id="test-session-123"`, assert second request's `conversation_history` has length ≥ 1; run against unfixed lazy-init — expect FAIL (`conversation_history == []`)
    - Defect 5 — Indonesian product lookup: submit `query="apa saja info untuk produk Sania Botol?"` with `language="id"`, assert response is not `_ERROR_RESPONSE` and not empty; run against unfixed `min_score=0.3` — expect FAIL (error or empty result)
    - Defect 7 — Silent defective data: inject `Document(page_content="", metadata={"source_type":"chunk","file_name":"bad.pdf"})`, assert `_check_data_quality([doc])` returns a non-empty list; run against unfixed `RAGChain` — expect FAIL (method does not exist)
  - **Frontend tests** (Jest/RTL): create `eaip-layer1/frontend/src/components/Chat/__tests__/MessageBubble.bug.test.tsx`
    - Defect 6 — Missing action buttons: render `<MessageBubble message={{role:"assistant", isComplete:true, content:"test"}} />`, assert `queryByRole("button", {name:/copy/i})` is not null and `queryByRole("button", {name:/regenerate/i})` is not null; run against unfixed component — expect FAIL (no buttons rendered)
  - Run all tests on UNFIXED code
  - **EXPECTED OUTCOME**: All seven sub-tests FAIL (this is correct — it proves each bug exists)
  - Document counterexamples found (e.g., "Defect 1: response='Sania adalah produk.' — only 4 words"; "Defect 2: ValidationError extra fields not permitted"; "Defect 6: queryAllByRole returns []")
  - Mark task complete when tests are written, run, and failures are documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 2. Write preservation property tests (BEFORE implementing any fix)
  - **Property 2: Preservation** - All Non-Buggy Inputs Unchanged
  - **IMPORTANT**: Follow observation-first methodology — observe UNFIXED code behavior for non-buggy inputs first, then encode as properties
  - **Backend tests** (Hypothesis, `pytest`): create `eaip-layer1/backend/tests/test_preservation.py`
    - Retrieval mode preservation: for any `retrieval_mode` in `["local", "global", "combined"]` with a non-Indonesian query, assert the retrieval service returns the same document structure (fields, ordering logic) as observed on unfixed code
    - Session eviction preservation: add 21 turns to a session, assert only 20 most recent turns are retained (`MAX_TURNS=20` unchanged)
    - Language selection preservation: for `language="en"` queries, assert response is in English; for `language="id"` non-product queries, assert response is in Indonesian
    - Error handling preservation: assert HTTP 503 when LLM is not configured; assert HTTP 504 when workflow exceeds 60 seconds
    - Source attribution preservation: for queries retrieving chunk-type documents, assert `SourceAttribution` objects are present in the response
    - Clarification path preservation: submit an ambiguous query, assert `response_type == "clarification"` with a clarifying question
    - No DataQualityNotice for clean chunks: invoke `_check_data_quality` with well-formed documents (content ≥ 20 chars, file_name present, file_id present), assert empty list returned
    - min_score language property: for any query string and `language="en"`, assert `CustomRetriever._effective_min_score()` returns the configured `min_score` (0.3 default)
    - Tone injection property: for any `response_tone` in ` n` e n;'
    unum, assert formatted `_RAG_SYSTEM_PROMPT` contains the corresponding tone instruction and does NOT contain "B'e concise and direct"
    "'
    
    - Session store identity property: for any sequence of N requests with the same `session_id`, assert the `session_store` instance used by each `AgentWorkflow` is the same object
  - **Frontend tests** (Jest/RTL): add to `eaip-layer1/frontend/src/components/Chat/__tests__/MessageBubble.preservation.test.tsx`
    - Copy button absent for user messages: render `<MessageBubble message={{role:"user", content:"hello"}} />`, assert no copy or regenerate buttons are rendered
    - No action buttons for streaming messages: render with `isStreaming:true`, assert no action buttons are rendered
    - Streaming event order preservation: verify SSE stream continues to emit `token → sources → metadata → done → suggestions` in order
  - Observe behavior on UNFIXED code for all non-buggy inputs and record baseline
  - Run tests on UNFIXED code
  - **EXPECTED OUTCOME**: All preservation tests PASS (this confirms baseline behavior to preserve)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

- [x] 3. Fix all seven defects

  - [x] 3.1 Fix Defect 1 — Replace shallow-response system prompt in `rag_chain.py`
    - In `app/services/langchain/rag_chain.py`, replace rule 5 `"Be concise and direct in your answer."` with the thorough-response instruction: `"Provide a thorough, well-structured answer that fully synthesizes all relevant information from the context. Use headings, bullet points, or numbered lists where appropriate to improve readability for an executive audience."`
    - Add placeholder `{tone_instruction}` as rule 6 and shift `{language_instruction}` to rule 7
    - Update the prompt format call in `_build_messages` to supply `tone_instruction`
    - _Bug_Condition: isBugCondition(input) where `_RAG_SYSTEM_PROMPT` contains 'Be concise and direct'_
    - _Expected_Behavior: `word_count(response.answer) > 100` and `source_citation_count >= 1` for queries with 3+ retrieved documents_
    - _Preservation: All retrieval modes, streaming, language selection, and source attribution behavior unchanged_
    - _Requirements: 2.1, 3.1, 3.2, 3.3, 3.8, 3.9, 3.12_

  - [x] 3.2 Fix Defect 2 — Add `ResponseTone` enum and `response_tone` field across the stack
    - In `app/schemas/chat.py`: add `ResponseTone(str, Enum)` with values `executive_summary`, `detailed_analysis`, `concise`, `default`; add `response_tone: ResponseTone = ResponseTone.default` to `ChatRequest`
    - In `app/services/langchain/rag_chain.py`: add `_TONE_INSTRUCTIONS` dict; update `RAGChain.__init__` to accept `response_tone: str = "default"`; inject tone instruction in `_build_messages`
    - In `app/services/langchain/dependencies.py`: add `response_tone: str = "default"` parameter to `build_workflow` and `build_rag_chain`; forward to `RAGChain`
    - In `app/routers/chat.py`: pass `response_tone=body.response_tone.value` to `build_workflow` and `build_rag_chain`
    - In `frontend/src/types/index.ts`: add `ResponseTone` type and `responseTone?: ResponseTone` to `ChatRequest` and `ChatConfig` interfaces
    - _Bug_Condition: isBugCondition(input) where `input.response_tone IS NULL` (field does not exist)_
    - _Expected_Behavior: `ChatRequest(query="test", response_tone="executive_summary")` is valid; response applies the requested tone style_
    - _Preservation: Requests without `response_tone` continue to work with `default` tone; all existing schema fields unchanged_
    - _Requirements: 2.2, 3.1, 3.2, 3.3, 3.8, 3.9_

  - [x] 3.3 Fix Defect 3 — Add adaptive LLM selection in `dependencies.py` and `agent_workflow.py`
    - In `app/services/langchain/dependencies.py`: add `llm_complex_model` and `llm_complex_temperature` to `LangChainSettings`; add `_create_llm_simple()` (temperature=0.0) and `_create_llm_complex()` (model from `KB_LLM_COMPLEX_MODEL`, temperature from `KB_LLM_COMPLEX_TEMPERATURE` defaulting to 0.3) factory methods; instantiate `self.llm_simple` and `self.llm_complex` in `ServiceContainer.__init__`; pass both to `AgentWorkflow` via `build_workflow`
    - In `app/services/langchain/agent_workflow.py`: update `__init__` to accept `llm_simple=None` and `llm_complex=None`; use `self.llm_complex` in `_decompose_query` and `_synthesize_answer`; use `self.llm_simple` for simple retrieval path
    - _Bug_Condition: isBugCondition(input) where `llm.model == settings.llm_model` and `llm.temperature == settings.llm_temperature` for all query types_
    - _Expected_Behavior: `workflow.llm_simple.temperature == 0.0` for simple retrieval; `workflow.llm_complex.temperature == 0.3` for multi-step_
    - _Preservation: Classification and clarification paths continue to use `self.llm`; HTTP 503 still returned when LLM not configured_
    - _Requirements: 2.3, 3.4, 3.5, 3.6_

  - [x] 3.4 Fix Defect 4 — Remove lazy-init; inject `session_store` directly in `AgentWorkflow`
    - In `app/services/langchain/agent_workflow.py`: remove `self._session_store = None` and the `session_store` property with lazy-init; update `__init__` to require `session_store` parameter and assign `self.session_store = session_store` directly; fall back to `SessionStore()` only if `None` is passed
    - In `app/services/langchain/dependencies.py`: update `build_workflow` to pass `session_store=self.session_store` as a constructor argument (not a post-construction assignment)
    - _Bug_Condition: isBugCondition(input) where `AgentWorkflow._session_store IS None` (lazy-init creates new store per request)_
    - _Expected_Behavior: second request with same `session_id` sees `conversation_history` with first turn_
    - _Preservation: Session eviction at 20 turns unchanged; requests without `session_id` unaffected_
    - _Requirements: 2.4, 3.11_

  - [x] 3.5 Fix Defect 5 — Lower `min_score` for Indonesian queries and add graceful fallback
    - In `app/services/langchain/retriever.py`: add `language: str = "id"` field to `CustomRetriever`; add `_INDONESIAN_MIN_SCORE: ClassVar[float] = 0.15`; add `_effective_min_score()` method returning 0.15 for `language="id"` and `self.min_score` otherwise; replace `self.min_score` with `self._effective_min_score()` in `_execute_search`
    - In `app/services/langchain/rag_chain.py`: add `_NO_DOCUMENTS_RESPONSE_ID` localized message; when `documents` is empty and `language == "id"`, return the Indonesian no-results message instead of the generic error
    - Update `ServiceContainer.build_workflow` and `build_rag_chain` to pass `language` to `CustomRetriever`
    - _Bug_Condition: isBugCondition(input) where `input.language == 'id'` and `isProductLookupQuery(input.query)` and `retriever.min_score >= 0.3`_
    - _Expected_Behavior: response is not `_ERROR_RESPONSE`; contains product information or graceful Indonesian no-results message_
    - _Preservation: English queries continue to use `min_score=0.3`; all three retrieval modes unaffected; non-product Indonesian queries unaffected_
    - _Requirements: 2.5, 3.1, 3.2, 3.3, 3.9_

  - [x] 3.6 Fix Defect 6 — Add copy-to-clipboard and regenerate buttons to `MessageBubble.tsx`
    - In `frontend/src/components/Chat/MessageBubble.tsx`: add `onRegenerate?: () => void` to `MessageBubbleProps`; add `showActions` and `copied` state; add `handleCopy` async callback using `navigator.clipboard.writeText`; render action button group (copy + regenerate) only for completed, non-streaming assistant messages; wrap assistant bubble with `onMouseEnter`/`onMouseLeave` and `onFocus`/`onBlur` handlers; import `Copy`, `Check`, `RefreshCw` from `lucide-react`; add `role="toolbar"` and `aria-label` for accessibility
    - In `frontend/src/components/Chat/MessageList.tsx`: pass `onRegenerate` callback to each `MessageBubble` for assistant messages; callback re-submits the preceding user message's content as a new query
    - _Bug_Condition: isBugCondition(input) where `input.messageRole == 'assistant'` and `MessageBubble` renders no copy or regenerate button_
    - _Expected_Behavior: `queryByRole("button", {name:/copy/i})` is not null; `queryByRole("button", {name:/regenerate/i})` is not null for completed assistant messages_
    - _Preservation: No action buttons rendered for user messages or streaming messages; follow-up suggestion clicks still submit as new queries_
    - _Requirements: 2.6, 3.10, 3.12_

  - [x] 3.7 Fix Defect 7 — Add `_check_data_quality` method to `RAGChain`
    - In `app/services/langchain/rag_chain.py`: add `_check_data_quality(documents: list[Document]) -> list[dict]` method that scans chunk-type documents for: empty/near-empty `page_content` (< 20 chars), missing `file_name` in metadata, missing/zero `file_id` in metadata; returns list of issue dicts with keys `source_number`, `file_name`, `issue_type`, `recommendation`
    - Call `_check_data_quality` in both `invoke` and `ainvoke` after document truncation; if issues found, append a `DataQualityNotice` section to the LLM answer
    - _Bug_Condition: isBugCondition(input) where `EXISTS chunk IN input.documents WHERE isDefectiveChunk(chunk)` and response contains no DataQualityNotice_
    - _Expected_Behavior: `_check_data_quality([doc_with_empty_content])` returns non-empty list with `issue_type="empty_or_truncated_content"`; response includes "Data Quality Notice" section_
    - _Preservation: `_check_data_quality` returns empty list for well-formed documents; no notice appended for clean retrieval results_
    - _Requirements: 2.7, 3.1, 3.2, 3.3_

  - [x] 3.8 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Seven Defects Resolved
    - **IMPORTANT**: Re-run the SAME tests from task 1 — do NOT write new tests
    - The tests from task 1 encode the expected behavior for all seven defects
    - When these tests pass, it confirms the expected behavior is satisfied for each defect
    - Run `eaip-layer1/backend/tests/test_bug_condition.py` and `eaip-layer1/frontend/src/components/Chat/__tests__/MessageBubble.bug.test.tsx`
    - **EXPECTED OUTCOME**: All seven sub-tests PASS (confirms all bugs are fixed)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [x] 3.9 Verify preservation tests still pass
    - **Property 2: Preservation** - All Non-Buggy Inputs Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run `eaip-layer1/backend/tests/test_preservation.py` and `eaip-layer1/frontend/src/components/Chat/__tests__/MessageBubble.preservation.test.tsx`
    - **EXPECTED OUTCOME**: All preservation tests PASS (confirms no regressions)
    - Confirm all retrieval modes, streaming, session eviction, language selection, error handling, and source attribution behavior is unchanged
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12_

- [ ] 4. Checkpoint — Ensure all tests pass
  - Run the full backend test suite: `pytest eaip-layer1/backend/tests/ -v`
  - Run the full frontend test suite: `npm test --run` (or `jest --passWithNoTests`) in `eaip-layer1/frontend`
  - Ensure all seven bug condition tests pass (task 3.8)
  - Ensure all preservation tests pass (task 3.9)
  - Ensure no new type errors: run `mypy app/` for backend and `tsc --noEmit` for frontend
  - Ask the user if any questions arise before closing the spec
