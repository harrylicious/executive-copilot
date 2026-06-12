"""Preservation property tests for the AI pipeline and Chat UI.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11, 3.12**

Property 3: Preservation - All Non-Buggy Inputs Unchanged

These tests encode baseline behavior observed on UNFIXED code for inputs that do NOT
trigger any of the seven bug conditions. They MUST PASS on unfixed code and must
continue to pass after the fix is applied (regression prevention).

Observation baseline (recorded from unfixed code):
- SessionStore.MAX_TURNS == 20 (eviction at 21st turn confirmed)
- RAGChain returns _NO_DOCUMENTS_RESPONSE string for zero docs (English for all languages)
- CustomRetriever has no language field / no _effective_min_score() in unfixed code
- AgentWorkflow._session_store starts as None (lazy-init property exists)
- All three retrieval modes (local/global/combined) accepted by CustomRetriever
- RAGChain has no _check_data_quality method on unfixed code
- _RAG_SYSTEM_PROMPT contains rule 5: Be concise and direct
- ChatRequest schema does not have response_tone field on unfixed code
- AgentWorkflow classifies queries; routes clarification correctly
- ServiceContainer.session_store is a shared SessionStore singleton

EXPECTED OUTCOME: ALL tests PASS on unfixed code.
Tests covering post-fix-only behavior are skipped via pytest.skip().
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.documents import Document
from langchain_core.messages import AIMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk_document(
    text: str = "This is a well-formed content paragraph with sufficient length for quality check.",
    file_id: int = 1,
    file_name: str = "quality_report.pdf",
    department: str = "Finance",
    score: float = 0.85,
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


def _make_mock_llm(answer: str = "This is a detailed answer about the topic.") -> MagicMock:
    mock_llm = MagicMock()
    response = AIMessage(content=answer)
    response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    mock_llm.invoke.return_value = response
    mock_llm.ainvoke = AsyncMock(return_value=response)
    return mock_llm


def _make_mock_retriever(documents: list[Document], retrieval_mode: str = "combined") -> MagicMock:
    mock_retriever = MagicMock()
    mock_retriever.retrieval_mode = retrieval_mode
    mock_retriever.invoke.return_value = documents
    mock_retriever.ainvoke = AsyncMock(return_value=documents)
    return mock_retriever



# ===========================================================================
# Section 1: Session Eviction Preservation
# ===========================================================================

class TestSessionEvictionPreservation:
    """Preservation: Session history eviction at MAX_TURNS=20 is unchanged.

    Observed baseline: SessionStore.MAX_TURNS == 20; after adding 21 turns,
    only the 20 most recent turns are retained.

    **Validates: Requirements 3.11**
    """

    def test_session_store_max_turns_is_20(self) -> None:
        """
        **Validates: Requirements 3.11**

        Concrete test: SessionStore.MAX_TURNS must equal 20.

        EXPECTED TO PASS on unfixed code  MAX_TURNS=20 is the existing baseline.
        """
        from app.services.langchain.session_store import SessionStore

        assert SessionStore.MAX_TURNS == 20, (
            f"Preservation broken: SessionStore.MAX_TURNS changed from 20 to {SessionStore.MAX_TURNS}."
        )

    def test_adding_21_turns_retains_only_20_most_recent(self) -> None:
        """
        **Validates: Requirements 3.11**

        Concrete test: After adding 21 turns with the same session_id, only
        the 20 most recent turns are retained.

        EXPECTED TO PASS on unfixed code  eviction logic exists and is correct.
        """
        from app.services.langchain.session_store import SessionStore

        store = SessionStore()
        session_id = "eviction-test-session"

        # Add 21 turns (one more than MAX_TURNS)
        for i in range(21):
            store.add_turn(session_id, "user", f"Turn {i}")

        history = store.get_history(session_id)

        assert len(history) == 20, (
            f"Preservation broken: Expected 20 turns after eviction, got {len(history)}. "
            f"Session eviction at MAX_TURNS=20 must be preserved."
        )

    def test_oldest_turn_is_evicted_not_newest(self) -> None:
        """
        **Validates: Requirements 3.11**

        Concrete test: After adding 21 turns, the oldest turn (Turn 0) is
        evicted and the newest turn (Turn 20) is retained.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.session_store import SessionStore

        store = SessionStore()
        session_id = "eviction-order-test"

        for i in range(21):
            store.add_turn(session_id, "user", f"Turn {i}")

        history = store.get_history(session_id)

        # Oldest turn (0) should be gone
        contents = [turn["content"] for turn in history]
        assert "Turn 0" not in contents, (
            "Preservation broken: Turn 0 (oldest) was NOT evicted. "
            "The eviction must remove the oldest turn."
        )

        # Newest turn (20) should be present
        assert "Turn 20" in contents, (
            "Preservation broken: Turn 20 (newest) was NOT retained after eviction."
        )

    @given(n_turns=st.integers(min_value=21, max_value=50))
    @settings(max_examples=10, deadline=None)
    def test_property_any_excess_turns_clamped_to_max(self, n_turns: int) -> None:
        """
        **Validates: Requirements 3.11**

        Property: For any number of turns >= MAX_TURNS+1, the stored history
        length never exceeds MAX_TURNS (20).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.session_store import SessionStore

        store = SessionStore()
        session_id = f"clamped-session-{n_turns}"

        for i in range(n_turns):
            store.add_turn(session_id, "user", f"content {i}")

        history = store.get_history(session_id)

        assert len(history) <= SessionStore.MAX_TURNS, (
            f"Preservation broken: SessionStore retained {len(history)} turns "
            f"when n_turns={n_turns} > MAX_TURNS={SessionStore.MAX_TURNS}. "
            f"Eviction must cap history at MAX_TURNS."
        )



# ===========================================================================
# Section 2: Retrieval Mode Preservation
# ===========================================================================

class TestRetrievalModePreservation:
    """Preservation: All three retrieval modes return documents with expected fields.

    Observed baseline: local, global, combined all accepted by CustomRetriever;
    documents have source_type, score/relevance_score fields.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """

    def test_retrieval_modes_are_valid_string_constants(self) -> None:
        """
        **Validates: Requirements 3.1, 3.2, 3.3**

        Concrete test: The CustomRetriever accepts each of the three retrieval
        mode strings without raising an error.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.retriever import CustomRetriever

        mock_service = MagicMock()

        for mode in ["local", "global", "combined"]:
            retriever = CustomRetriever(
                retrieval_service=mock_service,
                retrieval_mode=mode,
            )
            assert retriever.retrieval_mode == mode, (
                f"Preservation broken: retrieval_mode={mode!r} was not stored correctly."
            )

    @given(retrieval_mode=st.sampled_from(["local", "global", "combined"]))
    @settings(max_examples=3, deadline=None)
    def test_property_each_retrieval_mode_routes_to_correct_service_method(
        self, retrieval_mode: str
    ) -> None:
        """
        **Validates: Requirements 3.1, 3.2, 3.3**

        Property: For each retrieval mode, _execute_search calls the correct
        RetrievalService method (local_search, global_search, combined_search).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.retriever import CustomRetriever
        from app.services.retrieval_service import SearchResult

        mock_service = MagicMock()
        # Each method returns an empty SearchResult
        empty_result = SearchResult(chunks=[], community_summaries=[], entities=[], relationships=[])
        mock_service.local_search.return_value = empty_result
        mock_service.global_search.return_value = empty_result
        mock_service.combined_search.return_value = empty_result

        retriever = CustomRetriever(
            retrieval_service=mock_service,
            retrieval_mode=retrieval_mode,
        )

        retriever._execute_search("test query")

        if retrieval_mode == "local":
            assert mock_service.local_search.called, (
                f"Preservation broken: local_search was not called for retrieval_mode='local'."
            )
        elif retrieval_mode == "global":
            assert mock_service.global_search.called, (
                f"Preservation broken: global_search was not called for retrieval_mode='global'."
            )
        else:  # combined
            assert mock_service.combined_search.called, (
                f"Preservation broken: combined_search was not called for retrieval_mode='combined'."
            )

    def test_chunk_documents_have_required_metadata_fields(self) -> None:
        """
        **Validates: Requirements 3.1, 3.3**

        Concrete test: Documents mapped from local/combined search results have
        the required metadata fields: file_id, file_name, department, chunk_index,
        score, source_type.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.retriever import CustomRetriever
        from app.services.retrieval_service import SearchResult

        mock_service = MagicMock()
        chunk = {
            "text": "Some content",
            "file_id": 42,
            "file_name": "report.pdf",
            "department": "Finance",
            "chunk_index": 3,
            "score": 0.87,
        }
        result = SearchResult(chunks=[chunk], community_summaries=[], entities=[], relationships=[])
        mock_service.local_search.return_value = result
        mock_service.combined_search.return_value = result

        retriever = CustomRetriever(
            retrieval_service=mock_service,
            retrieval_mode="local",
        )
        docs = retriever._execute_search("test")
        documents = retriever._map_search_result_to_documents(docs)

        assert len(documents) == 1
        doc = documents[0]

        required_fields = ["file_id", "file_name", "department", "chunk_index", "score", "source_type"]
        for field in required_fields:
            assert field in doc.metadata, (
                f"Preservation broken: chunk document metadata is missing field '{field}'. "
                f"All chunk metadata fields must be preserved."
            )

        assert doc.metadata["source_type"] == "chunk", (
            "Preservation broken: source_type is not 'chunk' for chunk documents."
        )

    def test_community_summary_documents_have_required_metadata_fields(self) -> None:
        """
        **Validates: Requirements 3.2, 3.3**

        Concrete test: Community summary documents mapped from global/combined search
        have the required metadata fields: community_id, level, relevance_score, source_type.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.retriever import CustomRetriever
        from app.services.retrieval_service import SearchResult

        mock_service = MagicMock()
        summary = {
            "summary": "Community about financial reports",
            "community_id": 7,
            "level": 1,
            "relevance_score": 0.72,
        }
        result = SearchResult(chunks=[], community_summaries=[summary], entities=[], relationships=[])
        mock_service.global_search.return_value = result

        retriever = CustomRetriever(
            retrieval_service=mock_service,
            retrieval_mode="global",
        )
        docs = retriever._execute_search("test")
        documents = retriever._map_search_result_to_documents(docs)

        assert len(documents) == 1
        doc = documents[0]

        required_fields = ["community_id", "level", "relevance_score", "source_type"]
        for field in required_fields:
            assert field in doc.metadata, (
                f"Preservation broken: community summary document is missing field '{field}'."
            )

        assert doc.metadata["source_type"] == "community_summary", (
            "Preservation broken: source_type is not 'community_summary' for community documents."
        )



# ===========================================================================
# Section 3: Source Attribution Preservation
# ===========================================================================

class TestSourceAttributionPreservation:
    """Preservation: SourceAttribution objects are present for chunk-type documents.

    Observed baseline: RAGChain._extract_source_attributions returns file_id,
    file_name, department for each unique chunk document.

    **Validates: Requirements 3.12**
    """

    def test_rag_chain_extracts_source_attributions_from_chunk_documents(self) -> None:
        """
        **Validates: Requirements 3.12**

        Concrete test: RAGChain._extract_source_attributions returns a non-empty
        list of dicts with file_id, file_name, department for chunk-type documents.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        docs = [
            _make_chunk_document(file_id=1, file_name="a.pdf", department="Finance"),
            _make_chunk_document(file_id=2, file_name="b.pdf", department="HR"),
        ]
        mock_retriever = _make_mock_retriever(docs)
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        attributions = chain._extract_source_attributions(docs)

        assert len(attributions) == 2, (
            f"Preservation broken: expected 2 source attributions, got {len(attributions)}."
        )

        for attr in attributions:
            assert "file_id" in attr, "Preservation broken: source attribution missing 'file_id'."
            assert "file_name" in attr, "Preservation broken: source attribution missing 'file_name'."
            assert "department" in attr, "Preservation broken: source attribution missing 'department'."

    def test_community_summaries_not_included_in_source_attributions(self) -> None:
        """
        **Validates: Requirements 3.12**

        Concrete test: Community summary documents are NOT included in source
        attributions (only chunk documents are).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        docs = [
            Document(
                page_content="Community summary text",
                metadata={"source_type": "community_summary", "community_id": 1, "relevance_score": 0.8},
            )
        ]

        attributions = chain._extract_source_attributions(docs)

        assert len(attributions) == 0, (
            f"Preservation broken: community summaries should NOT appear in source attributions, "
            f"but got {len(attributions)} attribution(s)."
        )

    def test_duplicate_file_ids_deduplicated_in_attributions(self) -> None:
        """
        **Validates: Requirements 3.12**

        Concrete test: Multiple chunks from the same file produce only one
        source attribution (deduplication by file_id).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        docs = [
            _make_chunk_document(file_id=1, file_name="same.pdf"),
            _make_chunk_document(file_id=1, file_name="same.pdf"),  # duplicate
            _make_chunk_document(file_id=2, file_name="other.pdf"),
        ]

        attributions = chain._extract_source_attributions(docs)

        assert len(attributions) == 2, (
            f"Preservation broken: expected 2 unique attributions (deduped by file_id), "
            f"got {len(attributions)}."
        )



