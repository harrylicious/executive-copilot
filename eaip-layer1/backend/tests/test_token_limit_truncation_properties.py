"""Property-based tests for token limit truncation in combined search.

Property 21: Combined search respects token limit by truncating lowest-relevance items

For any combined search result, the total token count of the assembled context
SHALL NOT exceed the configured maximum token limit, and when truncation is
necessary, items with the lowest relevance scores SHALL be removed first.

**Validates: Requirements 9.3**
"""

from unittest.mock import MagicMock, patch

import hypothesis.strategies as st
import tiktoken
from hypothesis import HealthCheck, given, settings, assume

from app.config import GraphRAGSettings
from app.services.retrieval_service import RetrievalService, SearchResult


# --- Strategies ---

# Strategy for max_tokens (valid range 1000-16000)
max_tokens_st = st.integers(min_value=1000, max_value=4000)

# Strategy for relevance scores
relevance_score_st = st.floats(min_value=0.01, max_value=1.0, allow_nan=False)

# Strategy for generating chunk text of varying token lengths
# We use words that are typically 1 token each to control token count
def chunk_text_st(min_tokens: int = 10, max_tokens: int = 200):
    """Generate text with a controlled number of tokens.

    Uses simple words that map to single tokens in cl100k_base.
    """
    return st.integers(min_value=min_tokens, max_value=max_tokens).map(
        lambda n: " ".join(["word"] * n)
    )


# Strategy for a single chunk item with score and text
def chunk_item_st():
    """Generate a chunk dict with a relevance score and text."""
    return st.fixed_dictionaries({
        "text": chunk_text_st(min_tokens=20, max_tokens=300),
        "score": relevance_score_st,
        "file_id": st.integers(min_value=1, max_value=100),
        "file_name": st.just("test.txt"),
        "department": st.just("engineering"),
        "file_path": st.just("engineering/test.txt"),
        "chunk_index": st.integers(min_value=0, max_value=50),
        "entities": st.just([]),
        "relationships": st.just([]),
    })


# Strategy for a community summary item with relevance_score and summary text
def community_summary_st():
    """Generate a community summary dict with a relevance score and summary."""
    return st.fixed_dictionaries({
        "community_id": st.integers(min_value=1, max_value=100),
        "level": st.integers(min_value=0, max_value=4),
        "summary": chunk_text_st(min_tokens=20, max_tokens=200),
        "relevance_score": relevance_score_st,
        "member_entities": st.just([]),
        "document_references": st.just([]),
    })


# --- Helper functions ---

def _count_tokens(text: str) -> int:
    """Count tokens using cl100k_base encoding (same as the service)."""
    if not text:
        return 0
    tokenizer = tiktoken.get_encoding("cl100k_base")
    return len(tokenizer.encode(text))


def _compute_result_tokens(result: SearchResult) -> int:
    """Compute total token count for a SearchResult (mirrors service logic)."""
    total = 0
    for chunk in result.chunks:
        total += _count_tokens(chunk.get("text", ""))
    for summary in result.community_summaries:
        total += _count_tokens(summary.get("summary", ""))
    for entity in result.entities:
        total += _count_tokens(entity.get("description", "") or "")
        total += _count_tokens(entity.get("name", "") or "")
    for rel in result.relationships:
        total += _count_tokens(rel.get("description", "") or "")
    return total


def _create_mock_combined_search_service(
    local_chunks: list[dict],
    community_summaries: list[dict],
) -> RetrievalService:
    """Create a RetrievalService with mocked local_search and global_search.

    This allows us to test the combined_search merging and truncation logic
    directly without needing a real database or vector store.
    """
    mock_db = MagicMock()
    config = GraphRAGSettings(vector_store_path="./test_chroma_prop21")

    with patch(
        "app.services.retrieval_service.EmbeddingModel"
    ) as MockModel, patch(
        "app.services.retrieval_service.ChromaVectorStore"
    ), patch(
        "app.services.retrieval_service.GraphRAGEngine"
    ):
        mock_model_instance = MockModel.return_value
        mock_model_instance.embed_query.return_value = [0.1] * 384
        mock_model_instance.dimension = 384

        service = RetrievalService(db=mock_db, config=config)
        service.model = mock_model_instance

    # Mock local_search to return the provided chunks
    local_result = SearchResult(
        chunks=local_chunks,
        entities=[],
        relationships=[],
        community_summaries=[],
        source_attributions=[
            {"file_id": c["file_id"], "file_name": c["file_name"],
             "department": c["department"], "file_path": c["file_path"]}
            for c in local_chunks
        ],
        metadata={"query_time_ms": 10, "total_chunks_searched": len(local_chunks), "retrieval_mode": "local"},
    )

    # Mock global_search to return the provided community summaries
    global_result = SearchResult(
        chunks=[],
        entities=[],
        relationships=[],
        community_summaries=community_summaries,
        source_attributions=[],
        metadata={"query_time_ms": 5, "total_chunks_searched": 0, "retrieval_mode": "global"},
    )

    service.local_search = MagicMock(return_value=local_result)
    service.global_search = MagicMock(return_value=global_result)

    return service


# --- Property Tests ---


