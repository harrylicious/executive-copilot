"""Service initialization and dependency injection for LangChain integration.

Provides a centralized service container that instantiates and wires together
all LangChain components: LangChainSettings, LLM provider, TracingService,
SessionStore, CustomRetriever, RAGChain, and AgentWorkflow.

Implements graceful degradation: if the LLM is not configured or required
packages are missing, LLM-dependent features are disabled while retrieval
remains operational. TracingService callbacks are attached to all LangChain
operations when tracing is enabled.

Usage from FastAPI dependencies:

    from app.services.langchain.dependencies import get_service_container

    container = get_service_container()
    if not container.is_llm_available:
        raise HTTPException(503, ...)
    workflow = container.build_workflow(db, retrieval_mode, top_k, max_tokens)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.services.langchain import LANGCHAIN_AVAILABLE
from app.services.langchain.config import LangChainSettings
from app.services.langchain.session_store import SessionStore

if TYPE_CHECKING:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.language_models import BaseChatModel
    from sqlalchemy.orm import Session

    from app.services.langchain.agent_workflow import AgentWorkflow
    from app.services.langchain.rag_chain import RAGChain
    from app.services.langchain.retriever import CustomRetriever
    from app.services.langchain.tracing import TracingService

logger = logging.getLogger(__name__)


class ServiceContainer:
    """Centralized container for LangChain service instances.

    Instantiates settings, LLM, tracing, and session store at construction
    time. Provides factory methods to build request-scoped components
    (retriever, RAG chain, agent workflow) that require a database session.

    Attributes:
        settings: LangChainSettings loaded from environment.
        llm: The LLM instance, or None if not configured/available.
        tracing_service: TracingService instance (may be disabled).
        session_store: Shared in-memory session store for conversations.
        is_llm_available: Whether LLM-dependent features can be used.
    """

    def __init__(self) -> None:
        """Initialize the service container.

        Loads settings, creates the LLM (if configured), sets up tracing,
        and initializes the session store. Logs status at startup.
        """
        # 1. Load settings from environment
        self.settings = LangChainSettings()

        # 2. Determine overall availability
        self._packages_available = LANGCHAIN_AVAILABLE

        # 3. Create LLM instance (may be None)
        self.llm: BaseChatModel | None = None
        if self._packages_available and self.settings.is_llm_configured():
            self.llm = self._create_llm()

        # 4. Create TracingService and configure environment if LLM is available
        self.tracing_service: TracingService | None = None
        if self._packages_available and self.llm is not None:
            self.tracing_service = self._create_tracing_service()

        # 5. Initialize shared session store
        self.session_store = SessionStore()

        # 6. Log startup status
        self._log_status()

    @property
    def is_llm_available(self) -> bool:
        """Whether LLM-dependent features are operational.

        Returns False if packages are missing or LLM is not configured.
        Retrieval-only features remain available regardless.
        """
        return self._packages_available and self.llm is not None

    def get_tracing_callbacks(self) -> list[Any]:
        """Return tracing callbacks to attach to LangChain operations.

        Returns an empty list if tracing is not enabled or not configured.
        """
        if self.tracing_service is not None and self.tracing_service.is_enabled():
            return self.tracing_service.get_callbacks()
        return []

    def build_workflow(
        self,
        db: "Session",
        retrieval_mode: str = "combined",
        top_k: int | None = None,
        max_tokens: int | None = None,
        language: str = "id",
    ) -> "AgentWorkflow":
        """Build a fully-wired AgentWorkflow for a request.

        Creates a CustomRetriever (bound to the given db session), a RAGChain,
        and an AgentWorkflow. Attaches TracingService callbacks when enabled.

        Args:
            db: SQLAlchemy session for the retrieval service.
            retrieval_mode: Retrieval mode (local, global, combined).
            top_k: Optional top_k override for retrieval.
            max_tokens: Optional max context tokens override.
            language: Response language code (id or en).

        Returns:
            An AgentWorkflow instance ready to invoke.

        Raises:
            RuntimeError: If LLM is not available.
        """
        if not self.is_llm_available:
            raise RuntimeError(
                "Cannot build workflow: LLM is not available. "
                "Check package availability and LLM configuration."
            )

        from app.services.langchain.agent_workflow import AgentWorkflow
        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.retriever import CustomRetriever
        from app.config import graphrag_settings
        from app.services.retrieval_service import RetrievalService

        # Build retrieval service with the request's db session
        retrieval_service = RetrievalService(db, graphrag_settings)

        # Build retriever with optional overrides
        retriever_kwargs: dict[str, Any] = {
            "retrieval_service": retrieval_service,
            "retrieval_mode": retrieval_mode,
        }
        if top_k is not None:
            retriever_kwargs["top_k"] = top_k
        if max_tokens is not None:
            retriever_kwargs["max_tokens"] = max_tokens

        retriever = CustomRetriever(**retriever_kwargs)

        # Determine context token limit
        context_tokens = max_tokens if max_tokens is not None else self.settings.llm_max_tokens

        # Attach tracing callbacks to the LLM before building chains
        callbacks = self.get_tracing_callbacks()
        if callbacks:
            self._attach_callbacks_to_llm(callbacks)

        # Build RAG chain
        rag_chain = RAGChain(
            llm=self.llm,
            retriever=retriever,
            max_context_tokens=context_tokens,
            language=language,
        )

        # Build agent workflow with shared session store
        workflow = AgentWorkflow(llm=self.llm, rag_chain=rag_chain, language=language)
        workflow.session_store = self.session_store

        return workflow

    def build_rag_chain(
        self,
        db: "Session",
        retrieval_mode: str = "combined",
        top_k: int | None = None,
        max_tokens: int | None = None,
        language: str = "id",
    ) -> tuple["RAGChain", "CustomRetriever"]:
        """Build a RAGChain and retriever for streaming (bypasses agent workflow).

        Args:
            db: SQLAlchemy session for the retrieval service.
            retrieval_mode: Retrieval mode (local, global, combined).
            top_k: Optional top_k override for retrieval.
            max_tokens: Optional max context tokens override.
            language: Response language code (id or en).

        Returns:
            A tuple of (RAGChain, CustomRetriever) instances.

        Raises:
            RuntimeError: If LLM is not available.
        """
        if not self.is_llm_available:
            raise RuntimeError(
                "Cannot build RAG chain: LLM is not available. "
                "Check package availability and LLM configuration."
            )

        from app.services.langchain.rag_chain import RAGChain
        from app.services.langchain.retriever import CustomRetriever
        from app.config import graphrag_settings
        from app.services.retrieval_service import RetrievalService

        retrieval_service = RetrievalService(db, graphrag_settings)

        retriever_kwargs: dict[str, Any] = {
            "retrieval_service": retrieval_service,
            "retrieval_mode": retrieval_mode,
        }
        if top_k is not None:
            retriever_kwargs["top_k"] = top_k
        if max_tokens is not None:
            retriever_kwargs["max_tokens"] = max_tokens

        retriever = CustomRetriever(**retriever_kwargs)

        context_tokens = max_tokens if max_tokens is not None else self.settings.llm_max_tokens

        # Attach tracing callbacks to the LLM before building chains
        callbacks = self.get_tracing_callbacks()
        if callbacks:
            self._attach_callbacks_to_llm(callbacks)

        # Build RAG chain
        rag_chain = RAGChain(
            llm=self.llm,
            retriever=retriever,
            max_context_tokens=context_tokens,
            language=language,
        )

        return rag_chain, retriever

    def _create_llm(self) -> "BaseChatModel | None":
        """Create the LLM instance using the provider factory.

        Returns None if creation fails for any reason.
        """
        try:
            from app.services.langchain.llm_provider import create_llm

            return create_llm(self.settings)
        except Exception as exc:
            logger.error(f"Failed to create LLM instance: {exc}")
            return None

    def _create_tracing_service(self) -> "TracingService | None":
        """Create and configure the TracingService.

        Returns None if creation fails.
        """
        try:
            from app.services.langchain.tracing import TracingService

            return TracingService(self.settings)
        except Exception as exc:
            logger.warning(f"Failed to initialize TracingService: {exc}")
            return None

    def _attach_callbacks_to_llm(self, callbacks: list[Any]) -> None:
        """Attach tracing callbacks to the LLM instance.

        Configures the LLM's default callbacks so that all invocations
        (including those within the agent workflow) are traced.
        """
        if self.llm is None:
            return

        try:
            # LangChain BaseChatModel supports a `callbacks` field
            if hasattr(self.llm, "callbacks"):
                existing = self.llm.callbacks or []
                self.llm.callbacks = list(existing) + callbacks
        except Exception as exc:
            logger.warning(f"Failed to attach tracing callbacks to LLM: {exc}")

    def _log_status(self) -> None:
        """Log the initialization status of the service container."""
        if not self._packages_available:
            logger.warning(
                "LangChain packages are not available. "
                "LLM-dependent features are disabled; retrieval-only endpoints remain operational."
            )
            return

        if self.llm is None:
            logger.warning(
                "LLM is not configured (KB_LLM_PROVIDER or KB_LLM_API_KEY missing). "
                "LLM-dependent features are disabled; retrieval-only endpoints remain operational."
            )
        else:
            logger.info(
                f"LangChain service container initialized: "
                f"provider={self.settings.llm_provider}, "
                f"model={self.settings.llm_model}, "
                f"tracing={'enabled' if self.tracing_service and self.tracing_service.is_enabled() else 'disabled'}"
            )


# ─── Module-level singleton ──────────────────────────────────────────────────

_service_container: ServiceContainer | None = None


def get_service_container() -> ServiceContainer:
    """Get or create the global ServiceContainer singleton.

    The container is created once on first access and reused for the
    lifetime of the application. This ensures settings are loaded once
    and the LLM/tracing are initialized once at startup.

    Returns:
        The global ServiceContainer instance.
    """
    global _service_container
    if _service_container is None:
        _service_container = ServiceContainer()
    return _service_container


def reset_service_container() -> None:
    """Reset the global ServiceContainer (for testing purposes).

    Forces re-initialization on next access.
    """
    global _service_container
    _service_container = None