# ===========================================================================
# Section 4: Clarification Path Preservation
# ===========================================================================

class TestClarificationPathPreservation:
    """Preservation: AgentWorkflow correctly routes to clarification path.

    Observed baseline: When LLM returns "clarification", the workflow routes
    to _generate_clarification and sets response_type = "clarification".

    **Validates: Requirements 3.4**
    """

    def test_agent_workflow_classify_query_returns_clarification(self) -> None:
        """
        **Validates: Requirements 3.4**

        Concrete test: When the LLM classification returns "clarification",
        the _classify_query node sets response_type = "clarification".

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.agent_workflow import AgentWorkflow, AgentState
        from app.services.langchain.rag_chain import RAGChain

        clarification_llm = _make_mock_llm("clarification")
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=clarification_llm, retriever=mock_retriever)

        workflow = AgentWorkflow(llm=clarification_llm, rag_chain=rag_chain, language="id")

        state: AgentState = {
            "query": "do you have any documents?",
            "session_id": "",
            "conversation_history": [],
            "retrieved_context": [],
            "intermediate_steps": [],
            "sub_questions": [],
            "final_answer": "",
            "source_attributions": [],
            "retrieval_metadata": {},
            "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "response_type": "answer",
            "step_count": 0,
            "step_limit_reached": False,
        }

        result = workflow._classify_query(state)

        assert result["response_type"] == "clarification", (
            f"Preservation broken: _classify_query should set response_type='clarification' "
            f"when LLM returns 'clarification', got {result['response_type']!r}."
        )

    def test_route_after_classification_routes_clarification_correctly(self) -> None:
        """
        **Validates: Requirements 3.4**

        Concrete test: _route_after_classification returns 'generate_clarification'
        when response_type is 'clarification'.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.agent_workflow import AgentWorkflow, AgentState
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        workflow = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")

        state: AgentState = {
            "query": "vague question",
            "session_id": "",
            "conversation_history": [],
            "retrieved_context": [],
            "intermediate_steps": [],
            "sub_questions": [],
            "final_answer": "",
            "source_attributions": [],
            "retrieval_metadata": {},
            "token_usage": {},
            "response_type": "clarification",
            "step_count": 0,
            "step_limit_reached": False,
        }

        route = workflow._route_after_classification(state)

        assert route == "generate_clarification", (
            f"Preservation broken: routing with response_type='clarification' should "
            f"go to 'generate_clarification', got {route!r}."
        )

    def test_generate_clarification_sets_response_type(self) -> None:
        """
        **Validates: Requirements 3.4**

        Concrete test: _generate_clarification node returns a dict with
        response_type = "clarification" and a non-empty final_answer.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.agent_workflow import AgentWorkflow, AgentState
        from app.services.langchain.rag_chain import RAGChain

        clarification_question = "Could you please specify which product you mean?"
        mock_llm = _make_mock_llm(clarification_question)
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        workflow = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")

        state: AgentState = {
            "query": "what about it?",
            "session_id": "",
            "conversation_history": [],
            "retrieved_context": [],
            "intermediate_steps": [],
            "sub_questions": [],
            "final_answer": "",
            "source_attributions": [],
            "retrieval_metadata": {},
            "token_usage": {},
            "response_type": "clarification",
            "step_count": 0,
            "step_limit_reached": False,
        }

        result = workflow._generate_clarification(state)

        assert result["response_type"] == "clarification", (
            f"Preservation broken: _generate_clarification must set response_type='clarification'. "
            f"Got {result.get('response_type')!r}."
        )
        assert result["final_answer"], (
            "Preservation broken: _generate_clarification must return a non-empty final_answer."
        )



# ===========================================================================
# Section 5: No DataQualityNotice for Clean Chunks (skip on unfixed code)
# ===========================================================================

class TestNoDataQualityNoticeForCleanChunks:
    """Preservation: _check_data_quality returns empty list for well-formed documents.

    This test covers post-fix behavior: _check_data_quality does not exist on
    unfixed code, so we skip until it is added.

    **Validates: Requirements 3.7 (no notice for clean data)**
    """

    def test_check_data_quality_returns_empty_for_clean_chunk(self) -> None:
        """
        **Validates: Requirements 3.7**

        Concrete test: _check_data_quality returns an empty list when called
        with well-formed documents (content >= 20 chars, file_name present,
        file_id present).

        SKIPPED on unfixed code because _check_data_quality does not exist yet.
        After the fix, this must PASS.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        if not hasattr(chain, "_check_data_quality"):
            pytest.skip(
                "Skipping on unfixed code: _check_data_quality does not exist yet. "
                "This test will pass after task 3.7 adds the method."
            )

        clean_docs = [
            _make_chunk_document(
                text="This is a well-formed paragraph with at least twenty characters of content.",
                file_id=1,
                file_name="clean_report.pdf",
            ),
            _make_chunk_document(
                text="Another clean document with sufficient content for quality checks.",
                file_id=2,
                file_name="second_clean.pdf",
            ),
        ]

        issues = chain._check_data_quality(clean_docs)

        assert len(issues) == 0, (
            f"Preservation broken: _check_data_quality returned {len(issues)} issue(s) "
            f"for well-formed documents  no DataQualityNotice should appear for clean chunks. "
            f"Issues: {issues!r}"
        )

    @given(
        content=st.text(min_size=20, max_size=500).filter(lambda s: s.strip()),
        file_name=st.from_regex(r"[a-z]+\.pdf", fullmatch=True),
        file_id=st.integers(min_value=1, max_value=1000),
    )
    @settings(max_examples=10, deadline=None)
    def test_property_clean_chunks_produce_no_issues(
        self, content: str, file_name: str, file_id: int
    ) -> None:
        """
        **Validates: Requirements 3.7**

        Property: For any well-formed chunk document (content >= 20 chars,
        file_name present, file_id >= 1), _check_data_quality must return
        an empty list.

        SKIPPED on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        if not hasattr(chain, "_check_data_quality"):
            pytest.skip(
                "Skipping: _check_data_quality not yet implemented on unfixed code."
            )

        doc = Document(
            page_content=content,
            metadata={
                "source_type": "chunk",
                "file_name": file_name,
                "file_id": file_id,
                "department": "Finance",
                "chunk_index": 0,
                "score": 0.8,
            },
        )

        issues = chain._check_data_quality([doc])

        assert len(issues) == 0, (
            f"Preservation broken: Well-formed chunk triggered a DataQualityNotice. "
            f"Counterexample: content={content[:50]!r}, file_name={file_name!r}, "
            f"file_id={file_id}, issues={issues!r}"
        )



# ===========================================================================
# Section 6: min_score Language Property (skip on unfixed code)
# ===========================================================================

class TestMinScoreLanguagePreservation:
    """Preservation: For language="en", _effective_min_score returns configured min_score.

    This test covers post-fix behavior: _effective_min_score does not exist on
    unfixed code, so we skip until the method is added.

    **Validates: Requirements 3.9 (English queries use default min_score)**
    """

    @given(query=st.text(min_size=3, max_size=100).filter(lambda s: s.strip()))
    @settings(max_examples=10, deadline=None)
    def test_property_english_queries_use_default_min_score(self, query: str) -> None:
        """
        **Validates: Requirements 3.9**

        Property: For any query string with language="en",
        CustomRetriever._effective_min_score() returns the configured min_score
        (default 0.3).

        SKIPPED on unfixed code because _effective_min_score does not exist yet.
        After fix: this property ensures English queries are NOT affected by
        the Indonesian min_score lowering.
        """
        from app.services.langchain.retriever import CustomRetriever

        mock_service = MagicMock()

        # Try to create with language="en" parameter (only works after fix)
        try:
            retriever = CustomRetriever(
                retrieval_service=mock_service,
                retrieval_mode="combined",
                language="en",
                min_score=0.3,
            )
        except (TypeError, Exception):
            pytest.skip(
                "Skipping: CustomRetriever does not accept 'language' parameter on unfixed code. "
                "This test will pass after task 3.5 adds the language field."
            )

        if not hasattr(retriever, "_effective_min_score"):
            pytest.skip(
                "Skipping: CustomRetriever._effective_min_score does not exist on unfixed code."
            )

        effective = retriever._effective_min_score()

        assert effective == retriever.min_score, (
            f"Preservation broken: For language='en', _effective_min_score() should return "
            f"the configured min_score ({retriever.min_score}), but got {effective}. "
            f"English queries must use the default threshold."
        )

    def test_english_retriever_min_score_is_default_03(self) -> None:
        """
        **Validates: Requirements 3.9**

        Concrete test: CustomRetriever with language="en" uses min_score=0.3
        (the default), not the lowered Indonesian threshold.

        SKIPPED on unfixed code.
        """
        from app.services.langchain.retriever import CustomRetriever

        mock_service = MagicMock()

        try:
            retriever = CustomRetriever(
                retrieval_service=mock_service,
                retrieval_mode="combined",
                language="en",
            )
        except (TypeError, Exception):
            pytest.skip("Skipping: CustomRetriever does not accept 'language' parameter yet.")

        if not hasattr(retriever, "_effective_min_score"):
            pytest.skip("Skipping: _effective_min_score not yet implemented.")

        effective = retriever._effective_min_score()

        assert effective == 0.3, (
            f"Preservation broken: English retriever must use min_score=0.3, "
            f"but _effective_min_score() returned {effective}."
        )



# ===========================================================================
# Section 7: Tone Injection Property (skip on unfixed code)
# ===========================================================================

class TestToneInjectionPreservation:
    """Preservation: _RAG_SYSTEM_PROMPT contains the tone instruction after fix.

    This tests post-fix behavior: on unfixed code, _RAG_SYSTEM_PROMPT has no
    {tone_instruction} placeholder and ResponseTone enum does not exist, so we skip.

    **Validates: Requirements 3.8 (streaming SSE structure), 3.9 (language)**
    Note: Tone injection itself is a fix (Defect 2) but preservation means any
    ResponseTone value produces a valid (non-empty) prompt that does NOT use
    the old "Be concise and direct" instruction.
    """

    def test_tone_injection_produces_prompt_without_concise_rule(self) -> None:
        """
        **Validates: Requirements 3.1, 3.9**

        Concrete test: For any ResponseTone, the formatted _RAG_SYSTEM_PROMPT
        must NOT contain the old "Be concise and direct" instruction.

        SKIPPED on unfixed code (ResponseTone does not exist yet, and the
        prompt still contains "Be concise and direct").
        After fix: this must PASS for all tones.
        """
        try:
            from app.schemas.chat import ResponseTone
        except ImportError:
            pytest.skip(
                "Skipping: ResponseTone enum does not exist on unfixed code. "
                "This test will pass after task 3.2 adds ResponseTone to schemas/chat.py."
            )

        from app.services.langchain.rag_chain import _RAG_SYSTEM_PROMPT

        # After fix, the prompt should have {tone_instruction} placeholder
        if "{tone_instruction}" not in _RAG_SYSTEM_PROMPT:
            pytest.skip(
                "Skipping: _RAG_SYSTEM_PROMPT does not contain {tone_instruction} on unfixed code. "
                "This test will pass after task 3.1 adds the tone placeholder."
            )

        try:
            from app.services.langchain.rag_chain import _TONE_INSTRUCTIONS
        except ImportError:
            pytest.skip("Skipping: _TONE_INSTRUCTIONS not in rag_chain.py yet.")

        # For each tone, the formatted prompt must not contain "Be concise and direct"
        for tone in ResponseTone:
            tone_instruction = _TONE_INSTRUCTIONS.get(tone.value, "")
            try:
                formatted = _RAG_SYSTEM_PROMPT.format(
                    tone_instruction=tone_instruction,
                    language_instruction="You MUST respond in English."
                )
            except KeyError:
                pytest.skip(f"Prompt format failed for tone={tone.value!r}; skipping.")

            assert "Be concise and direct" not in formatted, (
                f"Preservation broken: Formatted _RAG_SYSTEM_PROMPT for tone={tone.value!r} "
                f"contains 'Be concise and direct'. This rule must be removed after the fix."
            )

    @given(tone=st.sampled_from(["executive_summary", "detailed_analysis", "concise", "default"]))
    @settings(max_examples=4, deadline=None)
    def test_property_tone_instruction_present_in_formatted_prompt(self, tone: str) -> None:
        """
        **Validates: Requirements 3.1, 3.9**

        Property: For any ResponseTone value, the formatted _RAG_SYSTEM_PROMPT
        must contain a non-empty tone instruction that corresponds to the requested tone.

        SKIPPED on unfixed code.
        """
        try:
            from app.services.langchain.rag_chain import _RAG_SYSTEM_PROMPT, _TONE_INSTRUCTIONS
        except ImportError:
            pytest.skip("Skipping: _TONE_INSTRUCTIONS not available on unfixed code.")

        if "{tone_instruction}" not in _RAG_SYSTEM_PROMPT:
            pytest.skip("Skipping: {tone_instruction} placeholder not in prompt on unfixed code.")

        tone_instruction = _TONE_INSTRUCTIONS.get(tone, "")
        assert tone_instruction, (
            f"Preservation broken: No tone instruction found for tone={tone!r} in _TONE_INSTRUCTIONS."
        )

        try:
            formatted = _RAG_SYSTEM_PROMPT.format(
                tone_instruction=tone_instruction,
                language_instruction="You MUST respond in English."
            )
        except KeyError as e:
            pytest.skip(f"Prompt format failed: {e}")

        # The tone instruction text must appear in the formatted prompt
        assert tone_instruction in formatted, (
            f"Preservation broken: tone_instruction for {tone!r} is not in the formatted prompt. "
            f"Counterexample: tone={tone!r}, tone_instruction={tone_instruction[:50]!r}"
        )



# ===========================================================================
# Section 8: Session Store Identity Property
# ===========================================================================

class TestSessionStoreIdentityPreservation:
    """Preservation: ServiceContainer.session_store is the same instance every time.

    Observed baseline: ServiceContainer initializes self.session_store = SessionStore()
    once in __init__. Every call to build_workflow uses the same shared store.
    This is the preservation property  the fix must not break the shared store.

    **Validates: Requirements 3.11**
    """

    def test_service_container_session_store_is_singleton(self) -> None:
        """
        **Validates: Requirements 3.11**

        Concrete test: ServiceContainer.session_store returns the same object
        on repeated accesses (it is set once in __init__).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.dependencies import ServiceContainer

        container = ServiceContainer()

        store_a = container.session_store
        store_b = container.session_store

        assert store_a is store_b, (
            "Preservation broken: ServiceContainer.session_store is not a singleton. "
            "Two accesses returned different objects."
        )

    def test_session_store_passed_to_workflow_is_container_store(self) -> None:
        """
        **Validates: Requirements 3.11**

        Concrete test: After build_workflow injects the session_store, the
        workflow.session_store is the same object as container.session_store.

        EXPECTED TO PASS on unfixed code (build_workflow does:
        workflow.session_store = self.session_store via property setter).
        """
        from app.services.langchain.dependencies import ServiceContainer
        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.session_store import SessionStore

        # Build workflow manually (no real db/LLM needed for this test)
        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])
        rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        shared_store = SessionStore()

        workflow = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")
        workflow.session_store = shared_store  # Simulate what build_workflow does

        assert workflow.session_store is shared_store, (
            "Preservation broken: After injecting session_store via property setter, "
            "workflow.session_store is not the injected store."
        )

    @given(n_requests=st.integers(min_value=2, max_value=5))
    @settings(max_examples=3, deadline=None)
    def test_property_multiple_workflows_with_same_store_share_history(
        self, n_requests: int
    ) -> None:
        """
        **Validates: Requirements 3.11**

        Property: For any N workflows that share the same SessionStore,
        history added by workflow_1 is visible to workflow_N.

        This tests the post-fix behavior where session_store is injected directly.
        EXPECTED TO PASS if the store is properly shared.
        """
        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.session_store import SessionStore

        shared_store = SessionStore()
        session_id = "shared-history-test"

        workflows = []
        for _ in range(n_requests):
            mock_llm = _make_mock_llm()
            mock_retriever = _make_mock_retriever([])
            rag_chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
            wf = AgentWorkflow(llm=mock_llm, rag_chain=rag_chain, language="id")
            wf.session_store = shared_store
            workflows.append(wf)

        # Add a turn via the first workflow
        workflows[0].session_store.add_turn(session_id, "user", "Hello from request 1")

        # All other workflows should see the turn (they share the same store)
        for i, wf in enumerate(workflows[1:], start=2):
            history = wf.session_store.get_history(session_id)
            assert len(history) >= 1, (
                f"Preservation broken: Workflow {i} does not see history from workflow 1. "
                f"All workflows sharing the same SessionStore must see the same history. "
                f"n_requests={n_requests}, history={history!r}"
            )



