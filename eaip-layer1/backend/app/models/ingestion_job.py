"""IngestionJob SQLAlchemy model for tracking document ingestion pipeline progress."""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey

from app.database import Base


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)  # UUID
    file_name = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    department = Column(String, nullable=False)
    subfolder = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued")
    # Status values: queued, validating, preprocessing, chunking, embedding,
    #                completed, failed, validation_failed, duplicate_exact,
    #                duplicate_near, access_denied
    current_stage = Column(String, nullable=True)
    error_code = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    failure_stage = Column(String, nullable=True)
    staging_path = Column(String, nullable=True)
    content_hash = Column(String, nullable=True)
    duplicate_of_file_id = Column(Integer, ForeignKey("files.id"), nullable=True)
    sensitivity_level = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=True)  # Set on completion
