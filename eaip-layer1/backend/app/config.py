"""Application configuration using pydantic-settings."""

import logging

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """KB Manager application settings.

    All settings can be overridden via environment variables
    prefixed with KB_ (e.g., KB_APP_PORT=9000).
    """

    app_port: int = 8000
    database_url: str = "sqlite:///./kb_manager.db"
    knowledge_base_path: str = "./knowledge_base"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_prefix = "KB_"


class GraphRAGSettings(BaseSettings):
    """GraphRAG-specific settings, all with KB_ prefix.

    Controls embedding generation, retrieval, entity extraction,
    and community detection parameters.
    """

    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 512
    chunk_overlap: int = 50
    vector_store_path: str = "./chroma_db"

    # Retrieval settings
    top_k: int = 5
    max_context_tokens: int = 2048
    similarity_weight: float = 0.7
    graph_relevance_weight: float = 0.3
    min_similarity_threshold: float = 0.5

    # Entity extraction
    entity_extraction_method: str = "rule-based"

    # Community detection
    community_resolution: float = 1.0
    max_community_size: int = 100

    class Config:
        env_prefix = "KB_"

    @field_validator("chunk_size", mode="before")
    @classmethod
    def validate_chunk_size(cls, v: object) -> int:
        """Validate chunk_size is within 64-4096. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid chunk_size value '{v}' (not an integer), using default 512"
            )
            return 512
        if not (64 <= v_int <= 4096):
            logger.warning(
                f"Invalid chunk_size {v_int} (must be 64-4096), using default 512"
            )
            return 512
        return v_int

    @field_validator("chunk_overlap", mode="before")
    @classmethod
    def validate_chunk_overlap(cls, v: object) -> int:
        """Validate chunk_overlap is within 0 to chunk_size//2.

        Note: cross-field validation with chunk_size is handled in the
        model_validator below since field_validator cannot access other fields
        in Pydantic v2.
        """
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid chunk_overlap value '{v}' (not an integer), using default 50"
            )
            return 50
        if v_int < 0:
            logger.warning(
                f"Invalid chunk_overlap {v_int} (must be >= 0), using default 50"
            )
            return 50
        return v_int

    @field_validator("top_k", mode="before")
    @classmethod
    def validate_top_k(cls, v: object) -> int:
        """Validate top_k is within 1-100. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid top_k value '{v}' (not an integer), using default 5"
            )
            return 5
        if not (1 <= v_int <= 100):
            logger.warning(
                f"Invalid top_k {v_int} (must be 1-100), using default 5"
            )
            return 5
        return v_int

    @field_validator("max_context_tokens", mode="before")
    @classmethod
    def validate_max_context_tokens(cls, v: object) -> int:
        """Validate max_context_tokens is within 256-16384. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid max_context_tokens value '{v}' (not an integer), using default 2048"
            )
            return 2048
        if not (256 <= v_int <= 16384):
            logger.warning(
                f"Invalid max_context_tokens {v_int} (must be 256-16384), using default 2048"
            )
            return 2048
        return v_int

    @field_validator("community_resolution", mode="before")
    @classmethod
    def validate_community_resolution(cls, v: object) -> float:
        """Validate community_resolution is within 0.1-10.0. Apply default on failure."""
        try:
            v_float = float(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid community_resolution value '{v}' (not a number), using default 1.0"
            )
            return 1.0
        if not (0.1 <= v_float <= 10.0):
            logger.warning(
                f"Invalid community_resolution {v_float} (must be 0.1-10.0), using default 1.0"
            )
            return 1.0
        return v_float

    @field_validator("max_community_size", mode="before")
    @classmethod
    def validate_max_community_size(cls, v: object) -> int:
        """Validate max_community_size is within 2-10000. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid max_community_size value '{v}' (not an integer), using default 100"
            )
            return 100
        if not (2 <= v_int <= 10000):
            logger.warning(
                f"Invalid max_community_size {v_int} (must be 2-10000), using default 100"
            )
            return 100
        return v_int

    @field_validator("entity_extraction_method", mode="before")
    @classmethod
    def validate_entity_extraction_method(cls, v: object) -> str:
        """Validate entity_extraction_method is 'rule-based' or 'llm-based'."""
        v_str = str(v).strip().lower()
        allowed = {"rule-based", "llm-based"}
        if v_str not in allowed:
            logger.warning(
                f"Invalid entity_extraction_method '{v}' "
                f"(must be one of {allowed}), using default 'rule-based'"
            )
            return "rule-based"
        return v_str

    @model_validator(mode="after")
    def validate_chunk_overlap_against_chunk_size(self) -> "GraphRAGSettings":
        """Ensure chunk_overlap does not exceed chunk_size // 2."""
        max_overlap = self.chunk_size // 2
        if self.chunk_overlap > max_overlap:
            logger.warning(
                f"Invalid chunk_overlap {self.chunk_overlap} "
                f"(must be <= chunk_size//2 = {max_overlap}), using default 50"
            )
            object.__setattr__(self, "chunk_overlap", 50)
        return self


settings = Settings()
graphrag_settings = GraphRAGSettings()
