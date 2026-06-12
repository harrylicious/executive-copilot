"""EmbeddingLog SQLAlchemy model for recording embedding job history."""

from sqlalchemy import Column, Integer, String, DateTime

from app.database import Base


class EmbeddingLog(Base):
    __tablename__ = "embedding_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    files_processed = Column(Integer, default=0)
    chunks_generated = Column(Integer, default=0)
    errors_count = Column(Integer, default=0)
    status = Column(String, nullable=False)  # "pending", "running", "completed", "failed"
