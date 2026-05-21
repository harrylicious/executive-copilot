"""Embedding model wrapper for generating vector embeddings.

Provides a unified interface around sentence-transformers SentenceTransformer
for batch and single-query embedding generation.
"""

import logging

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingModel:
    """Generates vector embeddings using sentence-transformers.

    Wraps the SentenceTransformer class to provide batch and single-query
    embedding generation with configurable model selection.

    Args:
        model_name: Name of the sentence-transformers model to load.
            Defaults to "all-MiniLM-L6-v2".

    Raises:
        RuntimeError: If the model fails to load on initialization.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        try:
            self.model = SentenceTransformer(model_name)
            # Use get_embedding_dimension if available (newer API),
            # fall back to get_sentence_embedding_dimension for older versions
            if hasattr(self.model, "get_embedding_dimension"):
                self.dimension: int = self.model.get_embedding_dimension()
            else:
                self.dimension: int = self.model.get_sentence_embedding_dimension()
        except Exception as e:
            logger.error(
                f"Failed to load embedding model '{model_name}': {e}"
            )
            raise RuntimeError(
                f"Failed to load embedding model '{model_name}': {e}"
            ) from e

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, one per input text. Each vector
            is a list of floats with length equal to self.dimension.
        """
        if not texts:
            return []

        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Args:
            query: The query text to embed.

        Returns:
            Embedding vector as a list of floats with length equal
            to self.dimension.
        """
        embedding = self.model.encode(query, convert_to_numpy=True)
        return embedding.tolist()
