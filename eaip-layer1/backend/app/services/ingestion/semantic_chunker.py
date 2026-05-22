"""Semantic chunker for document splitting at meaningful boundaries.

Splits documents at semantic boundaries (headings, section breaks, topic transitions)
using structure metadata from the normalizer. Produces chunks with target size
256-1024 tokens, delegating oversized sections to the Sliding Window Chunker.
"""

from dataclasses import dataclass

from app.config import ingestion_settings
from app.services.ingestion.normalizer import StructureMetadata
from app.services.ingestion.sliding_window_chunker import SlidingWindowChunker


@dataclass
class SemanticChunkResult:
    """Result of semantic chunking for a single chunk."""

    text: str
    prepended_heading: str
    chunk_index: int
    start_offset: int
    end_offset: int
    section_path: str
    chunking_method: str  # "semantic" or "sliding_window"
    token_count: int


class SemanticChunker:
    """Splits documents at semantic boundaries with structure-aware chunking.

    Uses StructureMetadata (headings, sections) from the normalizer to identify
    natural split points. Sections below the minimum token count are merged with
    adjacent sections. Sections exceeding the maximum token count are delegated
    to the SlidingWindowChunker.

    Each chunk is prepended with its parent section heading and includes metadata
    recording chunk_index, start_offset, end_offset, section_path, and chunking_method.

    The round-trip property holds: concatenating all chunk texts (excluding prepended
    headings) reconstructs the original document text exactly.
    """

    def __init__(
        self,
        min_tokens: int | None = None,
        max_tokens: int | None = None,
    ):
        """Initialize the semantic chunker.

        Args:
            min_tokens: Minimum tokens per chunk before merging. Defaults to ingestion_settings.semantic_chunk_min_tokens.
            max_tokens: Maximum tokens per chunk before delegation. Defaults to ingestion_settings.semantic_chunk_max_tokens.
        """
        self.min_tokens = min_tokens or ingestion_settings.semantic_chunk_min_tokens
        self.max_tokens = max_tokens or ingestion_settings.semantic_chunk_max_tokens
        self._sliding_window_chunker = SlidingWindowChunker()

    def _count_tokens(self, text: str) -> int:
        """Count tokens using whitespace splitting.

        Args:
            text: Text to count tokens for.

        Returns:
            Number of whitespace-delimited tokens.
        """
        if not text.strip():
            return 0
        return len(text.split())

    def _identify_boundaries(self, text: str, structure: StructureMetadata) -> list[int]:
        """Identify semantic boundaries from structure metadata.

        Detects heading positions and section breaks from the StructureMetadata
        produced by the normalizer. Returns sorted character offsets where the
        text should be split.

        Args:
            text: The full document text.
            structure: StructureMetadata containing headings and sections.

        Returns:
            Sorted list of character offsets representing split boundaries.
        """
        boundaries: set[int] = set()

        # Add heading offsets as boundaries
        for heading in structure.headings:
            if 0 < heading.offset < len(text):
                boundaries.add(heading.offset)

        # Add section start offsets as boundaries (may overlap with headings)
        for section in structure.sections:
            if 0 < section.start_offset < len(text):
                boundaries.add(section.start_offset)

        # Always include start and end
        boundaries.add(0)
        boundaries.add(len(text))

        return sorted(boundaries)

    def _split_at_boundaries(self, text: str, boundaries: list[int]) -> list[tuple[str, int, int]]:
        """Split text at the identified semantic boundaries.

        Args:
            text: The full document text.
            boundaries: Sorted list of character offsets to split at.

        Returns:
            List of tuples (section_text, start_offset, end_offset) for each section.
        """
        sections: list[tuple[str, int, int]] = []

        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            section_text = text[start:end]
            if section_text:  # Skip empty sections
                sections.append((section_text, start, end))

        return sections

    def _merge_small_sections(
        self, sections: list[tuple[str, int, int]]
    ) -> list[tuple[str, int, int]]:
        """Merge sections below the minimum token count with adjacent sections.

        Combines small sections with the next section. If the last section is small,
        it is merged with the previous section.

        Args:
            sections: List of (section_text, start_offset, end_offset) tuples.

        Returns:
            Updated list with small sections merged into adjacent ones.
        """
        if not sections:
            return sections

        merged: list[tuple[str, int, int]] = []

        i = 0
        while i < len(sections):
            current_text, current_start, current_end = sections[i]
            current_tokens = self._count_tokens(current_text)

            # If current section is below minimum and there's a next section, merge forward
            if current_tokens < self.min_tokens and i + 1 < len(sections):
                next_text, _, next_end = sections[i + 1]
                combined_text = current_text + next_text
                combined_tokens = self._count_tokens(combined_text)

                # Keep merging forward while still below minimum and more sections exist
                j = i + 2
                while combined_tokens < self.min_tokens and j < len(sections):
                    next_text_j, _, next_end_j = sections[j]
                    combined_text = combined_text + next_text_j
                    combined_tokens = self._count_tokens(combined_text)
                    next_end = next_end_j
                    j += 1
                else:
                    if j == i + 2:
                        # Only merged with one section
                        pass
                    else:
                        next_end = sections[j - 1][2]

                # Recalculate next_end from the last merged section
                last_merged_idx = j - 1 if j > i + 2 else i + 1
                next_end = sections[last_merged_idx][2]

                merged.append((combined_text, current_start, next_end))
                i = last_merged_idx + 1
            else:
                merged.append((current_text, current_start, current_end))
                i += 1

        # If the last merged section is still below minimum and there's a previous one, merge backward
        if len(merged) > 1:
            last_text, last_start, last_end = merged[-1]
            if self._count_tokens(last_text) < self.min_tokens:
                prev_text, prev_start, prev_end = merged[-2]
                combined = prev_text + last_text
                merged[-2] = (combined, prev_start, last_end)
                merged.pop()

        return merged

    def _get_section_path(self, offset: int, structure: StructureMetadata) -> str:
        """Build the hierarchical section path (heading trail) for a given offset.

        Finds all headings that are ancestors of the given offset position,
        building a path like "Chapter 1 > Section 1.1 > Subsection".

        Args:
            offset: Character offset in the document.
            structure: StructureMetadata with heading information.

        Returns:
            Hierarchical heading trail as a string separated by " > ".
        """
        if not structure.headings:
            return ""

        # Find all headings that precede this offset, building a hierarchy
        path_parts: list[str] = []
        current_level = 0

        for heading in structure.headings:
            if heading.offset > offset:
                break
            # If this heading is at a higher or same level, reset the path from that level
            if heading.level <= current_level:
                # Remove all path parts at this level or deeper
                path_parts = [
                    p for i, p in enumerate(path_parts)
                    if i < heading.level - 1
                ]
            path_parts.append(heading.text)
            current_level = heading.level

        return " > ".join(path_parts)

    def _get_parent_heading(self, offset: int, structure: StructureMetadata) -> str:
        """Get the immediate parent heading for a given offset.

        Args:
            offset: Character offset in the document.
            structure: StructureMetadata with heading information.

        Returns:
            The text of the most recent heading before this offset, or empty string.
        """
        parent_heading = ""
        for heading in structure.headings:
            if heading.offset > offset:
                break
            parent_heading = heading.text

        return parent_heading

    def _partition_section_for_sw_chunks(
        self,
        section_text: str,
        sw_chunks: list,
        section_start_offset: int,
    ) -> list[tuple[int, int]]:
        """Compute non-overlapping character offset partitions for sliding window chunks.

        The SlidingWindowChunker produces overlapping chunks (by design). For the
        semantic chunker's round-trip property, we need non-overlapping spans that
        partition the section completely. We compute the "owned" region for each
        chunk by splitting overlapping regions at their midpoints.

        Args:
            section_text: The text of the section that was chunked.
            sw_chunks: List of SlidingWindowChunkResult from the sliding window chunker.
            section_start_offset: Character offset of this section in the full document.

        Returns:
            List of (start_char_offset, end_char_offset) tuples forming a non-overlapping
            partition of the section.
        """
        if not sw_chunks:
            return []

        tokens = section_text.split()
        total_tokens = len(tokens)

        # Build a mapping from token index to character offset within section_text
        token_char_starts: list[int] = []
        pos = 0
        for token in tokens:
            idx = section_text.find(token, pos)
            token_char_starts.append(idx)
            pos = idx + len(token)
        # Sentinel: character position for "one past the last token"
        token_char_starts.append(len(section_text))

        if len(sw_chunks) == 1:
            return [(section_start_offset, section_start_offset + len(section_text))]

        # Compute non-overlapping token boundaries by splitting overlap at midpoints
        # Each chunk has token range [start_offset, end_offset)
        # For consecutive chunks i and i+1, the overlap region is
        # [chunk[i+1].start_offset, chunk[i].end_offset)
        # We split at the midpoint of this overlap.
        partition_token_boundaries: list[int] = [sw_chunks[0].start_offset]

        for i in range(len(sw_chunks) - 1):
            current_end = sw_chunks[i].end_offset
            next_start = sw_chunks[i + 1].start_offset

            if next_start < current_end:
                # There's overlap - split at midpoint
                midpoint = (next_start + current_end) // 2
                partition_token_boundaries.append(midpoint)
            else:
                # No overlap or gap - use the boundary between them
                partition_token_boundaries.append(current_end)

        partition_token_boundaries.append(
            sw_chunks[-1].end_offset if sw_chunks[-1].end_offset <= total_tokens else total_tokens
        )

        # Convert token boundaries to character offsets
        char_offsets: list[tuple[int, int]] = []
        for i in range(len(partition_token_boundaries) - 1):
            start_tok = partition_token_boundaries[i]
            end_tok = partition_token_boundaries[i + 1]

            char_start = token_char_starts[min(start_tok, total_tokens)]
            if end_tok >= total_tokens:
                char_end = len(section_text)
            else:
                char_end = token_char_starts[end_tok]

            char_offsets.append((
                section_start_offset + char_start,
                section_start_offset + char_end,
            ))

        return char_offsets

    def chunk(self, text: str, structure: StructureMetadata) -> list[SemanticChunkResult]:
        """Split a document into semantic chunks with metadata.

        Orchestrates the full chunking pipeline:
        1. Identify semantic boundaries from structure metadata
        2. Split text at boundaries
        3. Merge small sections below minimum token count
        4. For sections exceeding max tokens, delegate to SlidingWindowChunker
        5. Prepend parent heading and record metadata for each chunk

        The round-trip property holds: concatenating all chunk texts (the portion
        from the original document, excluding prepended headings) reconstructs
        the original text exactly.

        Args:
            text: The full normalized document text.
            structure: StructureMetadata from the normalizer.

        Returns:
            List of SemanticChunkResult with text, metadata, and prepended headings.
        """
        if not text.strip():
            return []

        # Step 1: Identify boundaries
        boundaries = self._identify_boundaries(text, structure)

        # Step 2: Split at boundaries
        sections = self._split_at_boundaries(text, boundaries)

        # If no sections were produced (no boundaries found), treat entire text as one section
        if not sections:
            sections = [(text, 0, len(text))]

        # Step 3: Merge small sections
        sections = self._merge_small_sections(sections)

        # Step 4 & 5: Process each section, delegating oversized ones
        results: list[SemanticChunkResult] = []
        chunk_index = 0

        for section_text, start_offset, end_offset in sections:
            token_count = self._count_tokens(section_text)
            parent_heading = self._get_parent_heading(start_offset, structure)
            section_path = self._get_section_path(start_offset, structure)

            if token_count > self.max_tokens:
                # Delegate to sliding window chunker
                sw_chunks = self._sliding_window_chunker.chunk(section_text)

                # Compute non-overlapping character offset partitions
                char_offsets = self._partition_section_for_sw_chunks(
                    section_text, sw_chunks, start_offset
                )

                for (chunk_char_start, chunk_char_end) in char_offsets:
                    chunk_original_text = text[chunk_char_start:chunk_char_end]
                    sw_token_count = self._count_tokens(chunk_original_text)

                    # Build the display text with prepended heading
                    if parent_heading:
                        display_text = f"[{parent_heading}]\n{chunk_original_text}"
                    else:
                        display_text = chunk_original_text

                    results.append(
                        SemanticChunkResult(
                            text=display_text,
                            prepended_heading=parent_heading,
                            chunk_index=chunk_index,
                            start_offset=chunk_char_start,
                            end_offset=chunk_char_end,
                            section_path=section_path,
                            chunking_method="sliding_window",
                            token_count=sw_token_count,
                        )
                    )
                    chunk_index += 1
            else:
                # Semantic chunk - within bounds
                if parent_heading:
                    display_text = f"[{parent_heading}]\n{section_text}"
                else:
                    display_text = section_text

                results.append(
                    SemanticChunkResult(
                        text=display_text,
                        prepended_heading=parent_heading,
                        chunk_index=chunk_index,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        section_path=section_path,
                        chunking_method="semantic",
                        token_count=token_count,
                    )
                )
                chunk_index += 1

        return results
