"""Schema validation service for the ingestion pipeline.

Verifies file extension support, magic bytes, and format-specific
structural validity before a file proceeds through the pipeline.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of schema validation.

    Attributes:
        is_valid: Whether the file passed all validation checks.
        error_code: Machine-readable error code if validation failed.
        error_message: Human-readable description of the failure.
        details: Additional context about the validation outcome.
    """

    is_valid: bool
    error_code: str | None = None
    error_message: str | None = None
    details: dict = field(default_factory=dict)


class SchemaValidator:
    """Validates file schema: extension, magic bytes, and structural integrity.

    Checks that incoming files have a supported extension, that their
    binary content matches the declared format (magic bytes), and that
    format-specific structural rules are satisfied (e.g., valid JSON,
    valid PDF header).
    """

    SUPPORTED_FORMATS: set[str] = {
        ".txt",
        ".md",
        ".json",
        ".docx",
        ".pdf",
        ".csv",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".tiff",
    }

    # Magic bytes signatures for binary formats.
    # Text-based formats (.txt, .md, .json, .csv) don't have magic bytes.
    MAGIC_BYTES: dict[str, bytes] = {
        ".pdf": b"%PDF",
        ".docx": b"PK\x03\x04",  # ZIP archive (OOXML)
        ".xlsx": b"PK\x03\x04",  # ZIP archive (OOXML)
        ".xls": b"\xd0\xcf\x11\xe0",  # OLE2 Compound Document
        ".png": b"\x89PNG",
        ".jpg": b"\xff\xd8\xff",
        ".tiff": b"II\x2a\x00",  # Little-endian TIFF (also accepts big-endian below)
    }

    # Big-endian TIFF alternative signature
    _TIFF_BIG_ENDIAN: bytes = b"MM\x00\x2a"

    def validate(self, file_path: Path, declared_format: str) -> ValidationResult:
        """Validate a file against schema rules.

        Performs three checks in order:
        1. Extension is in the supported formats set.
        2. Magic bytes match the declared format (for binary formats).
        3. Format-specific structural checks pass.

        Args:
            file_path: Path to the file to validate.
            declared_format: The declared file extension (e.g., ".pdf").

        Returns:
            ValidationResult indicating success or failure with details.
        """
        # Normalize the declared format
        fmt = declared_format.lower()
        if not fmt.startswith("."):
            fmt = f".{fmt}"

        # Step 1: Check extension support
        if fmt not in self.SUPPORTED_FORMATS:
            return ValidationResult(
                is_valid=False,
                error_code="UNSUPPORTED_FORMAT",
                error_message=f"File format '{fmt}' is not supported.",
                details={"declared_format": fmt, "supported_formats": sorted(self.SUPPORTED_FORMATS)},
            )

        # Verify the file exists and is readable
        if not file_path.exists():
            return ValidationResult(
                is_valid=False,
                error_code="FILE_NOT_FOUND",
                error_message=f"File not found: {file_path}",
                details={"file_path": str(file_path)},
            )

        if not file_path.is_file():
            return ValidationResult(
                is_valid=False,
                error_code="NOT_A_FILE",
                error_message=f"Path is not a regular file: {file_path}",
                details={"file_path": str(file_path)},
            )

        # Step 2: Magic bytes verification (for binary formats)
        if fmt in self.MAGIC_BYTES:
            if not self._check_magic_bytes(file_path, fmt):
                return ValidationResult(
                    is_valid=False,
                    error_code="MAGIC_BYTES_MISMATCH",
                    error_message=(
                        f"File content does not match declared format '{fmt}'. "
                        "The file may be corrupted or mislabeled."
                    ),
                    details={"declared_format": fmt, "file_path": str(file_path)},
                )

        # Step 3: Format-specific structural checks
        structural_result = self._run_structural_checks(file_path, fmt)
        if structural_result is not None:
            return structural_result

        return ValidationResult(is_valid=True, details={"declared_format": fmt})

    def _check_magic_bytes(self, file_path: Path, expected_format: str) -> bool:
        """Verify that file content starts with expected magic bytes.

        Args:
            file_path: Path to the file to check.
            expected_format: The expected format extension (e.g., ".pdf").

        Returns:
            True if magic bytes match, False otherwise.
        """
        expected_bytes = self.MAGIC_BYTES.get(expected_format)
        if expected_bytes is None:
            # No magic bytes defined for this format
            return True

        try:
            num_bytes = len(expected_bytes)
            with open(file_path, "rb") as f:
                header = f.read(num_bytes)

            if len(header) < num_bytes:
                return False

            # Special case: TIFF can be little-endian or big-endian
            if expected_format == ".tiff":
                return header == expected_bytes or header == self._TIFF_BIG_ENDIAN

            return header == expected_bytes
        except OSError as e:
            logger.error(f"Failed to read magic bytes from '{file_path}': {e}")
            return False

    def _validate_json(self, file_path: Path) -> bool:
        """Verify that a file contains valid, parseable JSON.

        Args:
            file_path: Path to the JSON file.

        Returns:
            True if the file is valid JSON, False otherwise.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                json.load(f)
            return True
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug(f"JSON validation failed for '{file_path}': {e}")
            return False
        except OSError as e:
            logger.error(f"Failed to read JSON file '{file_path}': {e}")
            return False

    def _validate_pdf(self, file_path: Path) -> bool:
        """Verify that a file has a valid PDF header signature.

        Checks that the file starts with the %PDF- marker followed by
        a version number.

        Args:
            file_path: Path to the PDF file.

        Returns:
            True if the file has a valid PDF header, False otherwise.
        """
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)

            # PDF header must start with %PDF- followed by version (e.g., %PDF-1.4)
            if not header.startswith(b"%PDF-"):
                return False

            # Check that version part is a digit, dot, digit pattern
            version_part = header[5:8]
            if len(version_part) < 3:
                return False

            # Version should be like "1.4" or "2.0"
            if not (version_part[0:1].isdigit() and version_part[1:2] == b"." and version_part[2:3].isdigit()):
                return False

            return True
        except OSError as e:
            logger.error(f"Failed to read PDF file '{file_path}': {e}")
            return False

    def _run_structural_checks(self, file_path: Path, fmt: str) -> ValidationResult | None:
        """Run format-specific structural validation.

        Args:
            file_path: Path to the file.
            fmt: Normalized file extension.

        Returns:
            A ValidationResult with failure details if the check fails,
            or None if the check passes (or no check is needed).
        """
        if fmt == ".json":
            if not self._validate_json(file_path):
                return ValidationResult(
                    is_valid=False,
                    error_code="INVALID_JSON",
                    error_message="File content is not valid JSON.",
                    details={"declared_format": fmt, "file_path": str(file_path)},
                )

        elif fmt == ".pdf":
            if not self._validate_pdf(file_path):
                return ValidationResult(
                    is_valid=False,
                    error_code="INVALID_PDF",
                    error_message="File does not contain a valid PDF header.",
                    details={"declared_format": fmt, "file_path": str(file_path)},
                )

        return None
