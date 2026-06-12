"""Pydantic schemas for user settings API requests and responses."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


def _to_camel(field_name: str) -> str:
    """Convert a snake_case field name to camelCase for JSON serialization."""
    parts = field_name.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class ProfileSettings(BaseModel):
    """Profile section of user settings."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    name: str | None = None
    email: str | None = None
    phone: str | None = None
    bio: str | None = None
    avatar: str | None = None


class NotificationSettings(BaseModel):
    """Notification preferences section."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    email_notifications: bool = True
    push_notifications: bool = True
    weekly_digest: bool = False


class ChatbotSettings(BaseModel):
    """Chatbot configuration section."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    language: Literal["id", "en"] = "id"
    nuance: str = ""
    restrict_cross_dept: bool = False


class SecuritySettings(BaseModel):
    """Security preferences section."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    two_factor_enabled: bool = False
    session_timeout: int = 30  # minutes


class SettingsResponse(BaseModel):
    """Full settings response returned by GET /api/settings/{user_id}."""

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    profile: ProfileSettings | None = None
    notifications: NotificationSettings | None = None
    chatbot: ChatbotSettings | None = None
    security: SecuritySettings | None = None


class SettingsUpdate(BaseModel):
    """Partial settings update payload for PUT /api/settings/{user_id}.

    All sections are optional — only provided sections will be updated.
    """

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )

    profile: ProfileSettings | None = None
    notifications: NotificationSettings | None = None
    chatbot: ChatbotSettings | None = None
    security: SecuritySettings | None = None
