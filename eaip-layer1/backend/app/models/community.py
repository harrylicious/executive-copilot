"""Community SQLAlchemy model for storing entity community clusters and summaries."""

from sqlalchemy import Column, Integer, String, JSON

from app.database import Base


class Community(Base):
    __tablename__ = "communities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    level = Column(Integer, nullable=False)  # Hierarchy depth, starting at 0
    member_entity_ids = Column(JSON, nullable=False, default=list)  # [entity_id, ...]
    summary = Column(String(5000), nullable=True)
    summary_embedding = Column(JSON, nullable=True)  # For global search comparison
