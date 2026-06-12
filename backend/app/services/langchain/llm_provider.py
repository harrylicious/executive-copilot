"""LLM provider factory for LangChain integration.

Creates the appropriate LangChain ChatModel instance based on configuration.
Supports OpenAI and Azure OpenAI providers. Returns None with a logged warning
if configuration is invalid, missing, or if required packages are unavailable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel

from app.services.langchain.config import LangChainSettings

logger = logging.getLogger(__name__)


def create_llm(settings: LangChainSettings) -> "BaseChatModel | None":
    """Factory function to create the configured LLM instance.

    Checks that the LLM is configured via settings, then instantiates the
    appropriate LangChain ChatModel based on the provider name.

    Args:
        settings: LangChainSettings instance with provider configuration.

    Returns:
        A BaseChatModel instance for the configured provider, or None if
        configuration is invalid/missing or required packages are unavailable.
    """
    if not settings.is_llm_configured():
        logger.warning(
            "LLM is not configured (missing llm_provider or llm_api_key). "
            "LLM-dependent features will be disabled."
        )
        return None

    provider = settings.llm_provider.lower()

    if provider == "openai":
        return _create_openai(settings)
    elif provider == "azure_openai":
        return _create_azure_openai(settings)
    else:
        logger.warning(
            f"Unknown LLM provider '{settings.llm_provider}'. "
            f"Supported providers are: 'openai', 'azure_openai'. "
            f"LLM-dependent features will be disabled."
        )
        return None


def _create_openai(settings: LangChainSettings) -> "BaseChatModel | None":
    """Instantiate ChatOpenAI with the given settings.

    Returns None and logs a warning if langchain-openai is not installed.
    """
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.warning(
            "langchain-openai package is not available. "
            "Cannot create OpenAI LLM instance. "
            "Install it with: pip install langchain-openai"
        )
        return None

    return ChatOpenAI(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.llm_api_key,
    )


def _create_azure_openai(settings: LangChainSettings) -> "BaseChatModel | None":
    """Instantiate AzureChatOpenAI with the given settings.

    Requires azure_openai_endpoint and azure_openai_api_version in addition
    to the common LLM settings. Returns None and logs a warning if the
    endpoint is missing or langchain-openai is not installed.
    """
    if not settings.azure_openai_endpoint:
        logger.warning(
            "Azure OpenAI endpoint (KB_AZURE_OPENAI_ENDPOINT) is not configured. "
            "Cannot create Azure OpenAI LLM instance. "
            "LLM-dependent features will be disabled."
        )
        return None

    try:
        from langchain_openai import AzureChatOpenAI
    except ImportError:
        logger.warning(
            "langchain-openai package is not available. "
            "Cannot create Azure OpenAI LLM instance. "
            "Install it with: pip install langchain-openai"
        )
        return None

    return AzureChatOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_version=settings.azure_openai_api_version,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        api_key=settings.llm_api_key,
    )
