"""File SQLAlchemy model for storing indexed file metadata."""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Boolean, Text

from app.database import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False, unique=True)
    department = Column(String, nullable=False)
    subfolder = Column(String, nullable=True)
    file_type = Column(String, nullable=True)
    size = Column(Integer, nullable=False)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, nullable=False)
    modified_at = Column(DateTime, nullable=False)
    indexed_at = Column(DateTime, nullable=True)
    content_hash = Column(String, nullable=True)
    checksum_md5 = Column(String, nullable=True)
    sync_status = Column(String, nullable=True, default="synced")
    sensitivity_level = Column(String, nullable=True, default="Internal")
    extracted_text = Column(Text, nullable=True)
    is_deleted = Column(Boolean, default=False)
    embedding_status = Column(String, nullable=True, default=None)
