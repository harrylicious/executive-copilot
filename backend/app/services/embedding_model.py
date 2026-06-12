"""Embedding model wrapper for generating vector embeddings.

Provides a unified interface around sentence-transformers (local models)
and OpenAI API (text-embedding-* models) for batch and single-query
embedding generation.
"""

import logging
import os

from openai import OpenAI
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_OPENAI_EMBEDDING_DIMENSIONS: dict[str, int] = {
    "text-embedding-ada-002": 1536,
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
}


class EmbeddingModel:
    """Generates vector embeddings using sentence-transformers or OpenAI.

    Dispatches to sentence-transformers for local model names and to the
    OpenAI API for model names starting with "text-embedding-".

    Args:
        model_name: Name of the embedding model to load.
            For local models, see sentence-transformers catalog.
            For API models: "text-embedding-ada-002", "text-embedding-3-small",
            "text-embedding-3-large". Defaults to "all-MiniLM-L6-v2".

    Raises:
        RuntimeError: If the model fails to load on initialization.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._client: OpenAI | None = None
        self._model: SentenceTransformer | None = None
        self.dimension: int = 0
        self._using_openai = False

        if model_name.startswith("text-embedding-"):
            self._using_openai = True
            self._init_openai(model_name)
        else:
            self._init_sentence_transformers(model_name)

    def _init_openai(self, model_name: str) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                f"OpenAI embedding model '{model_name}' requires "
                "OPENAI_API_KEY environment variable to be set."
            )
        self._client = OpenAI(api_key=api_key)
        self.dimension = _OPENAI_EMBEDDING_DIMENSIONS.get(model_name, 1536)
        logger.info(
            f"Initialized OpenAI embedding model '{model_name}' "
            f"(dimension={self.dimension})"
        )

    def _init_sentence_transformers(self, model_name: str) -> None:
        try:
            self._model = SentenceTransformer(model_name)
            dim = (
                self._model.get_embedding_dimension()
                if hasattr(self._model, "get_embedding_dimension")
                else self._model.get_sentence_embedding_dimension()
            )
            self.dimension = dim if dim is not None else 0
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

        if self._using_openai and self._client is not None:
            return self._embed_openai(texts)

        if self._model is not None:
            return self._embed_sentence_transformers(texts)

        return []

    def embed_query(self, query: str) -> list[float]:
        """Generate embedding for a single query string.

        Args:
            query: The query text to embed.

        Returns:
            Embedding vector as a list of floats with length equal
            to self.dimension.
        """
        if self._using_openai and self._client is not None:
            return self._embed_openai([query])[0]

        if self._model is not None:
            return self._embed_sentence_transformers([query])[0]

        return []

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        if self._client is None:
            return []
        response = self._client.embeddings.create(
            model=self.model_name,
            input=texts,
        )
        return [item.embedding for item in response.data]

    def _embed_sentence_transformers(
        self, texts: list[str]
    ) -> list[list[float]]:
        if self._model is None:
            return []
        embeddings = self._model.encode(texts, convert_to_numpy=True)
        return [embedding.tolist() for embedding in embeddings]
