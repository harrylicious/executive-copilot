"""UserSettings SQLAlchemy model for storing per-user configuration as JSON."""

from datetime import datetime, timezone

from sqlalchemy import Column, Integer, DateTime, JSON

from app.database import Base


class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, unique=True, index=True, nullable=False)
    profile_json = Column(JSON, nullable=True)
    notifications_json = Column(JSON, nullable=True)
    chatbot_json = Column(JSON, nullable=True)
    security_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
