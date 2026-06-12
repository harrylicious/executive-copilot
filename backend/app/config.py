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


class TurboVecSettings(BaseSettings):
    """TurboVec and routing configuration with KB_ prefix.

    Controls chunking, retrieval top-k values, index paths,
    and embedding model configuration. All integer fields
    validate their range and fall back to defaults with a
    warning log on invalid values.
    """

    # Chunking
    chunk_size: int = 600
    chunk_overlap: int = 80

    # Retrieval
    master_top_k: int = 20
    dept_top_k: int = 5
    master_first_supplement_k: int = 2

    # Paths
    index_cache_dir: str = "./index_cache"
    master_dir: str = "master"

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"

    class Config:
        env_prefix = "KB_"

    @field_validator("chunk_size", mode="before")
    @classmethod
    def validate_chunk_size(cls, v: object) -> int:
        """Validate chunk_size is a positive integer. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid chunk_size value '{v}' (not an integer), using default 600"
            )
            return 600
        if v_int < 1:
            logger.warning(
                f"Invalid chunk_size {v_int} (must be >= 1), using default 600"
            )
            return 600
        return v_int

    @field_validator("chunk_overlap", mode="before")
    @classmethod
    def validate_chunk_overlap(cls, v: object) -> int:
        """Validate chunk_overlap is a non-negative integer.

        Note: cross-field validation with chunk_size is handled in the
        model_validator below since field_validator cannot access other fields
        in Pydantic v2.
        """
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid chunk_overlap value '{v}' (not an integer), using default 80"
            )
            return 80
        if v_int < 0:
            logger.warning(
                f"Invalid chunk_overlap {v_int} (must be >= 0), using default 80"
            )
            return 80
        return v_int

    @field_validator("master_top_k", mode="before")
    @classmethod
    def validate_master_top_k(cls, v: object) -> int:
        """Validate master_top_k is within 1-100. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid master_top_k value '{v}' (not an integer), using default 8"
            )
            return 8
        if not (1 <= v_int <= 100):
            logger.warning(
                f"Invalid master_top_k {v_int} (must be 1-100), using default 8"
            )
            return 8
        return v_int

    @field_validator("dept_top_k", mode="before")
    @classmethod
    def validate_dept_top_k(cls, v: object) -> int:
        """Validate dept_top_k is within 1-100. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid dept_top_k value '{v}' (not an integer), using default 5"
            )
            return 5
        if not (1 <= v_int <= 100):
            logger.warning(
                f"Invalid dept_top_k {v_int} (must be 1-100), using default 5"
            )
            return 5
        return v_int

    @field_validator("master_first_supplement_k", mode="before")
    @classmethod
    def validate_master_first_supplement_k(cls, v: object) -> int:
        """Validate master_first_supplement_k is within 0-100. Apply default on failure."""
        try:
            v_int = int(v)
        except (TypeError, ValueError):
            logger.warning(
                f"Invalid master_first_supplement_k value '{v}' (not an integer), using default 2"
            )
            return 2
        if not (0 <= v_int <= 100):
            logger.warning(
                f"Invalid master_first_supplement_k {v_int} (must be 0-100), using default 2"
            )
            return 2
        return v_int

    @model_validator(mode="after")
    def validate_chunk_overlap_against_chunk_size(self) -> "TurboVecSettings":
        """Ensure chunk_overlap does not exceed chunk_size // 2."""
        max_overlap = self.chunk_size // 2
        if self.chunk_overlap > max_overlap:
            logger.warning(
                f"Invalid chunk_overlap {self.chunk_overlap} "
                f"(must be <= chunk_size//2 = {max_overlap}), using default 80"
            )
            object.__setattr__(self, "chunk_overlap", 80)
        return self


class IngestionSettings(BaseSettings):
    """Ingestion pipeline settings.

    Controls file upload limits, staging, OCR, PII redaction,
    deduplication, and chunking parameters.
    """

    max_file_size_mb: int = 100
    staging_path: str = "./staging"
    supported_formats: list[str] = [
        ".txt",
        ".md",
        ".json",
        ".docx",
        ".pdf",
        ".csv",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".tiff",
    ]
    ocr_provider: str = "tesseract"  # "tesseract" or "textract"
    ocr_confidence_threshold: float = 0.6
    pii_confidence_threshold: float = 0.7
    dedup_similarity_threshold: float = 0.9
    semantic_chunk_min_tokens: int = 256
    semantic_chunk_max_tokens: int = 1024
    sliding_window_size: int = 512
    sliding_window_overlap: int = 64
    sliding_window_min_chunk: int = 128
    job_retention_days: int = 30
    max_concurrent_uploads: int = 10

    class Config:
        env_prefix = "KB_INGESTION_"


settings = Settings()
turbovec_settings = TurboVecSettings()
ingestion_settings = IngestionSettings()