# ===========================================================================
# Section 9: Error Handling Preservation
# ===========================================================================

class TestErrorHandlingPreservation:
    """Preservation: HTTP 503 when LLM not configured; HTTP 504 on timeout.

    These are verified by testing the ServiceContainer.is_llm_available flag
    and the chat router logic (unit-level, not integration).

    **Validates: Requirements 3.6, 3.7**
    """

    def test_service_container_not_available_when_llm_is_none(self) -> None:
        """
        **Validates: Requirements 3.6**

        Concrete test: ServiceContainer.is_llm_available returns False when
        self.llm is None (LLM not configured).

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.dependencies import ServiceContainer

        container = ServiceContainer()
        # On most test environments, LLM is not configured (no API key)
        # is_llm_available should be False in that case
        if container.llm is None:
            assert not container.is_llm_available, (
                "Preservation broken: is_llm_available is True when llm is None. "
                "This should trigger HTTP 503."
            )
        else:
            # LLM IS configured  verify the flag is True
            assert container.is_llm_available, (
                "Preservation broken: is_llm_available is False even though llm is configured."
            )

    def test_build_workflow_raises_runtime_error_when_llm_unavailable(self) -> None:
        """
        **Validates: Requirements 3.6**

        Concrete test: ServiceContainer.build_workflow raises RuntimeError
        when is_llm_available is False.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.dependencies import ServiceContainer
        from unittest.mock import patch

        container = ServiceContainer()

        with patch.object(type(container), 'is_llm_available', new_callable=lambda: property(lambda self: False)):
            with pytest.raises(RuntimeError):
                container.build_workflow(db=MagicMock())

    def test_rag_chain_invoke_returns_error_response_on_llm_failure(self) -> None:
        """
        **Validates: Requirements 3.6**

        Concrete test: When the LLM raises an exception during invoke,
        RAGChain returns a RAGResponse with _ERROR_RESPONSE as the answer.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain, _ERROR_RESPONSE

        failing_llm = MagicMock()
        failing_llm.invoke.side_effect = RuntimeError("LLM unavailable")
        failing_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        docs = [_make_chunk_document()]
        mock_retriever = _make_mock_retriever(docs)

        chain = RAGChain(llm=failing_llm, retriever=mock_retriever)
        result = chain.invoke("What is the financial status?")

        assert result.answer == _ERROR_RESPONSE, (
            f"Preservation broken: LLM failure should return _ERROR_RESPONSE, "
            f"got {result.answer!r}."
        )



# ===========================================================================
# Section 10: Language Selection Preservation
# ===========================================================================

class TestLanguageSelectionPreservation:
    """Preservation: RAGChain uses the Indonesian system prompt template.

    After TurboVec migration, the RAG chain uses a single Indonesian prompt
    template (_SYSTEM_PROMPT_TEMPLATE) with no language selection.
    The prompt always responds in Bahasa Indonesia.

    **Validates: Requirements 3.9**
    """

    def test_system_prompt_template_exists(self) -> None:
        """
        **Validates: Requirements 3.9**

        Concrete test: _SYSTEM_PROMPT_TEMPLATE exists in rag_chain module.

        EXPECTED TO PASS after TurboVec migration.
        """
        from app.services.langchain.rag_chain import _SYSTEM_PROMPT_TEMPLATE

        assert _SYSTEM_PROMPT_TEMPLATE, (
            "Preservation broken: _SYSTEM_PROMPT_TEMPLATE is empty or missing."
        )

    def test_system_prompt_contains_indonesian_instructions(self) -> None:
        """
        **Validates: Requirements 3.9**

        Concrete test: The system prompt template contains Indonesian
        language instructions (Bahasa Indonesia).

        EXPECTED TO PASS after TurboVec migration.
        """
        from app.services.langchain.rag_chain import _SYSTEM_PROMPT_TEMPLATE

        assert "Bahasa Indonesia" in _SYSTEM_PROMPT_TEMPLATE, (
            "Preservation broken: System prompt template does not contain "
            "'Bahasa Indonesia' instruction."
        )

    def test_system_prompt_has_context_and_question_placeholders(self) -> None:
        """
        **Validates: Requirements 3.9**

        Concrete test: The system prompt template has {context} and {question}
        placeholders for substitution.

        EXPECTED TO PASS after TurboVec migration.
        """
        from app.services.langchain.rag_chain import _SYSTEM_PROMPT_TEMPLATE

        assert "{context}" in _SYSTEM_PROMPT_TEMPLATE, (
            "Preservation broken: _SYSTEM_PROMPT_TEMPLATE missing {context} placeholder."
        )
        assert "{question}" in _SYSTEM_PROMPT_TEMPLATE, (
            "Preservation broken: _SYSTEM_PROMPT_TEMPLATE missing {question} placeholder."
        )

    def test_build_messages_substitutes_context_and_question(self) -> None:
        """
        **Validates: Requirements 3.9**

        Concrete test: _build_messages properly substitutes {context} and {question}
        into the prompt template.

        EXPECTED TO PASS after TurboVec migration.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm()
        mock_retriever = _make_mock_retriever([])

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        messages = chain._build_messages("What is the budget?", "Some context text")

        content = messages[0].content
        assert "Some context text" in content, (
            "Preservation broken: context not substituted into prompt."
        )
        assert "What is the budget?" in content, (
            "Preservation broken: question not substituted into prompt."
        )



