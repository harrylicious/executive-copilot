"""Unit tests for the TextNormalizer service."""

import unicodedata

import pytest

from app.services.ingestion.normalizer import (
    HeadingInfo,
    NormalizedText,
    SectionInfo,
    StructureMetadata,
    TextNormalizer,
)


@pytest.fixture
def normalizer() -> TextNormalizer:
    """Create a TextNormalizer instance for testing."""
    return TextNormalizer()


class TestNormalizeUnicode:
    """Tests for _normalize_unicode() method."""

    def test_nfc_normalization_of_decomposed_chars(self, normalizer: TextNormalizer):
        # e + combining acute accent -> precomposed é
        decomposed = "caf\u0065\u0301"
        result = normalizer._normalize_unicode(decomposed)
        assert unicodedata.is_normalized("NFC", result)
        assert result == "café"

    def test_already_nfc_text_unchanged(self, normalizer: TextNormalizer):
        text = "Hello World café"
        result = normalizer._normalize_unicode(text)
        assert result == text

    def test_empty_string(self, normalizer: TextNormalizer):
        assert normalizer._normalize_unicode("") == ""

    def test_ascii_only_unchanged(self, normalizer: TextNormalizer):
        text = "Plain ASCII text 123"
        assert normalizer._normalize_unicode(text) == text


class TestCollapseWhitespace:
    """Tests for _collapse_whitespace() method."""

    def test_multiple_spaces_collapsed(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("Hello   World")
        assert result == "Hello World"

    def test_tabs_collapsed_to_space(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("Hello\t\tWorld")
        assert result == "Hello World"

    def test_paragraph_boundary_preserved(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("Para 1\n\nPara 2")
        assert result == "Para 1\n\nPara 2"

    def test_triple_newlines_collapsed_to_double(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("Para 1\n\n\n\nPara 2")
        assert result == "Para 1\n\nPara 2"

    def test_single_newline_preserved(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("Line 1\nLine 2")
        assert result == "Line 1\nLine 2"

    def test_leading_trailing_whitespace_stripped(self, normalizer: TextNormalizer):
        result = normalizer._collapse_whitespace("  Hello World  ")
        assert result == "Hello World"

    def test_empty_string(self, normalizer: TextNormalizer):
        assert normalizer._collapse_whitespace("") == ""

    def test_only_whitespace(self, normalizer: TextNormalizer):
        assert normalizer._collapse_whitespace("   \t\t  ") == ""


class TestRemoveControlChars:
    """Tests for _remove_control_chars() method."""

    def test_null_byte_removed(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("Hello\x00World")
        assert result == "HelloWorld"

    def test_c0_controls_removed(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("A\x01\x02\x03B")
        assert result == "AB"

    def test_newline_preserved(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("Hello\nWorld")
        assert result == "Hello\nWorld"

    def test_tab_preserved(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("Hello\tWorld")
        assert result == "Hello\tWorld"

    def test_c1_controls_removed(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("A\x80\x81\x9fB")
        assert result == "AB"

    def test_del_removed(self, normalizer: TextNormalizer):
        result = normalizer._remove_control_chars("Hello\x7fWorld")
        assert result == "HelloWorld"

    def test_normal_text_unchanged(self, normalizer: TextNormalizer):
        text = "Normal text with spaces and punctuation!"
        assert normalizer._remove_control_chars(text) == text


class TestExtractStructure:
    """Tests for _extract_structure() method."""

    def test_markdown_headings_detected(self, normalizer: TextNormalizer):
        text = "# Title\n\nContent\n\n## Section\n\nMore content"
        structure = normalizer._extract_structure(text)
        assert len(structure.headings) == 2
        assert structure.headings[0].level == 1
        assert structure.headings[0].text == "Title"
        assert structure.headings[1].level == 2
        assert structure.headings[1].text == "Section"

    def test_all_heading_levels(self, normalizer: TextNormalizer):
        text = "# H1\n## H2\n### H3\n#### H4\n##### H5\n###### H6"
        structure = normalizer._extract_structure(text)
        assert len(structure.headings) == 6
        for i, heading in enumerate(structure.headings):
            assert heading.level == i + 1

    def test_page_numbers_detected(self, normalizer: TextNormalizer):
        text = "Content\n\nPage 1\n\nMore content\n\n--- Page 5 ---"
        structure = normalizer._extract_structure(text)
        assert structure.page_numbers == [1, 5]

    def test_sections_built_from_headings(self, normalizer: TextNormalizer):
        text = "# First\n\nContent 1\n\n## Second\n\nContent 2"
        structure = normalizer._extract_structure(text)
        assert len(structure.sections) == 2
        assert structure.sections[0].title == "First"
        assert structure.sections[0].level == 1
        assert structure.sections[1].title == "Second"
        assert structure.sections[1].level == 2

    def test_section_offsets_correct(self, normalizer: TextNormalizer):
        text = "# First\n\nContent\n\n## Second\n\nMore"
        structure = normalizer._extract_structure(text)
        # First section starts at 0, ends at start of second heading
        assert structure.sections[0].start_offset == 0
        assert structure.sections[0].end_offset == structure.sections[1].start_offset
        # Last section ends at end of text
        assert structure.sections[1].end_offset == len(text)

    def test_no_headings_produces_empty_structure(self, normalizer: TextNormalizer):
        text = "Just plain text without any headings."
        structure = normalizer._extract_structure(text)
        assert structure.headings == []
        assert structure.sections == []
        assert structure.page_numbers == []

    def test_heading_offset_is_correct(self, normalizer: TextNormalizer):
        text = "Preamble\n\n# Heading"
        structure = normalizer._extract_structure(text)
        assert structure.headings[0].offset == text.index("# Heading")


class TestNormalize:
    """Tests for the full normalize() orchestration method."""

    def test_returns_normalized_text_dataclass(self, normalizer: TextNormalizer):
        result = normalizer.normalize("Hello World")
        assert isinstance(result, NormalizedText)
        assert isinstance(result.structure, StructureMetadata)

    def test_full_pipeline(self, normalizer: TextNormalizer):
        text = "# Title\n\n\n\n  Multiple   spaces  \n\n## Section\n\nContent\x00here"
        result = normalizer.normalize(text)
        # Whitespace collapsed, control chars removed, structure extracted
        assert "  " not in result.text
        assert "\x00" not in result.text
        assert "\n\n\n" not in result.text
        assert len(result.structure.headings) == 2

    def test_idempotence(self, normalizer: TextNormalizer):
        text = "# Heading\n\n\n\nSome   text\n\t\twith tabs\n\nAnother paragraph"
        r1 = normalizer.normalize(text)
        r2 = normalizer.normalize(r1.text)
        assert r1.text == r2.text

    def test_empty_input(self, normalizer: TextNormalizer):
        result = normalizer.normalize("")
        assert result.text == ""
        assert result.structure.headings == []
        assert result.structure.sections == []
        assert result.structure.page_numbers == []

    def test_unicode_and_structure_combined(self, normalizer: TextNormalizer):
        # Decomposed é in heading
        text = "# Caf\u0065\u0301\n\nContent"
        result = normalizer.normalize(text)
        assert unicodedata.is_normalized("NFC", result.text)
        assert result.structure.headings[0].text == "Café"
