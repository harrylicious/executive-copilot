"""Document chunking service using token-based boundaries.

Splits extracted text into overlapping chunks using the embedding model's
tokenizer for accurate token counting. Preserves character offset metadata
for each chunk.
"""

import logging
from dataclasses import dataclass

from transformers import AutoTokenizer

logger = logging.getLogger(__name__)


@dataclass
class ChunkResult:
    """Result of chunking a segment of text.

    Attributes:
        text: The chunk text content.
        chunk_index: Sequential index starting at 0.
        start_offset: Character offset from the beginning of the source text.
        end_offset: Character offset marking the end of this chunk in the source text.
    """

    text: str
    chunk_index: int
    start_offset: int
    end_offset: int


class DocumentChunker:
    """Splits text into overlapping chunks using token-based boundaries.

    Uses the configured embedding model's tokenizer to determine token
    boundaries, ensuring chunks respect the model's token limits.

    Args:
        chunk_size: Maximum number of tokens per chunk (default 512).
        chunk_overlap: Number of overlapping tokens between consecutive chunks (default 50).
        model_name: Name of the sentence-transformers model whose tokenizer to use.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = self._load_tokenizer(model_name)

    def _load_tokenizer(self, model_name: str) -> AutoTokenizer:
        """Load the tokenizer for the specified model.

        Attempts to load from the sentence-transformers namespace first,
        then falls back to the bare model name.
        """
        try:
            return AutoTokenizer.from_pretrained(
                f"sentence-transformers/{model_name}"
            )
        except Exception:
            try:
                return AutoTokenizer.from_pretrained(model_name)
            except Exception as e:
                logger.error(
                    f"Failed to load tokenizer for model '{model_name}': {e}"
                )
                raise

    def chunk(self, text: str) -> list[ChunkResult]:
        """Split text into chunks based on token boundaries.

        Returns an empty list for empty text. Returns a single chunk if the
        text contains fewer tokens than chunk_size.

        Args:
            text: The source text to chunk.

        Returns:
            List of ChunkResult with sequential indices and character offsets.
        """
        if not text:
            return []

        # Tokenize the full text without special tokens to get content tokens
        encoding = self.tokenizer(
            text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            truncation=False,
        )

        token_ids = encoding["input_ids"]
        offsets = encoding["offset_mapping"]

        if not token_ids:
            return []

        # If text fits in a single chunk, return it directly
        if len(token_ids) <= self.chunk_size:
            return [
                ChunkResult(
                    text=text,
                    chunk_index=0,
                    start_offset=0,
                    end_offset=len(text),
                )
            ]

        chunks: list[ChunkResult] = []
        chunk_index = 0
        start_token_idx = 0

        while start_token_idx < len(token_ids):
            # Determine the end token index for this chunk
            end_token_idx = min(start_token_idx + self.chunk_size, len(token_ids))

            # Get character offsets from the token offset mapping
            chunk_start_char = offsets[start_token_idx][0]
            chunk_end_char = offsets[end_token_idx - 1][1]

            # Extract the chunk text using character offsets
            chunk_text = text[chunk_start_char:chunk_end_char]

            chunks.append(
                ChunkResult(
                    text=chunk_text,
                    chunk_index=chunk_index,
                    start_offset=chunk_start_char,
                    end_offset=chunk_end_char,
                )
            )

            chunk_index += 1

            # Advance by (chunk_size - overlap) tokens
            step = self.chunk_size - self.chunk_overlap
            if step <= 0:
                # Safety: ensure we always advance at least 1 token
                step = 1
            start_token_idx += step

            # If we've consumed all tokens, stop
            if start_token_idx >= len(token_ids):
                break

        return chunks
