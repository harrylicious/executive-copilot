"""Relationship SQLAlchemy model for storing file-to-file connections."""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey

from app.database import Base


class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    target_file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    relationship_type = Column(String, nullable=False)  # "department", "tag", "manual"
    is_manual = Column(Boolean, default=False)
