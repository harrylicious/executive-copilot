"""Entity SQLAlchemy model for storing extracted named entities."""

from sqlalchemy import Column, Integer, String, JSON, UniqueConstraint

from app.database import Base


class Entity(Base):
    __tablename__ = "entities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(512), nullable=False)
    normalized_name = Column(String(512), nullable=False, index=True)
    entity_type = Column(String(128), nullable=False)
    description = Column(String(2000), nullable=True)
    source_chunk_ids = Column(JSON, nullable=False, default=list)  # [chunk_id, ...]

    __table_args__ = (
        UniqueConstraint("normalized_name", "entity_type", name="uq_entity_norm_type"),
    )
