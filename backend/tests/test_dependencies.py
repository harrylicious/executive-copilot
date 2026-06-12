"""Unit tests for the LangChain service container (dependencies module).

Tests graceful degradation, singleton behavior, and tracing callback attachment.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

from app.services.langchain.dependencies import (
    ServiceContainer,
    get_service_container,
    reset_service_container,
)


class TestServiceContainerGracefulDegradation:
    """Test graceful degradation when LLM is not configured."""

    def setup_method(self):
        """Reset the singleton before each test."""
        reset_service_container()

    def teardown_method(self):
        """Reset the singleton after each test."""
        reset_service_container()

    def test_llm_unavailable_when_not_configured(self):
        """When no LLM provider is configured, is_llm_available should be False."""
        # Default env has no KB_LLM_PROVIDER or KB_LLM_API_KEY
        container = ServiceContainer()
        assert container.is_llm_available is False

    def test_session_store_always_initialized(self):
        """SessionStore should be available even when LLM is not configured."""
        container = ServiceContainer()
        assert container.session_store is not None

    def test_tracing_service_none_when_llm_unavailable(self):
        """TracingService should not be created when LLM is unavailable."""
        container = ServiceContainer()
        assert container.tracing_service is None

    def test_packages_available_flag(self):
        """packages_available should reflect LANGCHAIN_AVAILABLE."""
        container = ServiceContainer()
        # Since we have langchain installed in the test env
        assert container._packages_available is True

    def test_build_workflow_raises_when_llm_unavailable(self):
        """build_workflow should raise RuntimeError when LLM is not available."""
        container = ServiceContainer()
        db_mock = MagicMock()
        with pytest.raises(RuntimeError, match="LLM is not available"):
            container.build_workflow(db=db_mock)

    def test_build_rag_chain_raises_when_llm_unavailable(self):
        """build_rag_chain should raise RuntimeError when LLM is not available."""
        container = ServiceContainer()
        db_mock = MagicMock()
        with pytest.raises(RuntimeError, match="LLM is not available"):
            container.build_rag_chain(db=db_mock)

    def test_get_tracing_callbacks_empty_when_no_tracing(self):
        """get_tracing_callbacks should return empty list when tracing is disabled."""
        container = ServiceContainer()
        assert container.get_tracing_callbacks() == []


class TestServiceContainerSingleton:
    """Test singleton behavior of get_service_container."""

    def setup_method(self):
        reset_service_container()

    def teardown_method(self):
        reset_service_container()

    def test_singleton_returns_same_instance(self):
        """get_service_container should return the same instance on repeated calls."""
        c1 = get_service_container()
        c2 = get_service_container()
        assert c1 is c2

    def test_reset_creates_new_instance(self):
        """After reset, get_service_container should create a new instance."""
        c1 = get_service_container()
        reset_service_container()
        c2 = get_service_container()
        assert c1 is not c2


class TestServiceContainerWithLLM:
    """Test container behavior when LLM is configured."""

    def setup_method(self):
        reset_service_container()

    def teardown_method(self):
        reset_service_container()
        # Clean up env vars
        for key in ["KB_LLM_PROVIDER", "KB_LLM_API_KEY", "KB_LANGSMITH_API_KEY"]:
            os.environ.pop(key, None)

    @patch.dict(os.environ, {"KB_LLM_PROVIDER": "openai", "KB_LLM_API_KEY": "test-key"})
    def test_llm_available_when_configured(self):
        """When LLM provider and key are set, is_llm_available should be True."""
        container = ServiceContainer()
        assert container.is_llm_available is True
        assert container.llm is not None

    @patch.dict(os.environ, {
        "KB_LLM_PROVIDER": "openai",
        "KB_LLM_API_KEY": "test-key",
        "KB_LANGSMITH_API_KEY": "ls-test-key",
    })
    def test_tracing_service_created_when_llm_and_langsmith_configured(self):
        """TracingService should be created when both LLM and LangSmith are configured."""
        container = ServiceContainer()
        assert container.tracing_service is not None
        assert container.tracing_service.is_enabled() is True

    @patch.dict(os.environ, {
        "KB_LLM_PROVIDER": "openai",
        "KB_LLM_API_KEY": "test-key",
        "KB_LANGSMITH_API_KEY": "ls-test-key",
    })
    def test_tracing_callbacks_returned_when_enabled(self):
        """get_tracing_callbacks should return callbacks when tracing is enabled."""
        container = ServiceContainer()
        callbacks = container.get_tracing_callbacks()
        assert len(callbacks) > 0

    @patch.dict(os.environ, {"KB_LLM_PROVIDER": "openai", "KB_LLM_API_KEY": "test-key"})
    def test_tracing_callbacks_empty_when_no_langsmith_key(self):
        """get_tracing_callbacks should return empty list when LangSmith key is missing."""
        container = ServiceContainer()
        # TracingService is created but disabled (no langsmith key)
        callbacks = container.get_tracing_callbacks()
        assert callbacks == []

    @patch.dict(os.environ, {
        "KB_LLM_PROVIDER": "openai",
        "KB_LLM_API_KEY": "test-key",
        "KB_LANGSMITH_API_KEY": "ls-test-key",
    })
    def test_callbacks_attached_to_llm_on_build_workflow(self):
        """TracingService callbacks should be attached to LLM when building workflow."""
        container = ServiceContainer()

        # Verify LLM initially has no callbacks (or empty)
        initial_callbacks = container.llm.callbacks or []

        # Build workflow (will attach callbacks)
        db_mock = MagicMock()
        try:
            container.build_workflow(db=db_mock)
        except Exception:
            # May fail due to missing DB setup, but callbacks should be attached
            pass

        # After build_workflow, LLM should have tracing callbacks attached
        assert container.llm.callbacks is not None
        assert len(container.llm.callbacks) > len(initial_callbacks)


class TestServiceContainerPackagesUnavailable:
    """Test container behavior when LangChain packages are unavailable."""

    def setup_method(self):
        reset_service_container()

    def teardown_method(self):
        reset_service_container()

    @patch("app.services.langchain.dependencies.LANGCHAIN_AVAILABLE", False)
    def test_llm_unavailable_when_packages_missing(self):
        """When packages are missing, is_llm_available should be False."""
        container = ServiceContainer()
        assert container.is_llm_available is False
        assert container.llm is None

    @patch("app.services.langchain.dependencies.LANGCHAIN_AVAILABLE", False)
    def test_session_store_available_when_packages_missing(self):
        """SessionStore should still be available when packages are missing."""
        container = ServiceContainer()
        assert container.session_store is not None

    @patch("app.services.langchain.dependencies.LANGCHAIN_AVAILABLE", False)
    def test_build_workflow_raises_when_packages_missing(self):
        """build_workflow should raise RuntimeError when packages are missing."""
        container = ServiceContainer()
        db_mock = MagicMock()
        with pytest.raises(RuntimeError, match="LLM is not available"):
            container.build_workflow(db=db_mock)
