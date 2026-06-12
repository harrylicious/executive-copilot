"""LangChain integration package.

Provides LLM-powered generation, entity extraction, agentic workflows,
and observability on top of the existing retrieval pipeline.

At import time, this module validates that all required LangChain packages
are available, logs their versions on success, and exposes a boolean flag
`LANGCHAIN_AVAILABLE` indicating whether LLM features can be used.
"""

import logging

logger = logging.getLogger(__name__)

# Required packages and their import names
_REQUIRED_PACKAGES = [
    ("langchain", "langchain"),
    ("langchain-openai", "langchain_openai"),
    ("langgraph", "langgraph"),
    ("langsmith", "langsmith"),
]

LANGCHAIN_AVAILABLE: bool = True
"""Flag indicating whether all required LangChain packages are importable.

When True, LLM-dependent features (generation, LLM entity extraction,
agent workflows) are available. When False, only retrieval-only features
remain operational.
"""


def _check_langchain_packages() -> bool:
    """Attempt to import each required LangChain package.

    Logs the package name and version for each successfully imported package.
    If any package fails to import, logs an error and returns False.

    Returns:
        True if all required packages imported successfully, False otherwise.
    """
    all_available = True

    for package_name, import_name in _REQUIRED_PACKAGES:
        try:
            mod = __import__(import_name)
            version = getattr(mod, "__version__", "unknown")
            logger.info(
                f"LangChain package '{package_name}' loaded successfully "
                f"(version: {version})"
            )
        except ImportError as exc:
            logger.error(
                f"Failed to import required LangChain package '{package_name}': {exc}. "
                f"LLM features will be unavailable."
            )
            all_available = False

    return all_available


# Run availability check on package import
LANGCHAIN_AVAILABLE = _check_langchain_packages()

if not LANGCHAIN_AVAILABLE:
    logger.warning(
        "One or more LangChain packages are missing. "
        "LLM-dependent features are disabled; retrieval-only endpoints remain operational."
    )
