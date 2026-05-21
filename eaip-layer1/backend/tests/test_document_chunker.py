"""Unit tests for the DocumentChunker service."""

import pytest

from app.services.document_chunker import ChunkResult, DocumentChunker


@pytest.fixture
def chunker():
    """Create a DocumentChunker with default settings."""
    return DocumentChunker(chunk_size=512, chunk_overlap=50)


@pytest.fixture
def small_chunker():
    """Create a DocumentChunker with small chunk_size for testing."""
    return DocumentChunker(chunk_size=10, chunk_overlap=3)


class TestChunkResultDataclass:
    """Tests for the ChunkResult dataclass."""

    def test_creates_chunk_result(self):
        """Should create a ChunkResult with all fields."""
        result = ChunkResult(
            text="hello world",
            chunk_index=0,
            start_offset=0,
            end_offset=11,
        )
        assert result.text == "hello world"
        assert result.chunk_index == 0
        assert result.start_offset == 0
        assert result.end_offset == 11


class TestDocumentChunkerInit:
    """Tests for DocumentChunker initialization."""

    def test_default_parameters(self):
        """Should initialize with default chunk_size=512, overlap=50."""
        dc = DocumentChunker()
        assert dc.chunk_size == 512
        assert dc.chunk_overlap == 50

    def test_custom_parameters(self):
        """Should accept custom chunk_size and overlap."""
        dc = DocumentChunker(chunk_size=256, chunk_overlap=25)
        assert dc.chunk_size == 256
        assert dc.chunk_overlap == 25

    def test_loads_tokenizer(self):
        """Should load a tokenizer from the model name."""
        dc = DocumentChunker(model_name="all-MiniLM-L6-v2")
        assert dc.tokenizer is not None


class TestChunkEmptyText:
    """Tests for chunking empty or whitespace-only text."""

    def test_empty_string_returns_empty_list(self, chunker):
        """Should return empty list for empty string."""
        result = chunker.chunk("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self, chunker):
        """Should return empty list for whitespace-only text (no tokens)."""
        result = chunker.chunk("   ")
        assert result == []


class TestChunkShortText:
    """Tests for text shorter than chunk_size."""

    def test_short_text_returns_single_chunk(self, chunker):
        """Should return a single chunk for text shorter than chunk_size."""
        text = "Hello, this is a short document."
        result = chunker.chunk(text)
        assert len(result) == 1
        assert result[0].text == text
        assert result[0].chunk_index == 0
        assert result[0].start_offset == 0
        assert result[0].end_offset == len(text)

    def test_single_word_returns_single_chunk(self, chunker):
        """Should return a single chunk for a single word."""
        text = "hello"
        result = chunker.chunk(text)
        assert len(result) == 1
        assert result[0].text == text
        assert result[0].chunk_index == 0


class TestChunkLongText:
    """Tests for text that requires multiple chunks."""

    def test_produces_multiple_chunks(self, small_chunker):
        """Should produce multiple chunks for text exceeding chunk_size."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast"
        result = small_chunker.chunk(text)
        assert len(result) > 1

    def test_chunk_indices_are_sequential(self, small_chunker):
        """Should produce sequential chunk indices starting at 0."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast"
        result = small_chunker.chunk(text)
        indices = [c.chunk_index for c in result]
        assert indices == list(range(len(result)))

    def test_chunk_offsets_map_to_source_text(self, small_chunker):
        """Should produce offsets that correctly map back to source text."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast"
        result = small_chunker.chunk(text)
        for chunk in result:
            assert text[chunk.start_offset:chunk.end_offset] == chunk.text

    def test_chunks_do_not_exceed_token_limit(self, small_chunker):
        """Each chunk should have at most chunk_size tokens."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast into the deep dark forest"
        result = small_chunker.chunk(text)
        for chunk in result:
            token_count = len(
                small_chunker.tokenizer.encode(
                    chunk.text, add_special_tokens=False
                )
            )
            assert token_count <= small_chunker.chunk_size

    def test_chunks_cover_entire_text(self, small_chunker):
        """Non-overlapping portions of chunks should cover the entire text."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast"
        result = small_chunker.chunk(text)
        # First chunk starts at 0, last chunk ends at or near end of text
        assert result[0].start_offset == 0
        assert result[-1].end_offset == len(text) or result[-1].end_offset <= len(text)
        # Verify no gaps: each chunk's start_offset <= previous chunk's end_offset
        for i in range(1, len(result)):
            assert result[i].start_offset < result[i - 1].end_offset


class TestChunkOverlap:
    """Tests for overlap behavior between chunks."""

    def test_consecutive_chunks_overlap(self, small_chunker):
        """Consecutive chunks should have overlapping text regions."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast into the forest"
        result = small_chunker.chunk(text)
        if len(result) >= 2:
            # Second chunk should start before first chunk ends
            assert result[1].start_offset < result[0].end_offset

    def test_zero_overlap_produces_non_overlapping_chunks(self):
        """With overlap=0, chunks should not overlap."""
        dc = DocumentChunker(chunk_size=5, chunk_overlap=0)
        text = "The quick brown fox jumps over the lazy dog"
        result = dc.chunk(text)
        if len(result) >= 2:
            # Each chunk starts where the previous one ended (or after)
            for i in range(1, len(result)):
                assert result[i].start_offset >= result[i - 1].end_offset


class TestChunkConfigurable:
    """Tests for configurable chunk_size and chunk_overlap."""

    def test_larger_chunk_size_produces_fewer_chunks(self):
        """Larger chunk_size should produce fewer chunks."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast into the deep dark forest near the river"
        dc_small = DocumentChunker(chunk_size=5, chunk_overlap=1)
        dc_large = DocumentChunker(chunk_size=20, chunk_overlap=1)
        result_small = dc_small.chunk(text)
        result_large = dc_large.chunk(text)
        assert len(result_small) > len(result_large)

    def test_larger_overlap_produces_more_chunks(self):
        """Larger overlap should produce more chunks (smaller step)."""
        text = "The quick brown fox jumps over the lazy dog and runs away fast into the deep dark forest near the river"
        dc_small_overlap = DocumentChunker(chunk_size=10, chunk_overlap=1)
        dc_large_overlap = DocumentChunker(chunk_size=10, chunk_overlap=5)
        result_small = dc_small_overlap.chunk(text)
        result_large = dc_large_overlap.chunk(text)
        assert len(result_large) >= len(result_small)
