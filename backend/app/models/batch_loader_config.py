"""BatchLoaderConfig SQLAlchemy model for scheduled batch ingestion configurations."""

from sqlalchemy import Column, String, DateTime, Boolean

from app.database import Base


class BatchLoaderConfig(Base):
    __tablename__ = "batch_loader_configs"

    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)
    source_path = Column(String, nullable=False)  # Local path or S3 URI
    source_type = Column(String, nullable=False)  # "local" or "s3"
    cron_expression = Column(String, nullable=False)
    department = Column(String, nullable=False)
    subfolder = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    last_execution_at = Column(DateTime, nullable=True)
    last_execution_status = Column(String, nullable=True)
