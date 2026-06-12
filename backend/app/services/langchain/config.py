"""LangChain integration configuration using pydantic-settings."""

import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class LangChainSettings(BaseSettings):
    """LangChain integration settings with KB_ prefix.

    Controls LLM provider configuration, Azure OpenAI settings,
    and LangSmith tracing parameters. Follows the same pattern
    as TurboVecSettings (BaseSettings with env_prefix="KB_",
    field validators that log warnings and apply defaults for
    invalid values).
    """

    # LLM Provider
    llm_provider: str = ""  # "openai" | "azure_openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7  # 0.0 - 2.0
    llm_max_tokens: int = 8000  # 1 - 32768
    llm_api_key: str = ""

    # Azure OpenAI-specific
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-01"

    # LangSmith
    langsmith_api_key: str = ""
    langsmith_project: str = "kb-copilot"
    langsmith_sample_rate: float = 1.0  # 0.0 - 1.0

    class Config:
        env_prefix = "KB_"

    @field_validator("llm_temperature", mode="before")
    @classmethod
    def validate_temperature(cls, v: object) -> float:
        """Validate llm_temperature is within 0.0-2.0. Apply default 0.7 on failure."""
        try:
            v_float = float(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid llm_temperature value '{v}' (not a number), using default 0.7"
            )
            return 0.7
        if not (0.0 <= v_float <= 2.0):
            logger.warning(
                f"Invalid llm_temperature {v_float} (must be 0.0-2.0), using default 0.7"
            )
            return 0.7
        return v_float

    @field_validator("llm_max_tokens", mode="before")
    @classmethod
    def validate_max_tokens(cls, v: object) -> int:
        """Validate llm_max_tokens is within 1-32768. Apply default 1024 on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid llm_max_tokens value '{v}' (not an integer), using default 1024"
            )
            return 1024
        if not (1 <= v_int <= 32768):
            logger.warning(
                f"Invalid llm_max_tokens {v_int} (must be 1-32768), using default 1024"
            )
            return 1024
        return v_int

    @field_validator("langsmith_sample_rate", mode="before")
    @classmethod
    def validate_sample_rate(cls, v: object) -> float:
        """Validate langsmith_sample_rate is within 0.0-1.0. Clamp to nearest bound."""
        try:
            v_float = float(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid langsmith_sample_rate value '{v}' (not a number), using default 1.0"
            )
            return 1.0
        if v_float < 0.0:
            logger.warning(
                f"Invalid langsmith_sample_rate {v_float} (must be 0.0-1.0), "
                f"clamping to 0.0"
            )
            return 0.0
        if v_float > 1.0:
            logger.warning(
                f"Invalid langsmith_sample_rate {v_float} (must be 0.0-1.0), "
                f"clamping to 1.0"
            )
            return 1.0
        return v_float

    def is_llm_configured(self) -> bool:
        """Return True if LLM provider and API key are set.

        This indicates that LLM-dependent features (generation,
        LLM-based entity extraction, agent workflows) can be enabled.
        """
        return bool(self.llm_provider and self.llm_api_key)
