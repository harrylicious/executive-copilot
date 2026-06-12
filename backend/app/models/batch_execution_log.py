"""BatchExecutionLog SQLAlchemy model for recording batch loader execution results."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON

from app.database import Base


class BatchExecutionLog(Base):
    __tablename__ = "batch_execution_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    config_id = Column(
        String, ForeignKey("batch_loader_configs.id"), nullable=False, index=True
    )
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    files_found = Column(Integer, default=0)
    files_submitted = Column(Integer, default=0)
    files_skipped = Column(Integer, default=0)  # Already ingested
    errors = Column(JSON, nullable=True)
    status = Column(String, nullable=False)  # running, completed, failed