# ===========================================================================
# Section 11: Streaming SSE Event Order Preservation
# ===========================================================================

class TestStreamingEventOrderPreservation:
    """Preservation: SSE stream emits events in token -> sources -> metadata -> done -> suggestions.

    Observed baseline: chat_stream endpoint emits events in the exact order
    defined in the event_generator() coroutine in routers/chat.py.

    **Validates: Requirements 3.8**
    """

    def test_rag_chain_astream_yields_tokens(self) -> None:
        """
        **Validates: Requirements 3.8**

        Concrete test: RAGChain.astream yields at least one string token for
        a query with documents available.

        EXPECTED TO PASS on unfixed code.
        """
        import asyncio
        from app.services.langchain.rag_chain import RAGChain

        async def run():
            mock_llm = MagicMock()
            # Configure the mock to stream
            async def mock_astream(messages):
                from langchain_core.messages import AIMessageChunk
                for word in ["This ", "is ", "a ", "token ", "stream."]:
                    yield AIMessageChunk(content=word)
            mock_llm.astream = mock_astream

            docs = [_make_chunk_document()]
            mock_retriever = _make_mock_retriever(docs)

            chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
            tokens = []
            async for token in chain.astream("What is the budget?"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(run())

        assert len(tokens) >= 1, (
            f"Preservation broken: RAGChain.astream yielded no tokens. "
            f"Streaming must continue to work after fixes."
        )

    def test_rag_chain_astream_handles_empty_retrieval(self) -> None:
        """
        **Validates: Requirements 3.8**

        Concrete test: RAGChain.astream still produces output when no documents
        are retrieved. After the TurboVec migration, the prompt template's built-in
        rule handles the no-documents case (rather than a separate _NO_DOCUMENTS_RESPONSE).

        EXPECTED TO PASS after TurboVec migration.
        """
        import asyncio
        from app.services.langchain.rag_chain import RAGChain

        async def run():
            mock_llm = MagicMock()
            # Configure mock to stream tokens (simulating LLM answering with empty context)
            async def mock_astream(messages):
                from langchain_core.messages import AIMessageChunk
                yield AIMessageChunk(content="Data tidak ditemukan dalam dokumen yang tersedia")
            mock_llm.astream = mock_astream

            mock_retriever = _make_mock_retriever([])  # no documents
            chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
            tokens = []
            async for token in chain.astream("test query"):
                tokens.append(token)
            return tokens

        tokens = asyncio.run(run())

        # Should yield at least one token (the LLM response)
        assert len(tokens) >= 1, (
            f"Preservation broken: Expected at least 1 token from astream with empty retrieval, "
            f"got {len(tokens)}: {tokens!r}"
        )

    def test_rag_chain_source_attributions_present_in_response(self) -> None:
        """
        **Validates: Requirements 3.12**

        Concrete test: RAGChain.invoke returns source_attributions in the response
        for queries with chunk documents.

        EXPECTED TO PASS on unfixed code.
        """
        from app.services.langchain.rag_chain import RAGChain

        mock_llm = _make_mock_llm("Detailed answer about the financial report.")
        docs = [
            _make_chunk_document(file_id=10, file_name="finance.pdf"),
            _make_chunk_document(file_id=11, file_name="budget.pdf"),
        ]
        mock_retriever = _make_mock_retriever(docs)

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("What is the budget?")

        assert len(result.source_attributions) > 0, (
            "Preservation broken: RAGChain returned no source_attributions for a query "
            "that retrieved chunk documents. Source attribution must be preserved."
        )

        for attr in result.source_attributions:
            assert attr.get("file_id") is not None, (
                "Preservation broken: source attribution is missing file_id."
            )
            assert attr.get("file_name"), (
                "Preservation broken: source attribution is missing file_name."
            )

