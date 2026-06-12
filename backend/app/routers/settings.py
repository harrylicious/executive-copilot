"""Settings router for managing per-user configuration."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user_settings import UserSettings
from app.schemas.settings import (
    ChatbotSettings,
    NotificationSettings,
    ProfileSettings,
    SecuritySettings,
    SettingsResponse,
    SettingsUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


def _build_response(record: UserSettings | None) -> SettingsResponse:
    """Build a SettingsResponse from a UserSettings record or defaults."""
    if record is None:
        return SettingsResponse()

    profile = ProfileSettings(**record.profile_json) if record.profile_json else None
    notifications = (
        NotificationSettings(**record.notifications_json) if record.notifications_json else None
    )
    chatbot = ChatbotSettings(**record.chatbot_json) if record.chatbot_json else None
    security = SecuritySettings(**record.security_json) if record.security_json else None

    return SettingsResponse(
        profile=profile,
        notifications=notifications,
        chatbot=chatbot,
        security=security,
    )


@router.get("/{user_id}", response_model=SettingsResponse)
def get_settings(user_id: int, db: Session = Depends(get_db)):
    """Return stored settings for a user, or defaults if none exist."""
    record = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()
    return _build_response(record)


@router.put("/{user_id}", response_model=SettingsResponse)
def update_settings(user_id: int, body: SettingsUpdate, db: Session = Depends(get_db)):
    """Upsert user settings. Only overwrites sections provided in the request."""
    record = db.query(UserSettings).filter(UserSettings.user_id == user_id).first()

    if record is None:
        record = UserSettings(user_id=user_id)
        db.add(record)

    # Only overwrite sections that are provided (non-None) in the request
    if body.profile is not None:
        record.profile_json = body.profile.model_dump(mode="python")
    if body.notifications is not None:
        record.notifications_json = body.notifications.model_dump(mode="python")
    if body.chatbot is not None:
        record.chatbot_json = body.chatbot.model_dump(mode="python")
    if body.security is not None:
        record.security_json = body.security.model_dump(mode="python")

    db.commit()
    db.refresh(record)

    return _build_response(record)
