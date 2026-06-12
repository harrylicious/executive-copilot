"""RAG (Retrieval-Augmented Generation) chain implementation.

Combines the CustomRetriever with an LLM to produce grounded natural language
answers from retrieved knowledge base content. Supports synchronous, async,
and streaming invocation modes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, AsyncGenerator

import tiktoken
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

    from app.services.langchain.retriever import CustomRetriever

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT_TEMPLATE = """\
Kamu adalah Executive Copilot, asisten bisnis cerdas untuk para eksekutif.
Jawab pertanyaan berdasarkan konteks dokumen yang diberikan.
Aturan:
- Jawab dalam Bahasa Indonesia yang formal dan ringkas
- Jika pertanyaan tentang data barang/produk, gunakan data dari master barang
- Jika pertanyaan tentang outlet/toko, gunakan data dari master outlet
- Jika pertanyaan tentang distributor/agen, gunakan data dari master distributor
- Sertakan angka/data spesifik jika tersedia di konteks
- Jika data tidak tersedia di konteks, katakan "Data tidak ditemukan dalam dokumen yang tersedia"
- JANGAN mengarang data yang tidak ada di konteks
Konteks dokumen:
{context}
Pertanyaan: {question}
Jawaban:"""

_ERROR_RESPONSE = (
    "An error occurred while processing your request. Please try again later."
)


@dataclass
class RAGResponse:
    """Structured RAG chain response.

    Attributes:
        answer: The generated natural language answer.
        source_attributions: List of source attribution dicts, each containing
            file_id, file_name, and department.
        retrieval_metadata: Dict with retrieval_mode, documents_retrieved,
            and query_time_ms.
        token_usage: Dict with prompt_tokens, completion_tokens, and total_tokens.
    """

    answer: str = ""
    source_attributions: list[dict] = field(default_factory=list)
    retrieval_metadata: dict = field(default_factory=dict)
    token_usage: dict = field(default_factory=dict)


class RAGChain:
    """Retrieval-Augmented Generation chain with Indonesian business assistant prompt.

    Retrieves relevant documents via the CustomRetriever, assembles them
    into a single prompt using the Indonesian system prompt template,
    calls the LLM, and returns a structured RAGResponse.

    Args:
        llm: A LangChain BaseChatModel instance for generation.
        retriever: A CustomRetriever instance for document retrieval.
        max_context_tokens: Maximum token budget for context documents
            in the prompt (default 4000, range 1000-16000).
    """

    def __init__(
        self,
        llm: "BaseChatModel",
        retriever: "CustomRetriever",
        max_context_tokens: int = 4000,
    ) -> None:
        self.llm = llm
        self.retriever = retriever
        self.max_context_tokens = max_context_tokens
        self._encoding = tiktoken.get_encoding("cl100k_base")

    def invoke(self, query: str) -> RAGResponse:
        """Synchronously retrieve documents, generate answer, and return response.

        Args:
            query: The user's question (1-1000 characters).

        Returns:
            RAGResponse with answer, source attributions, retrieval metadata,
            and token usage.
        """
        start_time = time.time()

        # Retrieve documents
        try:
            documents = self.retriever.invoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed: {exc}")
            return self._error_response(start_time)

        # When zero documents are returned, substitute {context} with empty string
        # The prompt's built-in rule handles the "Data tidak ditemukan" response
        if not documents:
            context_text = ""
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and call LLM
        try:
            messages = self._build_messages(query, context_text)
            response = self.llm.invoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)

            # Extract token usage from response metadata
            token_usage = self._extract_token_usage(response)
        except Exception as exc:
            logger.error(f"LLM invocation failed: {exc}")
            return self._error_response(start_time)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return RAGResponse(
            answer=answer,
            source_attributions=self._extract_source_attributions(documents),
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": len(documents),
                "query_time_ms": elapsed_ms,
            },
            token_usage=token_usage,
        )

    async def ainvoke(self, query: str) -> RAGResponse:
        """Asynchronously retrieve documents, generate answer, and return response.

        Args:
            query: The user's question (1-1000 characters).

        Returns:
            RAGResponse with answer, source attributions, retrieval metadata,
            and token usage.
        """
        start_time = time.time()

        # Retrieve documents
        try:
            documents = await self.retriever.ainvoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed: {exc}")
            return self._error_response(start_time)

        # When zero documents are returned, substitute {context} with empty string
        if not documents:
            context_text = ""
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and call LLM
        try:
            messages = self._build_messages(query, context_text)
            response = await self.llm.ainvoke(messages)
            answer = response.content if hasattr(response, "content") else str(response)

            # Extract token usage from response metadata
            token_usage = self._extract_token_usage(response)
        except Exception as exc:
            logger.error(f"LLM invocation failed: {exc}")
            return self._error_response(start_time)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return RAGResponse(
            answer=answer,
            source_attributions=self._extract_source_attributions(documents),
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": len(documents),
                "query_time_ms": elapsed_ms,
            },
            token_usage=token_usage,
        )

    async def astream(self, query: str) -> AsyncGenerator[str, None]:
        """Asynchronously stream tokens as they are generated.

        Retrieves documents, builds the prompt, and yields tokens from
        the LLM as they are produced. On error, yields nothing (caller
        should handle the empty stream case).

        Args:
            query: The user's question.

        Yields:
            Individual tokens (strings) as they are generated by the LLM.
        """
        # Retrieve documents
        try:
            documents = await self.retriever.ainvoke(query)
        except Exception as exc:
            logger.error(f"Retrieval failed during streaming: {exc}")
            yield _ERROR_RESPONSE
            return

        # When zero documents are returned, substitute {context} with empty string
        if not documents:
            context_text = ""
        else:
            # Truncate context to fit token budget
            documents = self._truncate_context(documents, self.max_context_tokens)
            context_text = self._format_context(documents)

        # Build prompt and stream LLM response
        try:
            messages = self._build_messages(query, context_text)
            async for chunk in self.llm.astream(messages):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
        except Exception as exc:
            logger.error(f"LLM streaming failed: {exc}")
            yield _ERROR_RESPONSE

    def _build_messages(self, query: str, context_text: str) -> list[HumanMessage]:
        """Build the chat messages for the LLM call.

        Substitutes {context} and {question} into the Indonesian prompt template
        and returns it as a single HumanMessage. No separate system or user
        message is needed since the template contains everything.

        Args:
            query: The user's question.
            context_text: The formatted context string (or empty string if no docs).

        Returns:
            List containing a single HumanMessage with the fully substituted prompt.
        """
        prompt = _SYSTEM_PROMPT_TEMPLATE.format(context=context_text, question=query)
        return [HumanMessage(content=prompt)]

    def _format_context(self, documents: list[Document]) -> str:
        """Format documents into a context string with chunks joined by blank lines.

        Args:
            documents: List of documents to format.

        Returns:
            Formatted string with document chunks separated by blank lines.
        """
        return "\n\n".join(doc.page_content for doc in documents)

    def _truncate_context(
        self, documents: list[Document], max_tokens: int
    ) -> list[Document]:
        """Remove lowest-scored documents until context fits within token limit.

        Documents are sorted by score ascending, and the lowest-scored
        documents are removed first until the total token count of the
        remaining documents is within the max_tokens budget.

        Args:
            documents: List of documents to potentially truncate.
            max_tokens: Maximum allowed token count for the context.

        Returns:
            List of documents fitting within the token budget.
        """
        # Calculate total tokens for all documents
        total_tokens = self._count_tokens_for_documents(documents)

        if total_tokens <= max_tokens:
            return documents

        # Sort by score ascending (lowest first) to identify removal candidates
        # Use 'score' for chunks, 'relevance_score' for community summaries
        def get_score(doc: Document) -> float:
            metadata = doc.metadata
            if metadata.get("source_type") == "community_summary":
                return metadata.get("relevance_score", 0.0)
            return metadata.get("score", 0.0)

        sorted_docs = sorted(documents, key=get_score)

        # Remove lowest-scored documents until under the limit
        remaining = list(sorted_docs)
        while remaining and self._count_tokens_for_documents(remaining) > max_tokens:
            remaining.pop(0)  # Remove lowest-scored document

        return remaining

    def _count_tokens_for_documents(self, documents: list[Document]) -> int:
        """Count total tokens across all document page_content fields.

        Args:
            documents: List of documents to count tokens for.

        Returns:
            Total token count.
        """
        total = 0
        for doc in documents:
            total += len(self._encoding.encode(doc.page_content))
        return total

    def _extract_source_attributions(self, documents: list[Document]) -> list[dict]:
        """Extract source attributions from documents.

        Only includes documents with source_type="chunk" (not community summaries).

        Args:
            documents: List of documents used in the context.

        Returns:
            List of attribution dicts with file_id, file_name, and department.
        """
        attributions = []
        seen = set()

        for doc in documents:
            metadata = doc.metadata
            if metadata.get("source_type") != "chunk":
                continue

            file_id = metadata.get("file_id")
            file_name = metadata.get("file_name", "")
            department = metadata.get("department", "")

            # Deduplicate by file_id
            if file_id in seen:
                continue
            seen.add(file_id)

            attributions.append(
                {
                    "file_id": file_id,
                    "file_name": file_name,
                    "department": department,
                }
            )

        return attributions

    def _extract_token_usage(self, response: object) -> dict:
        """Extract token usage from LLM response metadata.

        Args:
            response: The LLM response object.

        Returns:
            Dict with prompt_tokens, completion_tokens, and total_tokens.
            Returns zeros if usage info is not available.
        """
        usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        # LangChain responses typically have usage_metadata or response_metadata
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            um = response.usage_metadata
            usage["prompt_tokens"] = getattr(um, "input_tokens", 0) or um.get("input_tokens", 0) if isinstance(um, dict) else getattr(um, "input_tokens", 0)
            usage["completion_tokens"] = getattr(um, "output_tokens", 0) or um.get("output_tokens", 0) if isinstance(um, dict) else getattr(um, "output_tokens", 0)
            usage["total_tokens"] = usage["prompt_tokens"] + usage["completion_tokens"]
        elif hasattr(response, "response_metadata") and response.response_metadata:
            rm = response.response_metadata
            token_usage = rm.get("token_usage", {}) or rm.get("usage", {})
            if token_usage:
                usage["prompt_tokens"] = token_usage.get("prompt_tokens", 0)
                usage["completion_tokens"] = token_usage.get("completion_tokens", 0)
                usage["total_tokens"] = token_usage.get("total_tokens", 0)

        return usage

    def _error_response(self, start_time: float) -> RAGResponse:
        """Build a response for when an error occurs.

        Args:
            start_time: The time the request started (for elapsed time calc).

        Returns:
            RAGResponse with a generic error message.
        """
        elapsed_ms = int((time.time() - start_time) * 1000)
        return RAGResponse(
            answer=_ERROR_RESPONSE,
            source_attributions=[],
            retrieval_metadata={
                "retrieval_mode": getattr(self.retriever, "retrieval_mode", "combined"),
                "documents_retrieved": 0,
                "query_time_ms": elapsed_ms,
            },
            token_usage={
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
            },
        )
