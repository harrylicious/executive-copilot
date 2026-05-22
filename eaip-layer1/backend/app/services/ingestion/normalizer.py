"""Text normalization service for the ingestion pipeline.

Normalizes extracted text to NFC Unicode, collapses whitespace,
removes control characters, and extracts document structure metadata.
"""

import re
import unicodedata
from dataclasses import dataclass, field


@dataclass
class HeadingInfo:
    """Represents a detected heading in the document."""

    level: int
    text: str
    offset: int


@dataclass
class SectionInfo:
    """Represents a detected section in the document."""

    title: str
    start_offset: int
    end_offset: int
    level: int


@dataclass
class StructureMetadata:
    """Document structure metadata extracted during normalization."""

    headings: list[HeadingInfo] = field(default_factory=list)
    sections: list[SectionInfo] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)


@dataclass
class NormalizedText:
    """Result of text normalization containing the normalized text and structure metadata."""

    text: str
    structure: StructureMetadata


class TextNormalizer:
    """Normalizes extracted text for consistent downstream processing.

    Performs the following normalization steps:
    1. Unicode normalization to NFC form
    2. Removal of control characters (keeping newlines and tabs)
    3. Collapsing consecutive whitespace while preserving paragraph boundaries
    4. Extraction of document structure metadata (headings, sections, page numbers)

    The normalization is idempotent: normalizing twice produces the same result
    as normalizing once.
    """

    # Pattern for markdown-style headings (# Heading)
    _HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    # Pattern for page number indicators (e.g., "--- Page 3 ---" or "Page 3")
    _PAGE_NUMBER_PATTERN = re.compile(
        r"^(?:---\s*)?[Pp]age\s+(\d+)(?:\s*---)?$", re.MULTILINE
    )

    # Control characters to remove (everything in C0/C1 except \n and \t)
    _CONTROL_CHAR_PATTERN = re.compile(
        r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]"
    )

    # Pattern for collapsing horizontal whitespace (spaces and tabs on same line)
    _HORIZONTAL_WHITESPACE_PATTERN = re.compile(r"[^\S\n]+")

    # Pattern for collapsing multiple blank lines into paragraph boundary (double newline)
    _MULTIPLE_NEWLINES_PATTERN = re.compile(r"\n{3,}")

    def normalize(self, text: str) -> NormalizedText:
        """Orchestrate all normalization steps and return normalized text with structure.

        Args:
            text: Raw extracted text to normalize.

        Returns:
            NormalizedText containing the normalized text and extracted structure metadata.
        """
        # Step 1: Normalize Unicode to NFC form
        result = self._normalize_unicode(text)

        # Step 2: Remove control characters (keep \n and \t)
        result = self._remove_control_chars(result)

        # Step 3: Collapse whitespace while preserving paragraph boundaries
        result = self._collapse_whitespace(result)

        # Step 4: Extract structure metadata from the normalized text
        structure = self._extract_structure(result)

        return NormalizedText(text=result, structure=structure)

    def _normalize_unicode(self, text: str) -> str:
        """Convert text to NFC (Canonical Decomposition followed by Canonical Composition).

        NFC is the most common normalization form and ensures that equivalent
        Unicode sequences are represented identically.

        Args:
            text: Input text potentially containing non-NFC Unicode.

        Returns:
            Text normalized to NFC form.
        """
        return unicodedata.normalize("NFC", text)

    def _remove_control_chars(self, text: str) -> str:
        """Remove control characters except newlines (\\n) and tabs (\\t).

        Removes C0 control characters (U+0000-U+001F except \\t and \\n),
        DEL (U+007F), and C1 control characters (U+0080-U+009F).

        Args:
            text: Input text potentially containing control characters.

        Returns:
            Text with control characters removed.
        """
        return self._CONTROL_CHAR_PATTERN.sub("", text)

    def _collapse_whitespace(self, text: str) -> str:
        """Collapse consecutive whitespace into single spaces, preserving paragraph boundaries.

        - Consecutive horizontal whitespace (spaces, tabs) becomes a single space.
        - Three or more consecutive newlines collapse to exactly two (paragraph boundary).
        - Single and double newlines are preserved as-is.
        - Leading/trailing whitespace on each line is trimmed.

        Args:
            text: Input text with potentially excessive whitespace.

        Returns:
            Text with whitespace collapsed, paragraph boundaries preserved.
        """
        # First, collapse horizontal whitespace (spaces/tabs) into single spaces
        result = self._HORIZONTAL_WHITESPACE_PATTERN.sub(" ", text)

        # Trim leading/trailing spaces on each line (but preserve newlines)
        lines = result.split("\n")
        lines = [line.strip() for line in lines]
        result = "\n".join(lines)

        # Collapse 3+ consecutive newlines into exactly 2 (paragraph boundary)
        result = self._MULTIPLE_NEWLINES_PATTERN.sub("\n\n", result)

        # Strip leading/trailing whitespace from the entire text
        result = result.strip()

        return result

    def _extract_structure(self, text: str) -> StructureMetadata:
        """Extract document structure metadata from normalized text.

        Detects:
        - Headings: Markdown-style # prefixes (levels 1-6)
        - Sections: Regions between headings
        - Page numbers: Lines matching "Page N" or "--- Page N ---" patterns

        Args:
            text: Normalized text to extract structure from.

        Returns:
            StructureMetadata with detected headings, sections, and page numbers.
        """
        headings: list[HeadingInfo] = []
        sections: list[SectionInfo] = []
        page_numbers: list[int] = []

        # Extract headings
        for match in self._HEADING_PATTERN.finditer(text):
            level = len(match.group(1))
            heading_text = match.group(2).strip()
            offset = match.start()
            headings.append(HeadingInfo(level=level, text=heading_text, offset=offset))

        # Extract page numbers
        for match in self._PAGE_NUMBER_PATTERN.finditer(text):
            page_num = int(match.group(1))
            page_numbers.append(page_num)

        # Build sections from headings
        if headings:
            for i, heading in enumerate(headings):
                start_offset = heading.offset
                # Section ends at the next heading or end of text
                if i + 1 < len(headings):
                    end_offset = headings[i + 1].offset
                else:
                    end_offset = len(text)
                sections.append(
                    SectionInfo(
                        title=heading.text,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        level=heading.level,
                    )
                )

        return StructureMetadata(
            headings=headings,
            sections=sections,
            page_numbers=page_numbers,
        )
