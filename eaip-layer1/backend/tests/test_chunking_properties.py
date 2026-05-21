"""Property-based tests for document chunking validity.

Property 1: Chunking produces valid segments that reconstruct the source text

For any non-empty text string and valid chunking parameters (chunk_size ∈ [64, 4096],
overlap ∈ [0, chunk_size//2]), the DocumentChunker SHALL produce chunks where:
- Each chunk's token count is ≤ chunk_size
- Each chunk's text matches source_text[start_offset:end_offset]
- Chunk indices are sequential starting at 0
- The concatenation of non-overlapping portions of all chunks covers the entire original text

**Validates: Requirements 1.2, 1.3**
"""

import hypothesis.strategies as st
from hypothesis import given, settings, assume
from transformers import AutoTokenizer

from app.services.document_chunker import DocumentChunker


# Load the tokenizer once at module level to avoid repeated model loading
_TOKENIZER = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")


def _make_chunker(chunk_size: int, chunk_overlap: int) -> DocumentChunker:
    """Create a DocumentChunker reusing the shared tokenizer."""
    chunker = DocumentChunker.__new__(DocumentChunker)
    chunker.chunk_size = chunk_size
    chunker.chunk_overlap = chunk_overlap
    chunker.tokenizer = _TOKENIZER
    return chunker


# Strategy for generating valid chunking parameters
# chunk_size ∈ [64, 4096], overlap ∈ [0, chunk_size//2]
@st.composite
def chunking_params(draw):
    """Generate valid (chunk_size, chunk_overlap) pairs."""
    chunk_size = draw(st.integers(min_value=64, max_value=4096))
    max_overlap = chunk_size // 2
    chunk_overlap = draw(st.integers(min_value=0, max_value=max_overlap))
    return chunk_size, chunk_overlap


# Strategy for generating non-empty text strings that produce tokens.
# We use printable text to ensure the tokenizer produces meaningful tokens.
non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=1,
    max_size=2000,
).filter(lambda t: t.strip() != "")


class TestProperty1ChunkingValidity:
    """Property 1: Chunking produces valid segments that reconstruct the source text."""

    @given(text=non_empty_text, params=chunking_params())
    @settings(max_examples=100, deadline=30000)
    def test_each_chunk_token_count_within_limit(self, text: str, params: tuple):
        """Each chunk's token count is ≤ chunk_size."""
        chunk_size, chunk_overlap = params
        chunker = _make_chunker(chunk_size, chunk_overlap)

        # Skip if text produces no tokens
        encoding = chunker.tokenizer(
            text, add_special_tokens=False, truncation=False
        )
        assume(len(encoding["input_ids"]) > 0)

        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        for chunk in chunks:
            token_count = len(
                chunker.tokenizer.encode(chunk.text, add_special_tokens=False)
            )
            assert token_count <= chunk_size, (
                f"Chunk {chunk.chunk_index} has {token_count} tokens, "
                f"exceeding chunk_size={chunk_size}"
            )

    @given(text=non_empty_text, params=chunking_params())
    @settings(max_examples=100, deadline=30000)
    def test_chunk_text_matches_source_offsets(self, text: str, params: tuple):
        """Each chunk's text matches source_text[start_offset:end_offset]."""
        chunk_size, chunk_overlap = params
        chunker = _make_chunker(chunk_size, chunk_overlap)

        encoding = chunker.tokenizer(
            text, add_special_tokens=False, truncation=False
        )
        assume(len(encoding["input_ids"]) > 0)

        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        for chunk in chunks:
            expected_text = text[chunk.start_offset:chunk.end_offset]
            assert chunk.text == expected_text, (
                f"Chunk {chunk.chunk_index}: text does not match "
                f"source_text[{chunk.start_offset}:{chunk.end_offset}]"
            )

    @given(text=non_empty_text, params=chunking_params())
    @settings(max_examples=100, deadline=30000)
    def test_chunk_indices_are_sequential(self, text: str, params: tuple):
        """Chunk indices are sequential starting at 0."""
        chunk_size, chunk_overlap = params
        chunker = _make_chunker(chunk_size, chunk_overlap)

        encoding = chunker.tokenizer(
            text, add_special_tokens=False, truncation=False
        )
        assume(len(encoding["input_ids"]) > 0)

        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        indices = [c.chunk_index for c in chunks]
        assert indices == list(range(len(chunks))), (
            f"Chunk indices {indices} are not sequential starting at 0"
        )

    @given(text=non_empty_text, params=chunking_params())
    @settings(max_examples=100, deadline=30000)
    def test_chunks_cover_entire_text(self, text: str, params: tuple):
        """The concatenation of non-overlapping portions of all chunks covers the entire original text."""
        chunk_size, chunk_overlap = params
        chunker = _make_chunker(chunk_size, chunk_overlap)

        encoding = chunker.tokenizer(
            text, add_special_tokens=False, truncation=False
        )
        assume(len(encoding["input_ids"]) > 0)

        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        # For a single chunk, it should cover the entire tokenized text
        if len(chunks) == 1:
            assert chunks[0].start_offset == 0
            assert chunks[0].end_offset == len(text)
            return

        # For multiple chunks, verify full coverage:
        # 1. First chunk starts at 0
        assert chunks[0].start_offset == 0, (
            f"First chunk starts at {chunks[0].start_offset}, expected 0"
        )

        # 2. Last chunk ends at the end of the tokenized content
        # (the last token's end offset from the tokenizer)
        offsets = encoding["offset_mapping"]
        last_token_end = offsets[-1][1]
        assert chunks[-1].end_offset == last_token_end, (
            f"Last chunk ends at {chunks[-1].end_offset}, "
            f"expected {last_token_end} (end of tokenized content)"
        )

        # 3. No gaps between consecutive chunks: each chunk's start_offset
        #    must be <= the previous chunk's end_offset (overlap means <=)
        for i in range(1, len(chunks)):
            assert chunks[i].start_offset <= chunks[i - 1].end_offset, (
                f"Gap between chunk {i-1} (end={chunks[i-1].end_offset}) "
                f"and chunk {i} (start={chunks[i].start_offset})"
            )

        # 4. Build the non-overlapping coverage and verify it covers
        #    the full tokenized text range
        covered = set()
        for chunk in chunks:
            for pos in range(chunk.start_offset, chunk.end_offset):
                covered.add(pos)

        # Every character position from 0 to last_token_end should be covered
        expected_positions = set(range(0, last_token_end))
        missing = expected_positions - covered
        assert not missing, (
            f"Characters at positions {sorted(list(missing))[:10]}... "
            f"are not covered by any chunk"
        )
