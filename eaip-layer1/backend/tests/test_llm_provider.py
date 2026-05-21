"""Unit tests for the LLM provider factory."""

from unittest.mock import patch, MagicMock

import pytest

from app.services.langchain.config import LangChainSettings
from app.services.langchain.llm_provider import create_llm


class TestCreateLlm:
    """Tests for the create_llm factory function."""

    def test_returns_none_when_not_configured(self):
        """Returns None when LLM is not configured (no provider or api_key)."""
        settings = LangChainSettings(llm_provider="", llm_api_key="")
        result = create_llm(settings)
        assert result is None

    def test_returns_none_when_api_key_missing(self):
        """Returns None when provider is set but api_key is empty."""
        settings = LangChainSettings(llm_provider="openai", llm_api_key="")
        result = create_llm(settings)
        assert result is None

    def test_returns_none_for_unknown_provider(self):
        """Returns None for an unsupported provider name."""
        settings = LangChainSettings(
            llm_provider="anthropic", llm_api_key="sk-test-key"
        )
        result = create_llm(settings)
        assert result is None

    @patch("app.services.langchain.llm_provider._create_openai")
    def test_openai_provider_dispatches_correctly(self, mock_create):
        """Dispatches to _create_openai for 'openai' provider."""
        mock_create.return_value = MagicMock()
        settings = LangChainSettings(
            llm_provider="openai", llm_api_key="sk-test-key"
        )
        result = create_llm(settings)
        mock_create.assert_called_once_with(settings)
        assert result is not None

    @patch("app.services.langchain.llm_provider._create_azure_openai")
    def test_azure_openai_provider_dispatches_correctly(self, mock_create):
        """Dispatches to _create_azure_openai for 'azure_openai' provider."""
        mock_create.return_value = MagicMock()
        settings = LangChainSettings(
            llm_provider="azure_openai", llm_api_key="sk-test-key"
        )
        result = create_llm(settings)
        mock_create.assert_called_once_with(settings)
        assert result is not None

    @patch("app.services.langchain.llm_provider._create_openai")
    def test_provider_name_is_case_insensitive(self, mock_create):
        """Provider name matching is case-insensitive."""
        mock_create.return_value = MagicMock()
        settings = LangChainSettings(
            llm_provider="OpenAI", llm_api_key="sk-test-key"
        )
        result = create_llm(settings)
        mock_create.assert_called_once_with(settings)
        assert result is not None

    def test_logs_warning_when_not_configured(self, caplog):
        """Logs a warning when LLM is not configured."""
        settings = LangChainSettings(llm_provider="", llm_api_key="")
        with caplog.at_level("WARNING"):
            create_llm(settings)
        assert "LLM is not configured" in caplog.text

    def test_logs_warning_for_unknown_provider(self, caplog):
        """Logs a warning for unknown provider."""
        settings = LangChainSettings(
            llm_provider="unknown", llm_api_key="sk-test-key"
        )
        with caplog.at_level("WARNING"):
            create_llm(settings)
        assert "Unknown LLM provider" in caplog.text


class TestCreateOpenAI:
    """Tests for the OpenAI provider creation."""

    def test_creates_chat_openai_with_correct_params(self):
        """Creates ChatOpenAI with model, temperature, max_tokens, api_key."""
        from app.services.langchain.llm_provider import _create_openai

        settings = LangChainSettings(
            llm_provider="openai",
            llm_model="gpt-4o",
            llm_temperature=0.5,
            llm_max_tokens=2048,
            llm_api_key="sk-test-key",
        )

        mock_cls = MagicMock()
        with patch(
            "app.services.langchain.llm_provider.ChatOpenAI",
            mock_cls,
            create=True,
        ):
            # Need to patch the import inside the function
            pass

        # Use a different approach: mock the import mechanism
        mock_module = MagicMock()
        mock_chat_openai_cls = MagicMock()
        mock_module.ChatOpenAI = mock_chat_openai_cls

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def custom_import(name, *args, **kwargs):
            if name == "langchain_openai":
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=custom_import):
            result = _create_openai(settings)

        mock_chat_openai_cls.assert_called_once_with(
            model="gpt-4o",
            temperature=0.5,
            max_tokens=2048,
            api_key="sk-test-key",
        )
        assert result is not None

    def test_returns_none_when_langchain_openai_not_installed(self):
        """Returns None when langchain_openai cannot be imported."""
        from app.services.langchain.llm_provider import _create_openai

        settings = LangChainSettings(
            llm_provider="openai",
            llm_api_key="sk-test-key",
        )

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def custom_import(name, *args, **kwargs):
            if name == "langchain_openai":
                raise ImportError("no module named langchain_openai")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=custom_import):
            result = _create_openai(settings)
        assert result is None


class TestCreateAzureOpenAI:
    """Tests for the Azure OpenAI provider creation."""

    def test_returns_none_when_endpoint_missing(self):
        """Returns None when azure_openai_endpoint is not set."""
        from app.services.langchain.llm_provider import _create_azure_openai

        settings = LangChainSettings(
            llm_provider="azure_openai",
            llm_api_key="sk-test-key",
            azure_openai_endpoint="",
        )
        result = _create_azure_openai(settings)
        assert result is None

    def test_logs_warning_when_endpoint_missing(self, caplog):
        """Logs a warning when Azure endpoint is missing."""
        from app.services.langchain.llm_provider import _create_azure_openai

        settings = LangChainSettings(
            llm_provider="azure_openai",
            llm_api_key="sk-test-key",
            azure_openai_endpoint="",
        )
        with caplog.at_level("WARNING"):
            _create_azure_openai(settings)
        assert "Azure OpenAI endpoint" in caplog.text

    def test_creates_azure_chat_openai_with_correct_params(self):
        """Creates AzureChatOpenAI with endpoint, api_version, model, etc."""
        from app.services.langchain.llm_provider import _create_azure_openai

        settings = LangChainSettings(
            llm_provider="azure_openai",
            llm_model="gpt-4o",
            llm_temperature=0.3,
            llm_max_tokens=4096,
            llm_api_key="sk-azure-key",
            azure_openai_endpoint="https://my-endpoint.openai.azure.com",
            azure_openai_api_version="2024-02-01",
        )

        mock_module = MagicMock()
        mock_azure_cls = MagicMock()
        mock_module.AzureChatOpenAI = mock_azure_cls

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def custom_import(name, *args, **kwargs):
            if name == "langchain_openai":
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=custom_import):
            result = _create_azure_openai(settings)

        mock_azure_cls.assert_called_once_with(
            azure_endpoint="https://my-endpoint.openai.azure.com",
            api_version="2024-02-01",
            model="gpt-4o",
            temperature=0.3,
            max_tokens=4096,
            api_key="sk-azure-key",
        )
        assert result is not None

    def test_returns_none_when_langchain_openai_not_installed(self):
        """Returns None when langchain_openai cannot be imported."""
        from app.services.langchain.llm_provider import _create_azure_openai

        settings = LangChainSettings(
            llm_provider="azure_openai",
            llm_api_key="sk-test-key",
            azure_openai_endpoint="https://my-endpoint.openai.azure.com",
        )

        original_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

        def custom_import(name, *args, **kwargs):
            if name == "langchain_openai":
                raise ImportError("no module named langchain_openai")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=custom_import):
            result = _create_azure_openai(settings)
        assert result is None
