"""LangSmith tracing service and callback handler.

Provides observability for all LangChain operations via LangSmith.
When KB_LANGSMITH_API_KEY is configured, traces are recorded for
retriever, chain, and LLM invocations. When the key is absent,
tracing is disabled and the system operates normally.
"""

import logging
import os
import random
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from app.services.langchain.config import LangChainSettings

logger = logging.getLogger(__name__)


class TracingCallbackHandler(BaseCallbackHandler):
    """Custom callback handler for trace metadata enrichment and sampling.

    Implements sampling logic based on a configurable sample rate and
    enriches traces with retrieval_mode, documents_retrieved, and
    total_token_count as run metadata.
    """

    def __init__(self, sample_rate: float = 1.0) -> None:
        """Initialize the callback handler.

        Args:
            sample_rate: Probability (0.0-1.0) that a given run will be traced.
                         1.0 means all runs are traced, 0.0 means none.
        """
        super().__init__()
        self.sample_rate = sample_rate
        self._should_trace: bool = True
        self._retrieval_mode: str = ""
        self._documents_retrieved: int = 0
        self._total_token_count: int = 0

    @property
    def run_metadata(self) -> dict[str, Any]:
        """Return current trace metadata."""
        return {
            "retrieval_mode": self._retrieval_mode,
            "documents_retrieved": self._documents_retrieved,
            "total_token_count": self._total_token_count,
        }

    def _decide_sampling(self) -> bool:
        """Decide whether to trace this run based on sample rate."""
        return random.random() < self.sample_rate

    @property
    def ignore_llm(self) -> bool:
        """Whether to ignore LLM callbacks."""
        return not self._should_trace

    @property
    def ignore_chain(self) -> bool:
        """Whether to ignore chain callbacks."""
        return not self._should_trace

    @property
    def ignore_retriever(self) -> bool:
        """Whether to ignore retriever callbacks."""
        return not self._should_trace

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain starts running. Decides sampling for this run."""
        self._should_trace = self._decide_sampling()
        if not self._should_trace:
            return

        # Extract retrieval_mode from inputs if available
        if isinstance(inputs, dict) and "retrieval_mode" in inputs:
            self._retrieval_mode = inputs["retrieval_mode"]

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Called when a chain finishes. Attaches metadata to the run."""
        if not self._should_trace:
            return

        # Extract metadata from outputs if available
        if isinstance(outputs, dict):
            if "retrieval_mode" in outputs:
                self._retrieval_mode = outputs["retrieval_mode"]
            if "documents_retrieved" in outputs:
                self._documents_retrieved = outputs["documents_retrieved"]

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM starts running."""
        if not self._should_trace:
            return

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Called when an LLM finishes. Records token usage."""
        if not self._should_trace:
            return

        try:
            if response.llm_output and "token_usage" in response.llm_output:
                token_usage = response.llm_output["token_usage"]
                total = token_usage.get("total_tokens", 0)
                self._total_token_count += total
        except Exception as exc:
            logger.warning(f"Failed to extract token usage from LLM response: {exc}")

    def on_retriever_start(
        self,
        serialized: dict[str, Any],
        query: str,
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """Called when a retriever starts running."""
        if not self._should_trace:
            return

    def on_retriever_end(
        self,
        documents: list[Any],
        *,
        run_id: Any = None,
        parent_run_id: Any = None,
        **kwargs: Any,
    ) -> None:
        """Called when a retriever finishes. Records documents retrieved count."""
        if not self._should_trace:
            return

        try:
            self._documents_retrieved = len(documents)
        except Exception as exc:
            logger.warning(
                f"Failed to record documents retrieved count: {exc}"
            )


class TracingService:
    """LangSmith tracing configuration and lifecycle.

    Configures LangSmith environment variables when an API key is present
    and provides callback handlers for trace enrichment.
    """

    def __init__(self, settings: LangChainSettings) -> None:
        """Initialize the tracing service.

        Args:
            settings: LangChain settings containing LangSmith configuration.
        """
        self._settings = settings
        self._configured = False

        if self.is_enabled():
            self.configure_environment()
            logger.info(
                f"LangSmith tracing enabled (project: {self._settings.langsmith_project}, "
                f"sample_rate: {self._settings.langsmith_sample_rate})"
            )
        else:
            logger.info(
                "LangSmith tracing is disabled (KB_LANGSMITH_API_KEY not set). "
                "Traces will not be recorded."
            )

    def is_enabled(self) -> bool:
        """Check if LangSmith tracing is enabled.

        Returns:
            True if KB_LANGSMITH_API_KEY is set (non-empty), False otherwise.
        """
        return bool(self._settings.langsmith_api_key)

    def get_callbacks(self) -> list[BaseCallbackHandler]:
        """Return list of callback handlers when tracing is enabled.

        Returns:
            A list containing the TracingCallbackHandler if tracing is enabled,
            or an empty list if tracing is disabled.
        """
        if not self.is_enabled():
            return []

        return [TracingCallbackHandler(sample_rate=self._settings.langsmith_sample_rate)]

    def configure_environment(self) -> None:
        """Set LANGCHAIN_* environment variables for LangSmith SDK.

        Configures:
        - LANGCHAIN_TRACING_V2: "true" to enable tracing
        - LANGCHAIN_API_KEY: The LangSmith API key
        - LANGCHAIN_PROJECT: The project name for trace grouping

        Handles errors gracefully by logging warnings and continuing.
        """
        try:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self._settings.langsmith_api_key
            os.environ["LANGCHAIN_PROJECT"] = self._settings.langsmith_project
            self._configured = True
        except Exception as exc:
            logger.warning(
                f"Failed to configure LangSmith environment variables: {exc}. "
                f"Tracing may not function correctly."
            )
