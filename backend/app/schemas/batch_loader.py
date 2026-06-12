"""Pydantic schemas for batch loader configuration and execution log API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(field_name: str) -> str:
    """Convert a snake_case field name to camelCase for JSON serialization."""
    parts = field_name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class BatchLoaderConfigCreate(BaseModel):
    """Request schema for creating a new batch loader configuration."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    name: str = Field(..., min_length=1, description="Human-readable name for the batch loader")
    source_path: str = Field(..., min_length=1, description="Local filesystem path or S3 URI")
    source_type: str = Field(..., pattern=r"^(local|s3)$", description="Source type: 'local' or 's3'")
    cron_expression: str = Field(..., min_length=1, description="Cron expression for scheduling")
    department: str = Field(..., min_length=1, description="Target department for ingested files")
    subfolder: str | None = Field(default=None, description="Target subfolder within the department")
    is_active: bool = Field(default=True, description="Whether the batch loader is active")


class BatchLoaderConfigUpdate(BaseModel):
    """Request schema for updating an existing batch loader configuration.

    All fields are optional; only provided fields will be updated.
    """

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    name: str | None = Field(default=None, min_length=1, description="Human-readable name for the batch loader")
    source_path: str | None = Field(default=None, min_length=1, description="Local filesystem path or S3 URI")
    source_type: str | None = Field(default=None, pattern=r"^(local|s3)$", description="Source type: 'local' or 's3'")
    cron_expression: str | None = Field(default=None, min_length=1, description="Cron expression for scheduling")
    department: str | None = Field(default=None, min_length=1, description="Target department for ingested files")
    subfolder: str | None = Field(default=None, description="Target subfolder within the department")
    is_active: bool | None = Field(default=None, description="Whether the batch loader is active")


class BatchLoaderConfigResponse(BaseModel):
    """Response schema for a batch loader configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: str
    name: str
    source_path: str
    source_type: str
    cron_expression: str
    department: str
    subfolder: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_execution_at: datetime | None = None
    last_execution_status: str | None = None
    next_execution_at: datetime | None = None


class BatchExecutionLogResponse(BaseModel):
    """Response schema for a batch loader execution log entry."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    id: int
    config_id: str
    started_at: datetime
    completed_at: datetime | None = None
    files_found: int = 0
    files_submitted: int = 0
    files_skipped: int = 0
    errors: list[dict] | None = None
    status: str
