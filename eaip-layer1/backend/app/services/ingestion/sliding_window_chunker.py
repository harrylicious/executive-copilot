"""Sliding window chunker for the ingestion pipeline.

Chunks long text sections without clear semantic boundaries using
overlapping fixed-size windows with sentence-boundary alignment.
Uses whitespace-based token counting (split on whitespace).
"""

import re
from dataclasses import dataclass, field

from app.config import ingestion_settings


@dataclass
class SlidingWindowChunkResult:
    """Result of sliding window chunking for a single chunk."""

    text: str
    start_offset: int
    end_offset: int
    chunk_index: int


class SlidingWindowChunker:
    """Chunks text using overlapping fixed-size sliding windows.

    Splits text into overlapping chunks with configurable window size and overlap.
    Aligns chunk boundaries to sentence endings when possible (within 10% tolerance).
    Ensures all chunks have at least a minimum number of tokens by merging the
    final chunk with the previous one if it falls below the threshold.

    Token counting uses whitespace splitting (split on whitespace).
    """

    # Sentence-ending punctuation followed by whitespace or end of string
    _SENTENCE_END_PATTERN = re.compile(r"[.!?](?:\s|$)")

    def __init__(
        self,
        window_size: int | None = None,
        overlap: int | None = None,
        min_chunk_tokens: int | None = None,
    ):
        """Initialize the chunker with configurable parameters.

        Args:
            window_size: Target number of tokens per chunk. Defaults to ingestion_settings.
            overlap: Number of overlapping tokens between consecutive chunks. Defaults to ingestion_settings.
            min_chunk_tokens: Minimum tokens for the final chunk before merging. Defaults to ingestion_settings.
        """
        self.window_size = window_size if window_size is not None else ingestion_settings.sliding_window_size
        self.overlap = overlap if overlap is not None else ingestion_settings.sliding_window_overlap
        self.min_chunk_tokens = min_chunk_tokens if min_chunk_tokens is not None else ingestion_settings.sliding_window_min_chunk

    def _tokenize(self, text: str) -> list[str]:
        """Split text into tokens using whitespace splitting.

        Args:
            text: Input text to tokenize.

        Returns:
            List of whitespace-delimited tokens.
        """
        return text.split()

    def _tokens_to_text(self, tokens: list[str]) -> str:
        """Join tokens back into text with single spaces.

        Args:
            tokens: List of tokens to join.

        Returns:
            Space-joined text string.
        """
        return " ".join(tokens)

    def _find_sentence_boundary(
        self, tokens: list[str], target_pos: int, tolerance: float = 0.1
    ) -> int:
        """Find a sentence boundary near the target split position.

        Searches for a token ending with sentence-ending punctuation (.!?)
        within a tolerance window around the target position. The boundary
        is defined as the position after the sentence-ending token. If a
        boundary exists within 10% of the target split point, returns that
        boundary position. Otherwise returns the original target position.

        Args:
            tokens: The full list of tokens being chunked.
            target_pos: The target token index for the split point.
            tolerance: Fraction of window_size to search around target (default 0.1 = 10%).

        Returns:
            The adjusted split position aligned to a sentence boundary,
            or the original target_pos if no boundary is found within tolerance.
        """
        tolerance_tokens = max(1, int(self.window_size * tolerance))

        # We want to find tokens whose sentence boundary (i+1) is within
        # [target_pos - tolerance_tokens, target_pos + tolerance_tokens].
        # So we search token indices where i+1 is in that range,
        # meaning i is in [target_pos - tolerance_tokens - 1, target_pos + tolerance_tokens - 1].
        search_start = max(0, target_pos - tolerance_tokens - 1)
        search_end = min(len(tokens), target_pos + tolerance_tokens)

        # Look for sentence-ending tokens within the search window
        # Prefer the boundary closest to the target position
        best_pos = None
        best_distance = float("inf")

        for i in range(search_start, search_end):
            token = tokens[i]
            # Check if this token ends with sentence-ending punctuation
            if token and token[-1] in ".!?":
                # The split should happen after this token (i+1)
                candidate = i + 1
                # Only consider if the candidate is within tolerance of target
                if abs(candidate - target_pos) <= tolerance_tokens:
                    distance = abs(candidate - target_pos)
                    if distance < best_distance:
                        best_distance = distance
                        best_pos = candidate

        if best_pos is not None:
            return best_pos

        return target_pos

    def _merge_final_chunk(
        self, chunks: list[list[str]], min_size: int | None = None
    ) -> list[list[str]]:
        """Merge the final chunk with the previous one if it's below minimum size.

        If the last chunk has fewer tokens than min_size and there is a
        previous chunk to merge with, the last chunk's tokens are appended
        to the previous chunk.

        Args:
            chunks: List of token lists representing chunks.
            min_size: Minimum number of tokens for the final chunk.
                     Defaults to self.min_chunk_tokens.

        Returns:
            Updated list of token lists with final chunk merged if needed.
        """
        if min_size is None:
            min_size = self.min_chunk_tokens

        if len(chunks) < 2:
            return chunks

        if len(chunks[-1]) < min_size:
            # Merge last chunk into previous
            chunks[-2] = chunks[-2] + chunks[-1]
            chunks.pop()

        return chunks

    def chunk(
        self,
        text: str,
        window_size: int | None = None,
        overlap: int | None = None,
    ) -> list[SlidingWindowChunkResult]:
        """Split text into overlapping chunks using a sliding window approach.

        The text is tokenized using whitespace splitting, then divided into
        chunks of approximately window_size tokens with overlap tokens of
        overlap between consecutive chunks. Chunk boundaries are aligned to
        sentence endings when possible (within 10% tolerance of the target
        split point). The final chunk is merged with the previous one if it
        falls below the minimum chunk size (128 tokens by default).

        Args:
            text: Input text to chunk.
            window_size: Override window size (tokens per chunk). Uses instance default if None.
            overlap: Override overlap size (tokens shared between chunks). Uses instance default if None.

        Returns:
            List of SlidingWindowChunkResult objects with text, offsets, and chunk_index.
        """
        ws = window_size if window_size is not None else self.window_size
        ovlp = overlap if overlap is not None else self.overlap

        tokens = self._tokenize(text)

        if not tokens:
            return []

        # If the text fits in a single window, return it as one chunk
        if len(tokens) <= ws:
            return [
                SlidingWindowChunkResult(
                    text=self._tokens_to_text(tokens),
                    start_offset=0,
                    end_offset=len(tokens),
                    chunk_index=0,
                )
            ]

        # Build chunks using sliding window
        chunk_token_spans: list[tuple[int, int]] = []  # (start_idx, end_idx) in token space
        pos = 0

        while pos < len(tokens):
            # Target end position for this chunk
            target_end = min(pos + ws, len(tokens))

            if target_end >= len(tokens):
                # Last chunk: take everything remaining
                chunk_token_spans.append((pos, len(tokens)))
                break

            # Try to align to a sentence boundary
            aligned_end = self._find_sentence_boundary(tokens, target_end)

            # Ensure we make progress (at least 1 token)
            if aligned_end <= pos:
                aligned_end = target_end

            chunk_token_spans.append((pos, aligned_end))

            # Advance position: step forward by (chunk_size - overlap)
            step = aligned_end - pos - ovlp
            if step <= 0:
                # Ensure we always make forward progress
                step = max(1, ws - ovlp)
            pos += step

        # Convert token spans to token lists for merging
        chunk_token_lists = [tokens[start:end] for start, end in chunk_token_spans]

        # Merge final chunk if below minimum size
        chunk_token_lists = self._merge_final_chunk(chunk_token_lists)

        # Rebuild spans after potential merge
        # We need to recalculate offsets based on the actual token lists
        results: list[SlidingWindowChunkResult] = []
        # Track token positions by rebuilding from the chunk_token_spans
        # After merge, the last span may have changed
        if len(chunk_token_lists) < len(chunk_token_spans):
            # A merge happened: combine the last two spans
            merged_spans = list(chunk_token_spans[: len(chunk_token_lists) - 1])
            # The merged chunk spans from the start of the second-to-last to the end of the last
            merged_start = chunk_token_spans[-2][0]
            merged_end = chunk_token_spans[-1][1]
            merged_spans.append((merged_start, merged_end))
            chunk_token_spans = merged_spans

        for idx, (start, end) in enumerate(chunk_token_spans):
            chunk_text = self._tokens_to_text(tokens[start:end])
            results.append(
                SlidingWindowChunkResult(
                    text=chunk_text,
                    start_offset=start,
                    end_offset=end,
                    chunk_index=idx,
                )
            )

        return results
