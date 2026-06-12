"""SQLAlchemy model for storing file-to-file relationships in the knowledge graph."""

from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.sql import func

from app.database import Base


class FileRelationship(Base):
    """A directional relationship between two files in the knowledge graph."""

    __tablename__ = "file_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, nullable=False, index=True)
    target_file_id = Column(Integer, nullable=False, index=True)
    relationship_type = Column(String, nullable=False)  # references, related_to, depends_on, supersedes, manual
    confidence = Column(Float, nullable=True)  # AI-generated confidence score
    created_at = Column(DateTime, server_default=func.now())
