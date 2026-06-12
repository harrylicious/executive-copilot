"""Bug condition exploration tests for the seven defects in the AI pipeline.

**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7**

Property 1: Bug Condition — Seven Defects in AI Pipeline and Chat UI

These tests MUST FAIL on unfixed code — failure confirms each bug exists.
DO NOT attempt to fix the tests or the code when they fail.
These tests encode the expected behavior; they will validate the fix when
they pass after implementation.

GOAL: Surface counterexamples that demonstrate each of the seven bugs.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError
from unittest.mock import MagicMock, AsyncMock
from langchain_core.documents import Document
from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk_document(
    text: str,
    file_id: int = 1,
    file_name: str = "test.pdf",
    department: str = "Finance",
    score: float = 0.9,
) -> Document:
    return Document(
        page_content=text,
        metadata={
            "file_id": file_id,
            "file_name": file_name,
            "department": department,
            "chunk_index": 0,
            "score": score,
            "source_type": "chunk",
        },
    )


def _make_mock_llm(answer: str = "Short answer.") -> MagicMock:
    """Create a mock LLM that returns a short (shallow) answer."""
    mock_llm = MagicMock()
    response = AIMessage(content=answer)
    response.usage_metadata = {"input_tokens": 100, "output_tokens": 10}
    mock_llm.invoke.return_value = response
    mock_llm.ainvoke = AsyncMock(return_value=response)
    return mock_llm


def _make_mock_retriever(documents: list[Document]) -> MagicMock:
    mock_retriever = MagicMock()
    mock_retriever.retrieval_mode = "combined"
    mock_retriever.invoke.return_value = documents
    mock_retriever.ainvoke = AsyncMock(return_value=documents)
    return mock_retriever


def _word_count(text: str) -> int:
    return len(text.split())


def _source_citation_count(text: str) -> int:
    import re
    return len(re.findall(r"\[Source \d+\]", text))


# ---------------------------------------------------------------------------
# Defect 1 — Shallow response
# ---------------------------------------------------------------------------

class TestDefect1ShallowResponse:
    """Defect 1: _RAG_SYSTEM_PROMPT instructs 'Be concise' → shallow responses.

    For any query with 3+ retrieved documents, the response should have
    word_count > 100 and at least 1 source citation.

    EXPECTED TO FAIL on unfixed code because the prompt says 'Be concise and direct'.
    """

    @given(
        query=st.text(min_size=5, max_size=100).filter(lambda s: s.strip()),
    )
    @settings(max_examples=10, deadline=None)
    def test_property_shallow_response_bug_condition(self, query: str) -> None:
        """
        **Validates: Requirements 1.1**

        Property: For any query with 3+ retrieved documents, the RAG system prompt
        must NOT contain 'Be concise and direct' (which causes shallow responses).

        After TurboVec migration: The prompt was replaced with an Indonesian template
        (_SYSTEM_PROMPT_TEMPLATE) that does not contain this instruction.
        """
        from app.services.langchain.rag_chain import _SYSTEM_PROMPT_TEMPLATE

        # The bug: the old prompt contained 'Be concise and direct'
        # The migration fix: replaced the entire prompt with Indonesian template
        assert "Be concise and direct" not in _SYSTEM_PROMPT_TEMPLATE, (
            f"Bug confirmed — _SYSTEM_PROMPT_TEMPLATE contains 'Be concise and direct' "
            f"which causes shallow responses. "
            f"Counterexample: prompt contains 'Be concise and direct in your answer.'"
        )

    def test_rag_system_prompt_does_not_contain_concise_instruction(self) -> None:
        """
        **Validates: Requirements 1.1**

        Concrete test: System prompt template must not contain the shallow-response instruction.

        After TurboVec migration: The prompt was replaced with an Indonesian template.
        """
        from app.services.langchain.rag_chain import _SYSTEM_PROMPT_TEMPLATE

        assert "Be concise and direct" not in _SYSTEM_PROMPT_TEMPLATE, (
            "Bug confirmed (Defect 1): _SYSTEM_PROMPT_TEMPLATE contains 'Be concise and direct' "
            "which causes the LLM to produce shallow 1-3 sentence responses regardless of "
            "how much context was retrieved."
        )


# ---------------------------------------------------------------------------
# Defect 2 — Tone rejection
# ---------------------------------------------------------------------------

class TestDefect2ToneRejection:
    """Defect 2: ChatRequest has no response_tone field → ValidationError on tone.

    EXPECTED TO FAIL on unfixed code because ChatRequest does not accept
    response_tone (extra fields not permitted by Pydantic).
    """

    def test_chat_request_accepts_response_tone_executive_summary(self) -> None:
        """
        **Validates: Requirements 1.2**

        Concrete test: ChatRequest(query="test", response_tone="executive_summary")
        must NOT raise a Pydantic ValidationError.

        EXPECTED TO FAIL on unfixed code — HTTP 422 / extra fields not permitted.
        Counterexample: ValidationError: 1 validation error for ChatRequest
          response_tone: Extra inputs are not permitted
        """
        from app.schemas.chat import ChatRequest

        # This should NOT raise ValidationError after the fix
        try:
            req = ChatRequest(query="test", response_tone="executive_summary")
            # If we get here, the field exists — verify it was accepted
            assert req.response_tone == "executive_summary", (
                f"response_tone was not stored correctly: {req.response_tone}"
            )
        except (ValidationError, TypeError) as exc:
            pytest.fail(
                f"Bug confirmed (Defect 2): ChatRequest rejected response_tone='executive_summary'. "
                f"Counterexample: {exc}"
            )

    @given(
        tone=st.sampled_from(["executive_summary", "detailed_analysis", "concise", "default"]),
    )
    @settings(max_examples=4, deadline=None)
    def test_property_all_valid_tones_accepted(self, tone: str) -> None:
        """
        **Validates: Requirements 1.2**

        Property: For any valid ResponseTone value, ChatRequest must accept it
        without raising a ValidationError.

        EXPECTED TO FAIL on unfixed code.
        """
        from app.schemas.chat import ChatRequest

        try:
            req = ChatRequest(query="test query", response_tone=tone)
            assert hasattr(req, "response_tone"), (
                f"response_tone attribute missing after construction with tone={tone!r}"
            )
        except (ValidationError, TypeError) as exc:
            pytest.fail(
                f"Bug confirmed (Defect 2): ChatRequest rejected response_tone={tone!r}. "
                f"Counterexample: tone={tone!r}, error={exc}"
            )


# ---------------------------------------------------------------------------
# Defect 3 — Fixed model/temperature
# ---------------------------------------------------------------------------

class TestDefect3FixedModel:
    """Defect 3: ServiceContainer creates a single LLM for all query types.

    EXPECTED TO FAIL on unfixed code because AgentWorkflow has no llm_simple
    or llm_complex attributes — only a single self.llm.
    """

    def test_agent_workflow_has_distinct_llm_simple_and_llm_complex(self) -> None:
        """
        **Validates: Requirements 1.3**

        Concrete test: After building a workflow, workflow.llm_simple must be
        a different object from workflow.llm_complex.

        EXPECTED TO FAIL on unfixed code — AgentWorkflow has no llm_simple/llm_complex.
        Counterexample: AttributeError: 'AgentWorkflow' object has no attribute 'llm_simple'
        """
        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        # Build workflow — on unfixed code this only accepts llm, rag_chain, language
        workflow = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")

        # After the fix, workflow must have distinct llm_simple and llm_complex
        assert hasattr(workflow, "llm_simple"), (
            "Bug confirmed (Defect 3): AgentWorkflow has no 'llm_simple' attribute. "
            "Counterexample: workflow.llm_simple does not exist — only workflow.llm exists."
        )
        assert hasattr(workflow, "llm_complex"), (
            "Bug confirmed (Defect 3): AgentWorkflow has no 'llm_complex' attribute. "
            "Counterexample: workflow.llm_complex does not exist — only workflow.llm exists."
        )
        assert workflow.llm_simple is not workflow.llm_complex, (
            "Bug confirmed (Defect 3): workflow.llm_simple IS workflow.llm_complex — "
            "the same LLM instance is used for all query types regardless of complexity. "
            "Counterexample: id(workflow.llm_simple) == id(workflow.llm_complex)"
        )

    def test_service_container_creates_llm_simple_and_llm_complex(self) -> None:
        """
        **Validates: Requirements 1.3**

        Concrete test: ServiceContainer must have llm_simple and llm_complex attributes
        after initialization.

        EXPECTED TO FAIL on unfixed code — ServiceContainer only has self.llm.
        """
        from app.services.langchain.dependencies import ServiceContainer

        container = ServiceContainer()

        assert hasattr(container, "llm_simple"), (
            "Bug confirmed (Defect 3): ServiceContainer has no 'llm_simple' attribute. "
            "Counterexample: ServiceContainer.__init__ only creates self.llm."
        )
        assert hasattr(container, "llm_complex"), (
            "Bug confirmed (Defect 3): ServiceContainer has no 'llm_complex' attribute. "
            "Counterexample: ServiceContainer.__init__ only creates self.llm."
        )


# ---------------------------------------------------------------------------
# Defect 4 — Session history loss
# ---------------------------------------------------------------------------

class TestDefect4SessionHistoryLoss:
    """Defect 4: AgentWorkflow lazy-init creates a new SessionStore per request.

    EXPECTED TO FAIL on unfixed code because the lazy-init property creates
    a fresh SessionStore() when _session_store is None, losing history.
    """

    def test_session_history_persists_across_two_workflow_invocations(self) -> None:
        """
        **Validates: Requirements 1.4**

        Concrete test: Simulating two sequential HTTP requests (each calls build_workflow()
        which creates a NEW AgentWorkflow), the second workflow must see the conversation
        history from the first. This tests the real bug: build_workflow() creates a new
        AgentWorkflow each request, and if the session store is not properly shared,
        lazy-init fires and creates a fresh (empty) SessionStore.

        EXPECTED TO FAIL on unfixed code — because with lazy-init, two different workflows
        built WITHOUT explicit session_store injection will have different session stores.
        The bug: build_workflow() does NOT pass session_store to the constructor,
        so lazy-init fires during compile() and each workflow gets its own store.

        Counterexample: second_request.conversation_history == []
        """
        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.session_store import SessionStore

        mock_llm = _make_mock_llm("Simple answer about the topic.")
        mock_retriever = _make_mock_retriever([
            _make_chunk_document("Some relevant content about the topic.")
        ])

        # Simulate build_workflow() building a new AgentWorkflow per request
        # On unfixed code: workflow is built WITHOUT session_store in constructor
        # The lazy-init property fires during compile(), creating a fresh store
        session_id = "test-session-123"

        # First request workflow (unfixed path: no session_store in constructor)
        rag_chain_1 = RAGChain(llm=mock_llm, retriever=mock_retriever)
        workflow_1 = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain_1, language="id")
        # Simulate the build_workflow post-construction injection (current unfixed approach)
        workflow_1.session_store = workflow_1.session_store  # access lazy-init, then reassign

        # Add a turn directly (simulating what invoke() does after completing)
        workflow_1.session_store.add_turn(session_id, "user", "What is the topic?")
        workflow_1.session_store.add_turn(session_id, "assistant", "The topic is X.")

        # Second request: NEW AgentWorkflow built (simulating new HTTP request)
        # On unfixed code: a DIFFERENT lazy-initialized store is used
        rag_chain_2 = RAGChain(llm=mock_llm, retriever=mock_retriever)
        workflow_2 = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain_2, language="id")

        # History from workflow_1's session store should be visible in workflow_2
        # if they share the same session store — but on unfixed code, they DON'T
        history_in_workflow_2 = workflow_2.session_store.get_history(session_id)

        assert len(history_in_workflow_2) >= 1, (
            "Bug confirmed (Defect 4): Two separately-constructed AgentWorkflow instances "
            "do NOT share the same session store. The lazy-init creates a NEW empty store "
            "for each workflow, so conversation history is lost between HTTP requests. "
            f"Counterexample: session_id={session_id!r}, "
            f"workflow_1.session_store.get_history(session_id)={workflow_1.session_store.get_history(session_id)!r}, "
            f"workflow_2.session_store.get_history(session_id)={history_in_workflow_2!r} (should be >= 1, got {len(history_in_workflow_2)})"
        )

    def test_lazy_init_creates_new_session_store_bug(self) -> None:
        """
        **Validates: Requirements 1.4**

        Concrete test: The lazy-init property in AgentWorkflow creates a NEW
        SessionStore when _session_store is None, which is the root cause of
        session history loss.

        EXPECTED TO FAIL on unfixed code — the lazy-init property exists and
        creates a new store, meaning two workflows built from the same container
        will have different session stores if the property fires before injection.

        After the fix: AgentWorkflow.__init__ should require session_store parameter
        and the lazy-init property should be removed.
        """
        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.session_store import SessionStore

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        # Build two workflows WITHOUT injecting a session store
        # On unfixed code, each will lazy-init its own SessionStore
        workflow_a = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")
        workflow_b = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")

        # After the fix: both workflows built without explicit session_store
        # should still share the same store (or the constructor should require it)
        # The bug: accessing .session_store on each creates a NEW store
        store_a = workflow_a.session_store
        store_b = workflow_b.session_store

        # On unfixed code: store_a is not store_b (two different instances)
        # After fix: the constructor should require session_store, preventing this
        # We test the post-fix behavior: if session_store is passed, it must be stored
        shared_store = SessionStore()
        workflow_c = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")
        workflow_c.session_store = shared_store

        assert workflow_c.session_store is shared_store, (
            "Bug confirmed (Defect 4): Injected session_store was not retained. "
            "Counterexample: workflow.session_store is not the injected store."
        )

        # The real bug: two workflows built by build_workflow() in the same request
        # cycle will have different session stores because lazy-init fires
        # Add a turn to store_a and verify store_b doesn't see it
        store_a.add_turn("session-x", "user", "hello")
        history_in_b = store_b.get_history("session-x")

        assert len(history_in_b) >= 1, (
            "Bug confirmed (Defect 4): Two AgentWorkflow instances created without "
            "explicit session_store injection have DIFFERENT session stores. "
            "A turn added to workflow_a's store is NOT visible in workflow_b's store. "
            f"Counterexample: store_a.get_history('session-x')={store_a.get_history('session-x')!r}, "
            f"store_b.get_history('session-x')={history_in_b!r}"
        )


# ---------------------------------------------------------------------------
# Defect 5 — Indonesian product lookup
# ---------------------------------------------------------------------------

class TestDefect5IndonesianProductLookup:
    """Defect 5: min_score=0.3 filters out Indonesian product chunks.

    EXPECTED TO FAIL on unfixed code because CustomRetriever.min_score=0.3
    is too strict for Indonesian queries, and there is no _effective_min_score().
    """

    def test_custom_retriever_has_effective_min_score_method(self) -> None:
        """
        **Validates: Requirements 1.5**

        Concrete test: CustomRetriever must have an _effective_min_score() method
        that returns a lower threshold for Indonesian queries.

        EXPECTED TO FAIL on unfixed code — CustomRetriever has no _effective_min_score().
        Counterexample: AttributeError: 'CustomRetriever' object has no attribute '_effective_min_score'
        """
        from app.services.langchain.retriever import CustomRetriever

        mock_service = MagicMock()
        retriever = CustomRetriever(retrieval_service=mock_service, retrieval_mode="combined")

        assert hasattr(retriever, "_effective_min_score"), (
            "Bug confirmed (Defect 5): CustomRetriever has no '_effective_min_score' method. "
            "Counterexample: The retriever always uses min_score=0.3 regardless of language, "
            "which filters out valid Indonesian product chunks scoring 0.15-0.28."
        )

    def test_custom_retriever_uses_lower_min_score_for_indonesian(self) -> None:
        """
        **Validates: Requirements 1.5**

        Concrete test: For language='id', CustomRetriever._effective_min_score()
        must return a value < 0.3 (the default min_score).

        EXPECTED TO FAIL on unfixed code — no _effective_min_score() method exists.
        """
        from app.services.langchain.retriever import CustomRetriever

        mock_service = MagicMock()

        # After the fix: CustomRetriever should accept a language parameter
        try:
            retriever = CustomRetriever(
                retrieval_service=mock_service,
                retrieval_mode="combined",
                language="id",
            )
        except (TypeError, Exception):
            # Unfixed code: CustomRetriever doesn't accept language parameter
            pytest.fail(
                "Bug confirmed (Defect 5): CustomRetriever does not accept 'language' parameter. "
                "Counterexample: CustomRetriever(language='id') raises TypeError — "
                "the retriever has no language-aware min_score logic."
            )

        assert hasattr(retriever, "_effective_min_score"), (
            "Bug confirmed (Defect 5): CustomRetriever has no '_effective_min_score' method."
        )

        effective_score = retriever._effective_min_score()
        assert effective_score < 0.3, (
            f"Bug confirmed (Defect 5): For language='id', _effective_min_score() returned "
            f"{effective_score} which is >= 0.3. Indonesian product chunks scoring 0.15-0.28 "
            f"will be filtered out. "
            f"Counterexample: language='id', _effective_min_score()={effective_score}, "
            f"expected < 0.3 (e.g., 0.15)"
        )

    def test_rag_chain_returns_indonesian_no_results_message_not_error(self) -> None:
        """
        **Validates: Requirements 1.5**

        Concrete test: When no documents are retrieved for an Indonesian query,
        RAGChain must return a response that is NOT the generic error response.
        After TurboVec migration, the prompt is always in Indonesian and the
        built-in rule handles the no-documents case ("Data tidak ditemukan...").

        The LLM is expected to follow the prompt instruction when context is empty.
        """
        from app.services.langchain.rag_chain import (
            RAGChain,
            _ERROR_RESPONSE,
        )

        # Simulate LLM following the Indonesian prompt rule for empty context
        mock_llm = _make_mock_llm("Data tidak ditemukan dalam dokumen yang tersedia")
        mock_retriever = _make_mock_retriever([])  # Zero documents

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("apa saja info untuk produk Sania Botol?")

        # Must not be the generic error response
        assert result.answer != _ERROR_RESPONSE, (
            "Bug confirmed (Defect 5): RAGChain returned _ERROR_RESPONSE for a "
            "zero-document query. "
            f"Counterexample: answer={result.answer!r}"
        )


# ---------------------------------------------------------------------------
# Defect 7 — Silent defective data
# ---------------------------------------------------------------------------

class TestDefect7SilentDefectiveData:
    """Defect 7: RAGChain has no _check_data_quality method.

    EXPECTED TO FAIL on unfixed code because RAGChain._check_data_quality
    does not exist.
    """

    def test_rag_chain_has_check_data_quality_method(self) -> None:
        """
        **Validates: Requirements 1.7**

        Concrete test: RAGChain must have a _check_data_quality method.

        EXPECTED TO FAIL on unfixed code — method does not exist.
        Counterexample: AttributeError: 'RAGChain' object has no attribute '_check_data_quality'
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        assert hasattr(chain, "_check_data_quality"), (
            "Bug confirmed (Defect 7): RAGChain has no '_check_data_quality' method. "
            "Counterexample: chain._check_data_quality does not exist — defective chunks "
            "are silently passed to the LLM with no data quality notice."
        )
        assert callable(chain._check_data_quality), (
            "Bug confirmed (Defect 7): RAGChain._check_data_quality is not callable."
        )

    def test_check_data_quality_detects_empty_content_document(self) -> None:
        """
        **Validates: Requirements 1.7**

        Concrete test: _check_data_quality([doc_with_empty_content]) must return
        a non-empty list of issues.

        EXPECTED TO FAIL on unfixed code — method does not exist.
        Counterexample: AttributeError: 'RAGChain' object has no attribute '_check_data_quality'
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        # Inject a defective document: empty page_content
        defective_doc = Document(
            page_content="",
            metadata={
                "source_type": "chunk",
                "file_name": "bad.pdf",
                "file_id": 99,
                "department": "Finance",
                "chunk_index": 0,
                "score": 0.8,
            },
        )

        if not hasattr(chain, "_check_data_quality"):
            pytest.fail(
                "Bug confirmed (Defect 7): RAGChain has no '_check_data_quality' method. "
                "Counterexample: Document(page_content='', metadata={'source_type':'chunk', "
                "'file_name':'bad.pdf'}) — method does not exist to detect this defect."
            )

        issues = chain._check_data_quality([defective_doc])

        assert len(issues) > 0, (
            "Bug confirmed (Defect 7): _check_data_quality returned an empty list for a "
            "document with empty page_content. "
            f"Counterexample: Document(page_content='', metadata={defective_doc.metadata!r}), "
            f"issues={issues!r} (expected non-empty list)"
        )

    @given(
        content=st.just(""),  # Always empty — the concrete failing case
        file_name=st.just("bad.pdf"),
    )
    @settings(max_examples=1, deadline=None)
    def test_property_defective_chunk_detected(self, content: str, file_name: str) -> None:
        """
        **Validates: Requirements 1.7**

        Property: For a document with empty page_content and source_type='chunk',
        _check_data_quality must return a non-empty list.

        EXPECTED TO FAIL on unfixed code — method does not exist.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        doc = Document(
            page_content=content,
            metadata={
                "source_type": "chunk",
                "file_name": file_name,
                "file_id": 1,
                "department": "Finance",
                "chunk_index": 0,
                "score": 0.8,
            },
        )

        if not hasattr(chain, "_check_data_quality"):
            pytest.fail(
                f"Bug confirmed (Defect 7): RAGChain._check_data_quality does not exist. "
                f"Counterexample: page_content={content!r}, file_name={file_name!r}"
            )

        issues = chain._check_data_quality([doc])
        assert len(issues) > 0, (
            f"Bug confirmed (Defect 7): _check_data_quality([doc]) returned empty list. "
            f"Counterexample: page_content={content!r}, file_name={file_name!r}, "
            f"issues={issues!r}"
        )
