"""Retrieval service factory and dependency management.

Provides a centralized factory to create RetrievalService instances
with properly initialized TurboVecStore and QueryRouter components.
The store and router are cached as module-level singletons after first
initialization.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.config import turbovec_settings
from app.services.query_router import QueryRouter
from app.services.retrieval_service import RetrievalService

if TYPE_CHECKING:
    from app.services.turbovec_store import TurboVecStore

logger = logging.getLogger(__name__)

# Module-level singletons
_store: TurboVecStore | None = None
_router: QueryRouter | None = None
_retrieval_service: RetrievalService | None = None


def get_store() -> "TurboVecStore":
    """Get or create the global TurboVecStore singleton.

    On first call, initializes the TurboVecStore with the configured
    embedding model and attempts to load indexes from cache. If cache
    is not available, indexes will be empty until built by the lifespan.

    Returns:
        The global TurboVecStore instance.
    """
    global _store
    if _store is None:
        from app.services.embedding_model import EmbeddingModel
        from app.services.turbovec_store import TurboVecStore

        embedding_model = EmbeddingModel(turbovec_settings.embedding_model)
        _store = TurboVecStore(turbovec_settings, embedding_model)

        # Try to load from cache
        loaded = _store.load_from_cache()
        if loaded:
            logger.info("TurboVecStore loaded indexes from cache")
        else:
            logger.info(
                "TurboVecStore cache not found or failed to load. "
                "Indexes will be built during application startup."
            )
    return _store


def get_router() -> QueryRouter:
    """Get or create the global QueryRouter singleton.

    Returns:
        The global QueryRouter instance.
    """
    global _router
    if _router is None:
        _router = QueryRouter(turbovec_settings)
    return _router


def get_retrieval_service() -> RetrievalService:
    """Get or create the global RetrievalService singleton.

    Wires together TurboVecStore, QueryRouter, and config into
    a ready-to-use RetrievalService instance.

    Returns:
        The global RetrievalService instance.
    """
    global _retrieval_service
    if _retrieval_service is None:
        store = get_store()
        router = get_router()
        _retrieval_service = RetrievalService(
            store=store,
            router=router,
            config=turbovec_settings,
        )
    return _retrieval_service


def set_store(store: "TurboVecStore") -> None:
    """Set the global TurboVecStore instance.

    Used by the application lifespan to inject a fully-initialized store
    after indexes have been built or loaded from cache.

    Args:
        store: A fully-initialized TurboVecStore instance.
    """
    global _store, _retrieval_service
    _store = store
    # Invalidate the cached retrieval service so it picks up the new store
    _retrieval_service = None


def reset_dependencies() -> None:
    """Reset all cached singleton instances.

    Primarily used in tests to ensure clean state between test runs.
    """
    global _store, _router, _retrieval_service
    _store = None
    _router = None
    _retrieval_service = None