class TestProperty21TokenLimitTruncation:
    """Property 21: Combined search respects token limit by truncating lowest-relevance items.

    **Validates: Requirements 9.3**
    """

    @given(
        chunks=st.lists(chunk_item_st(), min_size=2, max_size=8),
        community_summaries=st.lists(community_summary_st(), min_size=1, max_size=4),
        max_tokens=max_tokens_st,
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_total_tokens_do_not_exceed_max_limit(
        self,
        chunks: list[dict],
        community_summaries: list[dict],
        max_tokens: int,
    ):
        """For any combined search result, the total token count of the assembled
        context SHALL NOT exceed the configured maximum token limit.

        **Validates: Requirements 9.3**
        """
        # Ensure the input data actually exceeds the token limit so truncation is needed
        # (otherwise the property is trivially satisfied)
        input_result = SearchResult(
            chunks=chunks,
            community_summaries=community_summaries,
            entities=[],
            relationships=[],
            source_attributions=[],
            metadata={},
        )
        input_tokens = _compute_result_tokens(input_result)
        assume(input_tokens > max_tokens)

        # Create service and run combined search
        service = _create_mock_combined_search_service(chunks, community_summaries)

        result = service.combined_search(
            query="test query",
            max_tokens=max_tokens,
        )

        # Verify: total tokens in result do not exceed max_tokens
        result_tokens = _compute_result_tokens(result)
        assert result_tokens <= max_tokens, (
            f"Result token count {result_tokens} exceeds max_tokens {max_tokens}. "
            f"Chunks: {len(result.chunks)}, Summaries: {len(result.community_summaries)}"
        )

    @given(
        chunks=st.lists(chunk_item_st(), min_size=3, max_size=8),
        community_summaries=st.lists(community_summary_st(), min_size=1, max_size=4),
        max_tokens=max_tokens_st,
    )
    @settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.filter_too_much])
    def test_lowest_relevance_items_removed_first(
        self,
        chunks: list[dict],
        community_summaries: list[dict],
        max_tokens: int,
    ):
        """When truncation is necessary, items with the lowest relevance scores
        SHALL be removed first.

        This verifies that if an item is removed, no remaining item has a lower
        relevance score than the removed item.

        **Validates: Requirements 9.3**
        """
        # Ensure the input data exceeds the token limit so truncation occurs
        input_result = SearchResult(
            chunks=chunks,
            community_summaries=community_summaries,
            entities=[],
            relationships=[],
            source_attributions=[],
            metadata={},
        )
        input_tokens = _compute_result_tokens(input_result)
        assume(input_tokens > max_tokens)

        # Create service and run combined search
        service = _create_mock_combined_search_service(chunks, community_summaries)

        result = service.combined_search(
            query="test query",
            max_tokens=max_tokens,
        )

        # Determine which items were kept and which were removed
        # Collect all scores from the original input
        all_input_scores = []
        for chunk in chunks:
            all_input_scores.append(("chunk", chunk["score"], chunk["text"]))
        for summary in community_summaries:
            all_input_scores.append(("summary", summary["relevance_score"], summary["summary"]))

        # Collect scores of items that remain in the result
        remaining_scores = []
        for chunk in result.chunks:
            remaining_scores.append(chunk["score"])
        for summary in result.community_summaries:
            remaining_scores.append(summary["relevance_score"])

        # If nothing was removed, the property is trivially satisfied
        total_input_items = len(chunks) + len(community_summaries)
        total_output_items = len(result.chunks) + len(result.community_summaries)

        if total_output_items >= total_input_items:
            return  # No truncation occurred

        # If truncation occurred, verify that the minimum remaining score
        # is >= the maximum removed score.
        # Build sets of remaining texts to identify removed items
        remaining_chunk_texts = {c["text"] for c in result.chunks}
        remaining_summary_texts = {s["summary"] for s in result.community_summaries}

        removed_scores = []
        for item_type, score, text in all_input_scores:
            if item_type == "chunk" and text not in remaining_chunk_texts:
                removed_scores.append(score)
            elif item_type == "summary" and text not in remaining_summary_texts:
                removed_scores.append(score)

        if not removed_scores or not remaining_scores:
            return  # Edge case: all removed or none removed

        max_removed_score = max(removed_scores)
        min_remaining_score = min(remaining_scores)

        assert min_remaining_score >= max_removed_score, (
            f"Truncation order violation: a remaining item has score "
            f"{min_remaining_score} which is less than a removed item's score "
            f"{max_removed_score}. This means a higher-relevance item was removed "
            f"before a lower-relevance item."
        )

    @given(
        chunks=st.lists(chunk_item_st(), min_size=1, max_size=5),
        community_summaries=st.lists(community_summary_st(), min_size=0, max_size=3),
        max_tokens=st.integers(min_value=4000, max_value=16000),
    )
    @settings(max_examples=50, deadline=None)
    def test_no_truncation_when_within_limit(
        self,
        chunks: list[dict],
        community_summaries: list[dict],
        max_tokens: int,
    ):
        """When the assembled context is within the token limit, no items
        SHALL be removed.

        **Validates: Requirements 9.3**
        """
        # Ensure the input data is within the token limit
        input_result = SearchResult(
            chunks=chunks,
            community_summaries=community_summaries,
            entities=[],
            relationships=[],
            source_attributions=[],
            metadata={},
        )
        input_tokens = _compute_result_tokens(input_result)
        assume(input_tokens <= max_tokens)

        # Create service and run combined search
        service = _create_mock_combined_search_service(chunks, community_summaries)

        result = service.combined_search(
            query="test query",
            max_tokens=max_tokens,
        )

        # Verify: all items are preserved (no truncation)
        assert len(result.chunks) == len(chunks), (
            f"Expected {len(chunks)} chunks but got {len(result.chunks)} "
            f"even though total tokens ({input_tokens}) <= max_tokens ({max_tokens})"
        )
        assert len(result.community_summaries) == len(community_summaries), (
            f"Expected {len(community_summaries)} summaries but got "
            f"{len(result.community_summaries)} even though total tokens "
            f"({input_tokens}) <= max_tokens ({max_tokens})"
        )
