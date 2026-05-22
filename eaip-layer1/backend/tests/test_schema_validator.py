"""Unit tests for the SchemaValidator service."""

import json
import tempfile
from pathlib import Path

import pytest

from app.services.ingestion.schema_validator import SchemaValidator, ValidationResult


@pytest.fixture
def validator():
    """Create a SchemaValidator instance."""
    return SchemaValidator()


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


class TestSupportedFormats:
    """Tests for extension support checking."""

    def test_all_supported_formats_accepted(self, validator, tmp_dir):
        """All declared supported formats should pass extension check."""
        for fmt in validator.SUPPORTED_FORMATS:
            file_path = tmp_dir / f"test{fmt}"
            # Create minimal valid content for each format
            if fmt in (".txt", ".md", ".csv"):
                file_path.write_text("content")
            elif fmt == ".json":
                file_path.write_text('{"key": "value"}')
            elif fmt == ".pdf":
                file_path.write_bytes(b"%PDF-1.4\n")
            elif fmt in (".docx", ".xlsx"):
                file_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
            elif fmt == ".xls":
                file_path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
            elif fmt == ".png":
                file_path.write_bytes(b"\x89PNG" + b"\x00" * 100)
            elif fmt == ".jpg":
                file_path.write_bytes(b"\xff\xd8\xff" + b"\x00" * 100)
            elif fmt == ".tiff":
                file_path.write_bytes(b"II\x2a\x00" + b"\x00" * 100)

            result = validator.validate(file_path, fmt)
            assert result.is_valid, f"Format {fmt} should be valid, got: {result.error_message}"

    def test_unsupported_format_rejected(self, validator, tmp_dir):
        """Unsupported formats should be rejected."""
        file_path = tmp_dir / "test.exe"
        file_path.write_bytes(b"MZ\x00\x00")
        result = validator.validate(file_path, ".exe")
        assert not result.is_valid
        assert result.error_code == "UNSUPPORTED_FORMAT"

    def test_format_normalized_without_dot(self, validator, tmp_dir):
        """Format without leading dot should be normalized."""
        file_path = tmp_dir / "test.txt"
        file_path.write_text("hello")
        result = validator.validate(file_path, "txt")
        assert result.is_valid

    def test_format_case_insensitive(self, validator, tmp_dir):
        """Format check should be case-insensitive."""
        file_path = tmp_dir / "test.txt"
        file_path.write_text("hello")
        result = validator.validate(file_path, ".TXT")
        assert result.is_valid


class TestMagicBytes:
    """Tests for magic bytes verification."""

    def test_pdf_valid_magic_bytes(self, validator, tmp_dir):
        """PDF with correct magic bytes should pass."""
        file_path = tmp_dir / "test.pdf"
        file_path.write_bytes(b"%PDF-1.7\nrest of content")
        result = validator.validate(file_path, ".pdf")
        assert result.is_valid

    def test_pdf_invalid_magic_bytes(self, validator, tmp_dir):
        """PDF with wrong magic bytes should fail."""
        file_path = tmp_dir / "test.pdf"
        file_path.write_bytes(b"not a pdf file")
        result = validator.validate(file_path, ".pdf")
        assert not result.is_valid
        assert result.error_code == "MAGIC_BYTES_MISMATCH"

    def test_png_valid_magic_bytes(self, validator, tmp_dir):
        """PNG with correct magic bytes should pass."""
        file_path = tmp_dir / "test.png"
        file_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        result = validator.validate(file_path, ".png")
        assert result.is_valid

    def test_jpg_valid_magic_bytes(self, validator, tmp_dir):
        """JPEG with correct magic bytes should pass."""
        file_path = tmp_dir / "test.jpg"
        file_path.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
        result = validator.validate(file_path, ".jpg")
        assert result.is_valid

    def test_docx_valid_magic_bytes(self, validator, tmp_dir):
        """DOCX (ZIP) with correct magic bytes should pass."""
        file_path = tmp_dir / "test.docx"
        file_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        result = validator.validate(file_path, ".docx")
        assert result.is_valid

    def test_xlsx_valid_magic_bytes(self, validator, tmp_dir):
        """XLSX (ZIP) with correct magic bytes should pass."""
        file_path = tmp_dir / "test.xlsx"
        file_path.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
        result = validator.validate(file_path, ".xlsx")
        assert result.is_valid

    def test_xls_valid_magic_bytes(self, validator, tmp_dir):
        """XLS (OLE2) with correct magic bytes should pass."""
        file_path = tmp_dir / "test.xls"
        file_path.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 100)
        result = validator.validate(file_path, ".xls")
        assert result.is_valid

    def test_tiff_little_endian(self, validator, tmp_dir):
        """TIFF with little-endian magic bytes should pass."""
        file_path = tmp_dir / "test.tiff"
        file_path.write_bytes(b"II\x2a\x00" + b"\x00" * 100)
        result = validator.validate(file_path, ".tiff")
        assert result.is_valid

    def test_tiff_big_endian(self, validator, tmp_dir):
        """TIFF with big-endian magic bytes should pass."""
        file_path = tmp_dir / "test.tiff"
        file_path.write_bytes(b"MM\x00\x2a" + b"\x00" * 100)
        result = validator.validate(file_path, ".tiff")
        assert result.is_valid

    def test_text_formats_skip_magic_bytes(self, validator, tmp_dir):
        """Text-based formats should not require magic bytes."""
        for fmt in (".txt", ".md", ".csv"):
            file_path = tmp_dir / f"test{fmt}"
            file_path.write_text("any content here")
            result = validator.validate(file_path, fmt)
            assert result.is_valid, f"Text format {fmt} should skip magic bytes check"

    def test_empty_file_fails_magic_bytes(self, validator, tmp_dir):
        """Empty file should fail magic bytes check for binary formats."""
        file_path = tmp_dir / "test.pdf"
        file_path.write_bytes(b"")
        result = validator.validate(file_path, ".pdf")
        assert not result.is_valid
        assert result.error_code == "MAGIC_BYTES_MISMATCH"


