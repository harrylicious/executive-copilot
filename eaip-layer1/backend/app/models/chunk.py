"""Chunk SQLAlchemy model for storing document text segments and their embeddings."""

from sqlalchemy import Column, Integer, String, ForeignKey, JSON, UniqueConstraint

from app.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(String(10000), nullable=False)
    start_offset = Column(Integer, nullable=False)
    end_offset = Column(Integer, nullable=False)
    embedding = Column(JSON, nullable=True)  # JSON-serialized float array

    __table_args__ = (
        UniqueConstraint("file_id", "chunk_index", name="uq_file_chunk_index"),
    )
