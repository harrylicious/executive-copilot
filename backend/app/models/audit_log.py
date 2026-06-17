"""AuditLog SQLAlchemy model for recording system actions."""

from sqlalchemy import Column, ForeignKey, Integer, JSON, String

from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String, nullable=False)  # ISO 8601 with ms precision
    event_type = Column(String, nullable=False)  # AuditEventType value
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    actor = Column(String, nullable=False, default="system")
    details = Column(JSON, nullable=True)  # Additional context as JSON
