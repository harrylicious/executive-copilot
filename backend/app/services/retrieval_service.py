"""Retrieval service for local, global, and combined search queries.

Handles search queries using TurboVecStore with intent-based routing
via QueryRouter. Performs vector-similarity-only search against the
dual-index TurboVec store (master + department).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import tiktoken

from app.config import TurboVecSettings
from app.services.embedding_model import EmbeddingModel
from app.services.query_router import QueryRouter

if TYPE_CHECKING:
    from app.services.turbovec_store import TurboVecStore

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured search result containing all retrieval components."""

    chunks: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    community_summaries: list[dict] = field(default_factory=list)
    source_attributions: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RetrievalService:
    """Handles search queries using TurboVec vector store with intent routing.

    Provides three retrieval modes:
    - local_search: Vector similarity search with intent routing via QueryRouter
    - global_search: Vector search using QueryRouter logic (community-based removed)
    - combined_search: Merged search using router with token budget

    Args:
        store: TurboVecStore instance with initialized indexes.
        router: QueryRouter instance for keyword-based intent routing.
        config: TurboVec settings for retrieval parameters.
    """

    def __init__(
        self,
        store: "TurboVecStore",
        router: QueryRouter,
        config: TurboVecSettings,
    ):
        self.store = store
        self.router = router
        self.config = config
        self.model = EmbeddingModel(config.embedding_model)

    def local_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.3,
        similarity_weight: float = 0.7,
        **kwargs: Any,
    ) -> SearchResult:
        """Vector similarity search with intent routing.

        Uses the QueryRouter to determine which index to query, then
        performs vector similarity search via TurboVecStore. Results are
        filtered by min_score and limited to top_k.

        Args:
            query: The search query text (1-1000 characters).
            top_k: Maximum number of results to return (1-50, default 5).
            min_score: Minimum similarity score threshold (0.0-1.0, default 0.3).
            similarity_weight: Weight for vector similarity (kept for API compatibility, no-op).
            **kwargs: Additional parameters accepted for API compatibility.

        Returns:
            SearchResult with ranked chunks and metadata.

        Raises:
            ValueError: If query is empty or exceeds 1000 characters.
        """
        start_time = time.time()

        # Validate query
        if not query or not query.strip():
            raise ValueError(
                "Query text must not be empty. Please provide a query between "
                "1 and 1000 characters."
            )
        if len(query) > 1000:
            raise ValueError(
                "Query text exceeds 1000 characters. Please shorten your query "
                "to at most 1000 characters."
            )

        # Generate query embedding
        query_embedding = self.model.embed_query(query)

        # Use QueryRouter to route and retrieve results
        results = self.router.retrieve(query, query_embedding, self.store)

        # Filter by min_score and limit to top_k
        filtered_results = [
            r for r in results if r.get("score", 0.0) >= min_score
        ]
        filtered_results = filtered_results[:top_k]

        # Map results to the expected chunk format
        enriched_chunks, source_attributions = self._map_results_to_chunks(
            filtered_results
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return SearchResult(
            chunks=enriched_chunks,
            entities=[],
            relationships=[],
            community_summaries=[],
            source_attributions=source_attributions,
            metadata={
                "query_time_ms": elapsed_ms,
                "total_chunks_searched": len(filtered_results),
                "retrieval_mode": "local",
            },
        )

    def global_search(
        self,
        query: str,
        num_communities: int = 3,
        min_relevance: float = 0.1,
        **kwargs: Any,
    ) -> SearchResult:
        """Vector search using QueryRouter logic.

        Replaces the previous community-based global search. The endpoint
        remains functional by routing to the appropriate TurboVec index
        using the QueryRouter.

        Args:
            query: The search query text (1-1000 characters).
            num_communities: Kept for API compatibility (no-op).
            min_relevance: Minimum similarity threshold (0.0-1.0, default 0.1).
            **kwargs: Additional parameters accepted for API compatibility.

        Returns:
            SearchResult with chunks and metadata.

        Raises:
            ValueError: If query is empty or exceeds 1000 characters.
        """
        start_time = time.time()

        # Validate query
        if not query or not query.strip():
            raise ValueError(
                "Query text must not be empty. Please provide a query between "
                "1 and 1000 characters."
            )
        if len(query) > 1000:
            raise ValueError(
                "Query text exceeds 1000 characters. Please shorten your query "
                "to at most 1000 characters."
            )

        # Generate query embedding
        query_embedding = self.model.embed_query(query)

        # Use QueryRouter to route and retrieve results
        results = self.router.retrieve(query, query_embedding, self.store)

        # Filter by min_relevance
        filtered_results = [
            r for r in results if r.get("score", 0.0) >= min_relevance
        ]

        # Map results to the expected chunk format
        enriched_chunks, source_attributions = self._map_results_to_chunks(
            filtered_results
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return SearchResult(
            chunks=enriched_chunks,
            entities=[],
            relationships=[],
            community_summaries=[],
            source_attributions=source_attributions,
            metadata={
                "query_time_ms": elapsed_ms,
                "total_chunks_searched": len(filtered_results),
                "retrieval_mode": "global",
            },
        )

    def combined_search(
        self,
        query: str,
        max_tokens: int = 4000,
        top_k: int = 5,
        num_communities: int = 3,
        min_score: float = 0.3,
        min_relevance: float = 0.1,
        similarity_weight: float = 0.7,
        **kwargs: Any,
    ) -> SearchResult:
        """Merged search using router with token budget.

        Uses the QueryRouter to retrieve results and then truncates
        to fit within the configured token limit. Accepts all existing
        parameters for API compatibility even though some are no-ops.

        Args:
            query: The search query text (1-1000 characters).
            max_tokens: Maximum context token limit (1000-16000, default 4000).
            top_k: Maximum number of results (1-50, default 5).
            num_communities: Kept for API compatibility (no-op).
            min_score: Minimum similarity score threshold (0.0-1.0, default 0.3).
            min_relevance: Minimum relevance threshold (0.0-1.0, default 0.1).
            similarity_weight: Weight for vector similarity (kept for API compatibility, no-op).
            **kwargs: Additional parameters accepted for API compatibility.

        Returns:
            SearchResult with merged chunks, source_attributions, and metadata.

        Raises:
            ValueError: If query is empty or exceeds 1000 characters.
        """
        start_time = time.time()

        # Validate query
        if not query or not query.strip():
            raise ValueError(
                "Query text must not be empty. Please provide a query between "
                "1 and 1000 characters."
            )
        if len(query) > 1000:
            raise ValueError(
                "Query text exceeds 1000 characters. Please shorten your query "
                "to at most 1000 characters."
            )

        # Validate and clamp max_tokens
        max_tokens = max(1000, min(16000, max_tokens))

        # Generate query embedding
        query_embedding = self.model.embed_query(query)

        # Use QueryRouter to route and retrieve results
        results = self.router.retrieve(query, query_embedding, self.store)

        # Apply the stricter of min_score and min_relevance as a combined filter
        effective_min_score = min(min_score, min_relevance)
        filtered_results = [
            r for r in results if r.get("score", 0.0) >= effective_min_score
        ]

        # Limit to top_k
        filtered_results = filtered_results[:top_k]

        # Map results to the expected chunk format
        enriched_chunks, source_attributions = self._map_results_to_chunks(
            filtered_results
        )

        # Build initial result
        result = SearchResult(
            chunks=enriched_chunks,
            entities=[],
            relationships=[],
            community_summaries=[],
            source_attributions=source_attributions,
            metadata={
                "query_time_ms": 0,
                "total_chunks_searched": len(filtered_results),
                "retrieval_mode": "combined",
            },
        )

        # Truncate to token limit
        result = self._truncate_to_token_limit(result, max_tokens)

        elapsed_ms = int((time.time() - start_time) * 1000)
        result.metadata["query_time_ms"] = elapsed_ms

        return result

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _map_results_to_chunks(
        self, results: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        """Map TurboVec search results to the API chunk format.

        Converts results from the TurboVecStore/QueryRouter format to
        the enriched chunk dicts expected by the SearchResponse schema.

        Args:
            results: List of result dicts from TurboVecStore similarity_search.
                Each dict has 'content', 'metadata', and 'score' keys.

        Returns:
            A tuple of (enriched_chunks, source_attributions).
        """
        enriched_chunks: list[dict] = []
        source_attributions: list[dict] = []
        seen_file_ids: set[int] = set()

        for result in results:
            metadata = result.get("metadata", {})
            file_id = metadata.get("file_id", 0)
            filename = metadata.get("filename", "")
            department = metadata.get("department", "")

            chunk_data: dict[str, Any] = {
                "text": result.get("content", ""),
                "score": result.get("score", 0.0),
                "file_id": file_id,
                "file_name": filename,
                "department": department,
                "file_path": "",
                "chunk_index": metadata.get("chunk_index", 0),
                "entities": [],
                "relationships": [],
            }
            enriched_chunks.append(chunk_data)

            # Collect unique source attributions
            if file_id and file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                source_attributions.append({
                    "file_id": file_id,
                    "file_name": filename,
                    "department": department,
                    "file_path": "",
                })

        return enriched_chunks, source_attributions

    def _truncate_to_token_limit(
        self, results: SearchResult, max_tokens: int
    ) -> SearchResult:
        """Remove lowest-relevance items until within token budget.

        Args:
            results: The SearchResult to potentially truncate.
            max_tokens: Maximum allowed token count for the assembled context.

        Returns:
            A new SearchResult truncated to fit within the token budget.
        """
        tokenizer = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            if not text:
                return 0
            return len(tokenizer.encode(text))

        def compute_result_tokens(result: SearchResult) -> int:
            total = 0
            for chunk in result.chunks:
                total += count_tokens(chunk.get("text", ""))
            return total

        current_tokens = compute_result_tokens(results)

        if current_tokens <= max_tokens:
            return results

        # Remove lowest-score chunks until within budget
        scored_chunks = [
            (chunk.get("score", 0.0), i, count_tokens(chunk.get("text", "")))
            for i, chunk in enumerate(results.chunks)
        ]
        scored_chunks.sort(key=lambda x: x[0])  # ascending score

        chunks_to_remove: set[int] = set()
        for _score, index, token_cost in scored_chunks:
            if current_tokens <= max_tokens:
                break
            chunks_to_remove.add(index)
            current_tokens -= token_cost

        truncated_chunks = [
            chunk
            for i, chunk in enumerate(results.chunks)
            if i not in chunks_to_remove
        ]

        # Rebuild source attributions based on remaining chunks
        remaining_file_ids: set[int] = set()
        for chunk in truncated_chunks:
            file_id = chunk.get("file_id")
            if file_id is not None:
                remaining_file_ids.add(file_id)

        truncated_attributions = [
            attr for attr in results.source_attributions
            if attr.get("file_id") in remaining_file_ids
        ]

        return SearchResult(
            chunks=truncated_chunks,
            entities=[],
            relationships=[],
            community_summaries=[],
            source_attributions=truncated_attributions,
            metadata=results.metadata,
        )
