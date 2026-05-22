"""PIIRedactionLog SQLAlchemy model for auditing PII redaction actions."""

from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey

from app.database import Base


class PIIRedactionLog(Base):
    __tablename__ = "pii_redaction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String, ForeignKey("ingestion_jobs.id"), nullable=False, index=True)
    category = Column(String, nullable=False)  # EMAIL, PHONE, NIK, NAME
    original_start = Column(Integer, nullable=False)
    original_end = Column(Integer, nullable=False)
    placeholder = Column(String, nullable=False)
    confidence = Column(Float, nullable=True)
    flagged_for_review = Column(Boolean, default=False)
