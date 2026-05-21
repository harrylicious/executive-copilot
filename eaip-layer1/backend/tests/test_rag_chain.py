"""Unit tests for RAGChain implementation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from app.services.langchain.rag_chain import RAGChain, RAGResponse, _NO_DOCUMENTS_RESPONSE, _ERROR_RESPONSE


def _make_chunk_document(text: str, file_id: int, file_name: str, department: str, score: float, chunk_index: int = 0) -> Document:
    """Helper to create a chunk-type Document."""
    return Document(
        page_content=text,
        metadata={
            "file_id": file_id,
            "file_name": file_name,
            "department": department,
            "chunk_index": chunk_index,
            "score": score,
            "source_type": "chunk",
        },
    )


def _make_community_document(text: str, community_id: int, relevance_score: float) -> Document:
    """Helper to create a community_summary-type Document."""
    return Document(
        page_content=text,
        metadata={
            "community_id": community_id,
            "level": 1,
            "relevance_score": relevance_score,
            "source_type": "community_summary",
        },
    )


def _make_mock_llm(answer: str = "Test answer", usage_metadata=None):
    """Create a mock LLM that returns a predictable response."""
    mock_llm = MagicMock()
    response = AIMessage(content=answer)
    if usage_metadata:
        response.usage_metadata = usage_metadata
    else:
        response.usage_metadata = {"input_tokens": 100, "output_tokens": 50}
    mock_llm.invoke.return_value = response
    mock_llm.ainvoke = AsyncMock(return_value=response)
    return mock_llm


def _make_mock_retriever(documents: list[Document]):
    """Create a mock retriever that returns given documents."""
    mock_retriever = MagicMock()
    mock_retriever.retrieval_mode = "combined"
    mock_retriever.invoke.return_value = documents
    mock_retriever.ainvoke = AsyncMock(return_value=documents)
    return mock_retriever


class TestRAGResponse:
    """Tests for the RAGResponse dataclass."""

    def test_default_values(self):
        response = RAGResponse()
        assert response.answer == ""
        assert response.source_attributions == []
        assert response.retrieval_metadata == {}
        assert response.token_usage == {}

    def test_custom_values(self):
        response = RAGResponse(
            answer="Hello",
            source_attributions=[{"file_id": 1, "file_name": "test.pdf", "department": "HR"}],
            retrieval_metadata={"retrieval_mode": "combined", "documents_retrieved": 3, "query_time_ms": 100},
            token_usage={"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        )
        assert response.answer == "Hello"
        assert len(response.source_attributions) == 1
        assert response.retrieval_metadata["documents_retrieved"] == 3


class TestRAGChainInvoke:
    """Tests for RAGChain.invoke method."""

    def test_invoke_returns_structured_response(self):
        docs = [
            _make_chunk_document("Policy content here", 1, "policy.pdf", "HR", 0.9),
            _make_chunk_document("Budget info here", 2, "budget.xlsx", "Finance", 0.8),
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm("Based on the policy [Source 1], the answer is yes.")

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("What is the policy?")

        assert isinstance(result, RAGResponse)
        assert result.answer == "Based on the policy [Source 1], the answer is yes."
        assert result.retrieval_metadata["documents_retrieved"] == 2
        assert result.retrieval_metadata["retrieval_mode"] == "combined"
        assert result.retrieval_metadata["query_time_ms"] >= 0

    def test_invoke_zero_documents_returns_no_info_message(self):
        mock_retriever = _make_mock_retriever([])
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("Unknown topic?")

        assert result.answer == _NO_DOCUMENTS_RESPONSE
        assert result.source_attributions == []
        assert result.retrieval_metadata["documents_retrieved"] == 0
        # LLM should NOT be called when no documents
        mock_llm.invoke.assert_not_called()

    def test_invoke_llm_failure_returns_error(self):
        docs = [_make_chunk_document("Some text", 1, "file.pdf", "IT", 0.9)]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = MagicMock()
        mock_llm.invoke.side_effect = RuntimeError("LLM connection failed")

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("What is this?")

        assert result.answer == _ERROR_RESPONSE
        assert result.source_attributions == []

    def test_invoke_retriever_failure_returns_error(self):
        mock_retriever = MagicMock()
        mock_retriever.retrieval_mode = "combined"
        mock_retriever.invoke.side_effect = RuntimeError("DB connection lost")
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("What is this?")

        assert result.answer == _ERROR_RESPONSE

    def test_source_attributions_only_include_chunks(self):
        docs = [
            _make_chunk_document("Chunk text", 1, "report.pdf", "Legal", 0.9),
            _make_community_document("Community summary", 10, 0.8),
            _make_chunk_document("Another chunk", 2, "memo.docx", "HR", 0.7),
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm("Answer text")

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("Question?")

        # Only chunk documents should appear in attributions
        assert len(result.source_attributions) == 2
        file_ids = [a["file_id"] for a in result.source_attributions]
        assert 1 in file_ids
        assert 2 in file_ids

    def test_source_attributions_deduplicated_by_file_id(self):
        docs = [
            _make_chunk_document("Chunk 1", 1, "report.pdf", "Legal", 0.9, chunk_index=0),
            _make_chunk_document("Chunk 2", 1, "report.pdf", "Legal", 0.8, chunk_index=1),
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm("Answer")

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain.invoke("Question?")

        # Same file_id should only appear once
        assert len(result.source_attributions) == 1
        assert result.source_attributions[0]["file_id"] == 1


class TestRAGChainTruncateContext:
    """Tests for RAGChain._truncate_context method."""

    def test_no_truncation_when_under_limit(self):
        docs = [
            _make_chunk_document("Short text", 1, "a.pdf", "HR", 0.9),
            _make_chunk_document("Another short", 2, "b.pdf", "IT", 0.8),
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever, max_context_tokens=4000)
        result = chain._truncate_context(docs, 4000)

        assert len(result) == 2

    def test_truncation_removes_lowest_scored_first(self):
        # Create documents with varying scores and sizes
        docs = [
            _make_chunk_document("A " * 500, 1, "a.pdf", "HR", 0.9),  # High score
            _make_chunk_document("B " * 500, 2, "b.pdf", "IT", 0.3),  # Low score
            _make_chunk_document("C " * 500, 3, "c.pdf", "Legal", 0.7),  # Medium score
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        # Set a token limit that can only fit ~2 documents
        # Each doc is ~500 tokens, so limit to 1100 should remove one
        result = chain._truncate_context(docs, 1100)

        # The lowest-scored doc (score=0.3, file_id=2) should be removed first
        remaining_ids = [d.metadata["file_id"] for d in result]
        assert 2 not in remaining_ids
        assert len(result) == 2

    def test_truncation_handles_community_summaries(self):
        docs = [
            _make_chunk_document("Chunk text " * 50, 1, "a.pdf", "HR", 0.9),
            _make_community_document("Summary " * 50, 10, 0.2),  # Low relevance
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)

        # Limit that can fit the chunk (101 tokens) but not both (152 total)
        result = chain._truncate_context(docs, 110)

        # Community summary with lower score should be removed first
        assert len(result) == 1
        assert result[0].metadata["source_type"] == "chunk"

    def test_truncation_returns_empty_if_single_doc_exceeds_limit(self):
        docs = [
            _make_chunk_document("Word " * 5000, 1, "a.pdf", "HR", 0.9),
        ]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = chain._truncate_context(docs, 10)

        # If even the highest-scored doc exceeds the limit, result is empty
        assert len(result) == 0


class TestRAGChainAsync:
    """Tests for RAGChain async methods."""

    @pytest.mark.asyncio
    async def test_ainvoke_returns_structured_response(self):
        docs = [_make_chunk_document("Content", 1, "file.pdf", "HR", 0.9)]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = _make_mock_llm("Async answer")

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = await chain.ainvoke("Question?")

        assert isinstance(result, RAGResponse)
        assert result.answer == "Async answer"
        assert result.retrieval_metadata["documents_retrieved"] == 1

    @pytest.mark.asyncio
    async def test_ainvoke_zero_documents(self):
        mock_retriever = _make_mock_retriever([])
        mock_llm = _make_mock_llm()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = await chain.ainvoke("Unknown?")

        assert result.answer == _NO_DOCUMENTS_RESPONSE
        mock_llm.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_ainvoke_llm_failure(self):
        docs = [_make_chunk_document("Text", 1, "f.pdf", "IT", 0.9)]
        mock_retriever = _make_mock_retriever(docs)
        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM error"))

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        result = await chain.ainvoke("Question?")

        assert result.answer == _ERROR_RESPONSE

    @pytest.mark.asyncio
    async def test_astream_yields_tokens(self):
        docs = [_make_chunk_document("Content", 1, "file.pdf", "HR", 0.9)]
        mock_retriever = _make_mock_retriever(docs)

        # Mock streaming LLM
        mock_llm = MagicMock()
        chunks = [
            MagicMock(content="Hello"),
            MagicMock(content=" world"),
            MagicMock(content="!"),
        ]

        async def mock_astream(messages):
            for chunk in chunks:
                yield chunk

        mock_llm.astream = mock_astream

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        tokens = []
        async for token in chain.astream("Question?"):
            tokens.append(token)

        assert tokens == ["Hello", " world", "!"]

    @pytest.mark.asyncio
    async def test_astream_zero_documents(self):
        mock_retriever = _make_mock_retriever([])
        mock_llm = MagicMock()

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        tokens = []
        async for token in chain.astream("Unknown?"):
            tokens.append(token)

        assert tokens == [_NO_DOCUMENTS_RESPONSE]

    @pytest.mark.asyncio
    async def test_astream_llm_failure(self):
        docs = [_make_chunk_document("Text", 1, "f.pdf", "IT", 0.9)]
        mock_retriever = _make_mock_retriever(docs)

        mock_llm = MagicMock()

        async def mock_astream_error(messages):
            raise RuntimeError("Stream error")
            yield  # Make it a generator

        mock_llm.astream = mock_astream_error

        chain = RAGChain(llm=mock_llm, retriever=mock_retriever)
        tokens = []
        async for token in chain.astream("Question?"):
            tokens.append(token)

        assert tokens == [_ERROR_RESPONSE]
