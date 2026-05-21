"""ChromaDB vector store service for embedding storage and similarity search.

Provides persistent vector storage using ChromaDB with cosine similarity,
supporting upsert, deletion by file, and filtered similarity search operations.
"""

import logging

import chromadb

from app.config import GraphRAGSettings
from app.services.document_chunker import ChunkResult

logger = logging.getLogger(__name__)


class ChromaVectorStore:
    """Persistent vector store using ChromaDB.

    Manages storage and retrieval of chunk embeddings with metadata filtering.
    Uses cosine similarity for nearest-neighbor search.

    Args:
        config: GraphRAGSettings instance with vector_store_path configuration.
    """

    def __init__(self, config: GraphRAGSettings):
        try:
            self.client = chromadb.PersistentClient(path=config.vector_store_path)
            self.collection = self.client.get_or_create_collection(
                name="kb_chunks",
                metadata={"hnsw:space": "cosine"},
            )
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB vector store: {e}")
            raise

    def upsert_chunks(
        self,
        file_id: int,
        chunks: list[ChunkResult],
        embeddings: list[list[float]],
        metadata: dict,
    ) -> None:
        """Store chunk embeddings with metadata. Replaces existing for file_id.

        First deletes any existing embeddings for the given file_id, then
        inserts the new chunks with their embeddings and metadata.

        Args:
            file_id: The database ID of the source file.
            chunks: List of ChunkResult objects from the document chunker.
            embeddings: List of embedding vectors corresponding to each chunk.
            metadata: Additional metadata dict containing 'department' key.

        Raises:
            Logs error and re-raises if the vector store is unavailable.
        """
        try:
            # First remove any existing embeddings for this file
            self.delete_by_file(file_id)

            if not chunks or not embeddings:
                return

            # Build IDs, documents, metadatas, and embeddings for ChromaDB
            ids = []
            documents = []
            metadatas = []

            for i, chunk in enumerate(chunks):
                chunk_id = f"file_{file_id}_chunk_{chunk.chunk_index}"
                ids.append(chunk_id)
                documents.append(chunk.text)
                metadatas.append(
                    {
                        "file_id": file_id,
                        "chunk_index": chunk.chunk_index,
                        "department": metadata.get("department", ""),
                    }
                )

            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas,
            )
        except Exception as e:
            logger.error(
                f"Failed to upsert chunks for file_id={file_id} "
                f"to vector store: {e}"
            )
            raise

    def delete_by_file(self, file_id: int) -> None:
        """Remove all embeddings for a file.

        Uses metadata filtering to find and delete all chunks associated
        with the given file_id.

        Args:
            file_id: The database ID of the file whose embeddings to remove.
        """
        try:
            # Query for all chunks belonging to this file_id
            results = self.collection.get(
                where={"file_id": file_id},
            )
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
        except Exception as e:
            logger.error(
                f"Failed to delete embeddings for file_id={file_id} "
                f"from vector store: {e}"
            )
            raise

    def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int,
        min_score: float,
        filters: dict | None = None,
    ) -> list[dict]:
        """Find top-k similar chunks above min_score threshold.

        Performs cosine similarity search against stored embeddings and
        filters results by minimum score. Optionally applies metadata filters.

        Args:
            query_embedding: The query vector to search against.
            top_k: Maximum number of results to return.
            min_score: Minimum similarity score threshold (0.0 to 1.0).
                ChromaDB returns distances; for cosine space,
                similarity = 1 - distance.
            filters: Optional metadata filter dict for ChromaDB where clause.
                Example: {"department": "engineering"}

        Returns:
            List of dicts with keys: id, text, file_id, chunk_index,
            department, score. Sorted by score descending.
        """
        try:
            query_params: dict = {
                "query_embeddings": [query_embedding],
                "n_results": top_k,
                "include": ["documents", "metadatas", "distances"],
            }

            if filters:
                query_params["where"] = filters

            results = self.collection.query(**query_params)

            # Process results - ChromaDB returns distances (lower = more similar for cosine)
            # For cosine space: similarity = 1 - distance
            search_results = []

            if results["ids"] and results["ids"][0]:
                ids = results["ids"][0]
                documents = results["documents"][0] if results["documents"] else []
                metadatas = results["metadatas"][0] if results["metadatas"] else []
                distances = results["distances"][0] if results["distances"] else []

                for i, doc_id in enumerate(ids):
                    # Convert cosine distance to similarity score
                    distance = distances[i] if i < len(distances) else 1.0
                    score = max(0.0, min(1.0, 1.0 - distance))

                    # Filter by minimum score
                    if score < min_score:
                        continue

                    meta = metadatas[i] if i < len(metadatas) else {}
                    text = documents[i] if i < len(documents) else ""

                    search_results.append(
                        {
                            "id": doc_id,
                            "text": text,
                            "file_id": meta.get("file_id"),
                            "chunk_index": meta.get("chunk_index"),
                            "department": meta.get("department", ""),
                            "score": score,
                        }
                    )

            # Sort by score descending
            search_results.sort(key=lambda x: x["score"], reverse=True)

            return search_results

        except Exception as e:
            logger.error(f"Failed to perform similarity search: {e}")
            raise
