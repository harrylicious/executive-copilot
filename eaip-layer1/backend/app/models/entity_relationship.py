"""EntityRelationship SQLAlchemy model for storing semantic relationships between entities."""

from sqlalchemy import Column, Integer, String, Float, ForeignKey

from app.database import Base


class EntityRelationship(Base):
    __tablename__ = "entity_relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    target_entity_id = Column(Integer, ForeignKey("entities.id"), nullable=False, index=True)
    description = Column(String(2000), nullable=True)
    strength = Column(Float, nullable=False, default=0.5)
    source_chunk_id = Column(Integer, ForeignKey("chunks.id"), nullable=False)
