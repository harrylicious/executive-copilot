"""FileVersion SQLAlchemy model for storing file version history."""

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from app.database import Base


class FileVersion(Base):
    __tablename__ = "file_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content_hash = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)  # UTC
    archive_path = Column(String, nullable=False)  # Path to stored content snapshot
    is_restore = Column(Boolean, default=False)
    restored_from_version = Column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("file_id", "version_number", name="uq_file_version"),
    )
