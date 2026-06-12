"""IngestionStageLog SQLAlchemy model for recording pipeline stage transitions."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON

from app.database import Base


class IngestionStageLog(Base):
    __tablename__ = "ingestion_stage_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False)  # started, completed, failed
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    details = Column(JSON, nullable=True)  # Stage-specific metadata
