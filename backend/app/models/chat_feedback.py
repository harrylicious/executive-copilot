"""SQLAlchemy model for chat message feedback (like/dislike)."""

from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.sql import func

from app.database import Base


class ChatFeedback(Base):
    """User feedback on an assistant message."""

    __tablename__ = "chat_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String, nullable=False, index=True)  # ID of the assistant message
    session_id = Column(String, nullable=True, index=True)  # Chat session ID
    rating = Column(String, nullable=False)  # "like" or "dislike"
    reason = Column(Text, nullable=True)  # User-provided reason (for dislike)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
