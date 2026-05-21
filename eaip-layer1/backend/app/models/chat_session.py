"""SQLAlchemy models for persisting chat sessions and messages."""

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float
from sqlalchemy.sql import func

from app.database import Base


class ChatSession(Base):
    """A chat session (conversation thread) in the Playground."""

    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True)  # UUID from frontend
    title = Column(String, nullable=True)  # Auto-generated from first message
    retrieval_mode = Column(String, nullable=True, default="combined")
    top_k = Column(Integer, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class ChatMessageRecord(Base):
    """A single message within a chat session."""

    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True)  # UUID from frontend
    session_id = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False, default="")
    sources = Column(JSON, nullable=True)  # SourceAttribution[]
    metadata_json = Column(JSON, nullable=True)  # RetrievalMetadata
    error = Column(String, nullable=True)
    timestamp = Column(Float, nullable=False)  # epoch ms from frontend
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
