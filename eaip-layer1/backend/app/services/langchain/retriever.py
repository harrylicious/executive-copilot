"""Custom LangChain retriever wrapping the existing RetrievalService.

Implements the LangChain BaseRetriever interface, delegating to
RetrievalService.local_search, global_search, or combined_search
based on the configured retrieval mode. Maps SearchResult objects
to LangChain Document objects for downstream chain consumption.
"""

import asyncio
from typing import Any

from langchain_core.callbacks import (
    AsyncCallbackManagerForRetrieverRun,
    CallbackManagerForRetrieverRun,
)
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.services.retrieval_service import RetrievalService, SearchResult


class CustomRetriever(BaseRetriever):
    """LangChain BaseRetriever wrapping the existing RetrievalService.

    Delegates retrieval to the appropriate RetrievalService method based
    on the configured retrieval_mode, and maps results to LangChain
    Document objects.

    Attributes:
        retrieval_service: Injected RetrievalService instance.
        retrieval_mode: One of "local", "global", or "combined" (default "combined").
        top_k: Max results for local/combined search (default 5, range 1-50).
        min_score: Min similarity score for local/combined (default 0.5, range 0.0-1.0).
        similarity_weight: Similarity weight for local/combined (default 0.7, range 0.0-1.0).
        num_communities: Communities for global/combined (default 3, range 1-20).
        min_relevance: Min relevance for global/combined (default 0.1, range 0.0-1.0).
        max_tokens: Token budget for combined search (default 4000, range 1000-16000).
    """

    retrieval_service: Any  # RetrievalService (Any for pydantic compatibility)
    retrieval_mode: str = "combined"
    top_k: int = 5
    min_score: float = 0.5
    similarity_weight: float = 0.7
    num_communities: int = 3
    min_relevance: float = 0.1
    max_tokens: int = 4000

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """Retrieve documents by delegating to RetrievalService.

        Routes to local_search, global_search, or combined_search based
        on self.retrieval_mode. Propagates ValueError from RetrievalService
        without modification.

        Args:
            query: The search query text.
            run_manager: LangChain callback manager (unused but required by interface).

        Returns:
            List of LangChain Document objects mapped from SearchResult.

        Raises:
            ValueError: Propagated from RetrievalService for invalid queries.
        """
        result = self._execute_search(query)
        return self._map_search_result_to_documents(result)

    async def _aget_relevant_documents(
        self,
        query: str,
        *,
        run_manager: AsyncCallbackManagerForRetrieverRun,
    ) -> list[Document]:
        """Async variant of _get_relevant_documents.

        Runs the synchronous RetrievalService call in a thread pool
        to avoid blocking the event loop.

        Args:
            query: The search query text.
            run_manager: Async callback manager (unused but required by interface).

        Returns:
            List of LangChain Document objects mapped from SearchResult.

        Raises:
            ValueError: Propagated from RetrievalService for invalid queries.
        """
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, self._execute_search, query)
        return self._map_search_result_to_documents(result)

    def _execute_search(self, query: str) -> SearchResult:
        """Execute the appropriate search method based on retrieval_mode.

        Args:
            query: The search query text.

        Returns:
            SearchResult from the underlying RetrievalService.

        Raises:
            ValueError: Propagated from RetrievalService for invalid queries.
        """
        if self.retrieval_mode == "local":
            return self.retrieval_service.local_search(
                query=query,
                top_k=self.top_k,
                min_score=self.min_score,
                similarity_weight=self.similarity_weight,
            )
        elif self.retrieval_mode == "global":
            return self.retrieval_service.global_search(
                query=query,
                num_communities=self.num_communities,
                min_relevance=self.min_relevance,
            )
        else:
            # "combined" mode (default)
            return self.retrieval_service.combined_search(
                query=query,
                max_tokens=self.max_tokens,
                top_k=self.top_k,
                num_communities=self.num_communities,
                min_score=self.min_score,
                min_relevance=self.min_relevance,
                similarity_weight=self.similarity_weight,
            )

    def _map_search_result_to_documents(
        self, result: SearchResult
    ) -> list[Document]:
        """Map a SearchResult to a list of LangChain Document objects.

        Chunks are mapped with source_type="chunk" metadata.
        Community summaries are mapped with source_type="community_summary" metadata.

        Args:
            result: The SearchResult from RetrievalService.

        Returns:
            List of LangChain Document objects.
        """
        documents: list[Document] = []

        # Map chunks to Documents
        for chunk in result.chunks:
            documents.append(
                Document(
                    page_content=chunk.get("text", ""),
                    metadata={
                        "file_id": chunk.get("file_id"),
                        "file_name": chunk.get("file_name", ""),
                        "department": chunk.get("department", ""),
                        "chunk_index": chunk.get("chunk_index"),
                        "score": chunk.get("score", 0.0),
                        "source_type": "chunk",
                    },
                )
            )

        # Map community summaries to Documents
        for summary in result.community_summaries:
            documents.append(
                Document(
                    page_content=summary.get("summary", ""),
                    metadata={
                        "community_id": summary.get("community_id"),
                        "level": summary.get("level"),
                        "relevance_score": summary.get("relevance_score", 0.0),
                        "source_type": "community_summary",
                    },
                )
            )

        return documents
