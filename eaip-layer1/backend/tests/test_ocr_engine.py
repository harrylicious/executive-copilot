"""Unit tests for the OCR Engine.

Tests the OCREngine class including:
- File type detection (_needs_ocr)
- Confidence threshold flagging
- Provider selection
- Error handling for missing files and unsupported types
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.ingestion.ocr_engine import IMAGE_EXTENSIONS, OCREngine, OCRResult


class TestNeedsOCR:
    """Tests for _needs_ocr() method."""

    def test_image_files_always_need_ocr(self, tmp_path: Path):
        """Image files (.png, .jpg, .tiff, etc.) always need OCR."""
        engine = OCREngine()
        for ext in IMAGE_EXTENSIONS:
            file = tmp_path / f"test{ext}"
            file.write_bytes(b"\x00" * 10)
            assert engine._needs_ocr(file) is True, f"Expected {ext} to need OCR"

    def test_text_files_do_not_need_ocr(self, tmp_path: Path):
        """Text-based files (.txt, .md, .json, etc.) do not need OCR."""
        engine = OCREngine()
        for ext in [".txt", ".md", ".json", ".csv", ".docx", ".xlsx"]:
            file = tmp_path / f"test{ext}"
            file.write_bytes(b"some content")
            assert engine._needs_ocr(file) is False, f"Expected {ext} to NOT need OCR"

    @patch("app.services.ingestion.ocr_engine.OCREngine._is_image_only_pdf")
    def test_pdf_delegates_to_image_only_check(self, mock_check, tmp_path: Path):
        """PDF files delegate to _is_image_only_pdf for the decision."""
        engine = OCREngine()
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4")

        mock_check.return_value = True
        assert engine._needs_ocr(pdf_file) is True

        mock_check.return_value = False
        assert engine._needs_ocr(pdf_file) is False


class TestExtractText:
    """Tests for extract_text() method."""

    def test_missing_file_returns_error(self, tmp_path: Path):
        """Non-existent file returns error result with manual review flag."""
        engine = OCREngine()
        result = engine.extract_text(tmp_path / "nonexistent.png")

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.needs_manual_review is True
        assert result.error is not None
        assert "not found" in result.error.lower()

    def test_file_not_needing_ocr_returns_empty(self, tmp_path: Path):
        """Files that don't need OCR return empty result without review flag."""
        engine = OCREngine()
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("Hello world")

        result = engine.extract_text(txt_file)

        assert result.text == ""
        assert result.confidence == 1.0
        assert result.needs_manual_review is False
        assert "does not need OCR" in result.error

    def test_confidence_below_threshold_flags_review(self, tmp_path: Path):
        """Results with confidence below threshold are flagged for manual review."""
        engine = OCREngine(confidence_threshold=0.6)
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(engine, "_run_tesseract", return_value=("some text", 0.4)):
            result = engine.extract_text(img_file)

        assert result.needs_manual_review is True
        assert result.confidence == 0.4
        assert result.text == "some text"

    def test_confidence_at_threshold_no_review(self, tmp_path: Path):
        """Results with confidence exactly at threshold are NOT flagged."""
        engine = OCREngine(confidence_threshold=0.6)
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(engine, "_run_tesseract", return_value=("some text", 0.6)):
            result = engine.extract_text(img_file)

        assert result.needs_manual_review is False
        assert result.confidence == 0.6

    def test_confidence_above_threshold_no_review(self, tmp_path: Path):
        """Results with confidence above threshold are NOT flagged."""
        engine = OCREngine(confidence_threshold=0.6)
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(engine, "_run_tesseract", return_value=("clear text", 0.95)):
            result = engine.extract_text(img_file)

        assert result.needs_manual_review is False
        assert result.confidence == 0.95
        assert result.text == "clear text"

    def test_textract_provider_selection(self, tmp_path: Path):
        """When provider is 'textract', _run_textract is called."""
        engine = OCREngine(ocr_provider="textract")
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(
            engine, "_run_textract", return_value=("textract text", 0.9)
        ) as mock_textract:
            result = engine.extract_text(img_file)

        mock_textract.assert_called_once_with(img_file)
        assert result.text == "textract text"
        assert result.provider == "textract"

    def test_tesseract_provider_selection(self, tmp_path: Path):
        """When provider is 'tesseract', _run_tesseract is called."""
        engine = OCREngine(ocr_provider="tesseract")
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(
            engine, "_run_tesseract", return_value=("tesseract text", 0.85)
        ) as mock_tesseract:
            result = engine.extract_text(img_file)

        mock_tesseract.assert_called_once_with(img_file)
        assert result.text == "tesseract text"
        assert result.provider == "tesseract"

    def test_ocr_exception_returns_error_result(self, tmp_path: Path):
        """OCR processing exceptions are caught and returned as error results."""
        engine = OCREngine()
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch.object(
            engine, "_run_tesseract", side_effect=RuntimeError("Tesseract not found")
        ):
            result = engine.extract_text(img_file)

        assert result.text == ""
        assert result.confidence == 0.0
        assert result.needs_manual_review is True
        assert "Tesseract not found" in result.error


class TestRunTextract:
    """Tests for _run_textract() stub."""

    def test_textract_raises_not_implemented(self, tmp_path: Path):
        """Textract stub raises NotImplementedError."""
        engine = OCREngine()
        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        with pytest.raises(NotImplementedError) as exc_info:
            engine._run_textract(img_file)

        assert "not yet implemented" in str(exc_info.value).lower()


class TestOCRResult:
    """Tests for OCRResult dataclass."""

    def test_default_values(self):
        """OCRResult has sensible defaults."""
        result = OCRResult(text="hello", confidence=0.9)
        assert result.needs_manual_review is False
        assert result.provider == "tesseract"
        assert result.page_count == 1
        assert result.error is None

    def test_custom_values(self):
        """OCRResult accepts custom values."""
        result = OCRResult(
            text="extracted",
            confidence=0.5,
            needs_manual_review=True,
            provider="textract",
            page_count=3,
            error="low quality",
        )
        assert result.text == "extracted"
        assert result.confidence == 0.5
        assert result.needs_manual_review is True
        assert result.provider == "textract"
        assert result.page_count == 3
        assert result.error == "low quality"
