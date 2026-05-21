"""SyncLog SQLAlchemy model for recording sync operation history."""

from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    files_added = Column(Integer, default=0)
    files_updated = Column(Integer, default=0)
    files_removed = Column(Integer, default=0)
    status = Column(String, nullable=False)  # "success", "error"
    summary = Column(String, nullable=True)