class TestJsonValidation:
    """Tests for JSON structural validation."""

    def test_valid_json_object(self, validator, tmp_dir):
        """Valid JSON object should pass."""
        file_path = tmp_dir / "test.json"
        file_path.write_text(json.dumps({"key": "value", "nested": {"a": 1}}))
        result = validator.validate(file_path, ".json")
        assert result.is_valid

    def test_valid_json_array(self, validator, tmp_dir):
        """Valid JSON array should pass."""
        file_path = tmp_dir / "test.json"
        file_path.write_text(json.dumps([1, 2, 3, "hello"]))
        result = validator.validate(file_path, ".json")
        assert result.is_valid

    def test_invalid_json(self, validator, tmp_dir):
        """Invalid JSON should fail with INVALID_JSON error."""
        file_path = tmp_dir / "test.json"
        file_path.write_text("{invalid json content")
        result = validator.validate(file_path, ".json")
        assert not result.is_valid
        assert result.error_code == "INVALID_JSON"

    def test_empty_json_file(self, validator, tmp_dir):
        """Empty file is not valid JSON."""
        file_path = tmp_dir / "test.json"
        file_path.write_text("")
        result = validator.validate(file_path, ".json")
        assert not result.is_valid
        assert result.error_code == "INVALID_JSON"


class TestPdfValidation:
    """Tests for PDF structural validation."""

    def test_valid_pdf_header(self, validator, tmp_dir):
        """PDF with valid header should pass."""
        file_path = tmp_dir / "test.pdf"
        file_path.write_bytes(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        result = validator.validate(file_path, ".pdf")
        assert result.is_valid

    def test_pdf_version_2(self, validator, tmp_dir):
        """PDF version 2.0 should pass."""
        file_path = tmp_dir / "test.pdf"
        file_path.write_bytes(b"%PDF-2.0\n")
        result = validator.validate(file_path, ".pdf")
        assert result.is_valid

    def test_pdf_missing_version(self, validator, tmp_dir):
        """PDF without proper version should fail."""
        file_path = tmp_dir / "test.pdf"
        # Has %PDF but no valid version
        file_path.write_bytes(b"%PDF-\x00\x00\x00")
        result = validator.validate(file_path, ".pdf")
        assert not result.is_valid
        assert result.error_code == "INVALID_PDF"


class TestFileExistence:
    """Tests for file existence and accessibility."""

    def test_nonexistent_file(self, validator):
        """Non-existent file should fail with FILE_NOT_FOUND."""
        result = validator.validate(Path("/nonexistent/file.txt"), ".txt")
        assert not result.is_valid
        assert result.error_code == "FILE_NOT_FOUND"

    def test_directory_instead_of_file(self, validator, tmp_dir):
        """Directory path should fail with NOT_A_FILE."""
        result = validator.validate(tmp_dir, ".txt")
        assert not result.is_valid
        assert result.error_code == "NOT_A_FILE"


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_success_result(self):
        """Successful result should have is_valid=True and no errors."""
        result = ValidationResult(is_valid=True)
        assert result.is_valid
        assert result.error_code is None
        assert result.error_message is None
        assert result.details == {}

    def test_failure_result(self):
        """Failed result should carry error details."""
        result = ValidationResult(
            is_valid=False,
            error_code="TEST_ERROR",
            error_message="Something went wrong",
            details={"key": "value"},
        )
        assert not result.is_valid
        assert result.error_code == "TEST_ERROR"
        assert result.error_message == "Something went wrong"
        assert result.details == {"key": "value"}
