"""Diff Engine service for computing line-level differences between file versions.

Uses Python's difflib.unified_diff to compute diffs, then parses the output
into structured DiffOperation objects. Handles non-text files by extracting
text via the TextExtractor service before diffing.
"""

import difflib
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.services.text_extractor import TextExtractor
from app.services.version_store import VersionStoreService


# Timeout for diff computation in seconds
DIFF_TIMEOUT_SECONDS = 30

# Text file extensions that can be decoded directly as UTF-8
_TEXT_EXTENSIONS = {".txt", ".md", ".json", ".csv"}


@dataclass
class DiffOperation:
    """Represents a single line-level change between two file versions.

    Attributes:
        operation: Type of change - "addition", "deletion", or "modification".
        line_number: The line number in the target (version_b) for additions/modifications,
                     or in the source (version_a) for deletions.
        content: The new content for additions/modifications, or removed content for deletions.
        old_content: The previous content for modifications. None for additions/deletions.
    """

    operation: str  # "addition", "deletion", "modification"
    line_number: int
    content: str
    old_content: str | None = None


@dataclass
class DiffSummary:
    """Summary counts of diff operations.

    Attributes:
        lines_added: Number of lines added.
        lines_deleted: Number of lines deleted.
        lines_modified: Number of lines modified.
    """

    lines_added: int
    lines_deleted: int
    lines_modified: int


@dataclass
class DiffResult:
    """Complete result of a diff computation.

    Attributes:
        operations: List of individual diff operations.
        summary: Summary counts of additions, deletions, and modifications.
    """

    operations: list[DiffOperation] = field(default_factory=list)
    summary: DiffSummary = field(default_factory=lambda: DiffSummary(0, 0, 0))


class DiffTimeoutError(Exception):
    """Raised when diff computation exceeds the configured timeout."""

    pass


class DiffEngine:
    """Computes line-level textual differences between two file versions.

    Uses difflib.unified_diff for diff computation, parses the output into
    structured DiffOperation objects. For non-text files, extracts text using
    the existing TextExtractor service before diffing. Enforces a 30-second
    timeout for large file diffs.
    """

    def __init__(
        self,
        text_extractor: TextExtractor,
        version_store: VersionStoreService,
    ):
        """Initialize the DiffEngine.

        Args:
            text_extractor: Service for extracting text from non-text files.
            version_store: Service for retrieving version content.
        """
        self._text_extractor = text_extractor
        self._version_store = version_store

    def compute_diff(self, file_id: int, version_a: int, version_b: int) -> DiffResult:
        """Compute line-level diff between two versions of a file.

        Retrieves content for both versions, extracts text if needed,
        then computes and parses the diff.

        Args:
            file_id: The database ID of the file.
            version_a: The source version number (old).
            version_b: The target version number (new).

        Returns:
            DiffResult containing operations and summary.

        Raises:
            FileNotFoundError: If either version doesn't exist.
            ValueError: If text extraction fails for either version.
            DiffTimeoutError: If diff computation exceeds 30 seconds.
        """
        # Retrieve content for both versions (raises FileNotFoundError if missing)
        content_a = self._version_store.get_version_content(file_id, version_a)
        content_b = self._version_store.get_version_content(file_id, version_b)

        # Extract text from both versions
        text_a = self._extract_text(content_a, file_id, version_a)
        text_b = self._extract_text(content_b, file_id, version_b)

        # Compute diff with timeout
        result = self._compute_with_timeout(text_a, text_b)
        return result

    def _extract_text(self, content: bytes, file_id: int, version_number: int) -> str:
        """Extract text from version content.

        For text-decodable content, decodes directly as UTF-8.
        For non-text content, writes to a temp file and uses TextExtractor.

        Args:
            content: Raw bytes content of the version.
            file_id: File ID (for error messages).
            version_number: Version number (for error messages).

        Returns:
            Extracted text content as a string.

        Raises:
            ValueError: If text extraction fails.
        """
        # Try direct UTF-8 decode first
        try:
            return content.decode("utf-8")
        except (UnicodeDecodeError, ValueError):
            pass

        # For non-text content, use TextExtractor with a temp file
        return self._extract_via_text_extractor(content, file_id, version_number)

    def _extract_via_text_extractor(
        self, content: bytes, file_id: int, version_number: int
    ) -> str:
        """Extract text from binary content using TextExtractor.

        Writes content to a temporary file, determines format from
        the file's database record, and invokes TextExtractor.

        Args:
            content: Binary file content.
            file_id: File ID for looking up file format.
            version_number: Version number for error messages.

        Returns:
            Extracted text string.

        Raises:
            ValueError: If extraction fails or returns None.
        """
        # Determine file extension from the version store's file record
        file_ext = self._guess_file_extension(file_id)

        # Write to temp file and extract
        suffix = file_ext if file_ext else ""
        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            result = self._text_extractor.extract(Path(tmp_path), file_ext or "")
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        if result is None:
            raise ValueError(
                f"Text extraction failed for file {file_id}, version {version_number}. "
                f"The file format may be unsupported or the content is corrupted."
            )

        return result

    def _guess_file_extension(self, file_id: int) -> str | None:
        """Determine file extension from the version store's database.

        Looks up the file path in the database to determine the extension.

        Args:
            file_id: The database ID of the file.

        Returns:
            File extension (e.g., ".pdf") or None if not determinable.
        """
        from app.models.file import File

        db = self._version_store._db
        file_record = db.query(File).filter(File.id == file_id).first()
        if file_record and file_record.path:
            _, ext = os.path.splitext(file_record.path)
            return ext.lower() if ext else None
        return None

    def _compute_with_timeout(self, text_a: str, text_b: str) -> DiffResult:
        """Compute diff with a 30-second timeout.

        Uses a thread to enforce the timeout on Windows and POSIX.

        Args:
            text_a: Source text (old version).
            text_b: Target text (new version).

        Returns:
            DiffResult with operations and summary.

        Raises:
            DiffTimeoutError: If computation exceeds 30 seconds.
        """
        result_container: list[DiffResult | None] = [None]
        error_container: list[Exception | None] = [None]

        def _worker():
            try:
                result_container[0] = self._parse_diff(text_a, text_b)
            except Exception as e:
                error_container[0] = e

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        thread.join(timeout=DIFF_TIMEOUT_SECONDS)

        if thread.is_alive():
            raise DiffTimeoutError(
                f"Diff computation exceeded {DIFF_TIMEOUT_SECONDS} second timeout."
            )

        if error_container[0] is not None:
            raise error_container[0]

        return result_container[0]  # type: ignore[return-value]

    def _parse_diff(self, text_a: str, text_b: str) -> DiffResult:
        """Parse unified diff output into structured DiffOperation objects.

        Uses difflib.unified_diff to compute the diff, then parses the
        output lines to identify additions, deletions, and modifications.
        Consecutive deletion+addition pairs on the same line are treated
        as modifications.

        Args:
            text_a: Source text (old version).
            text_b: Target text (new version).

        Returns:
            DiffResult with operations and summary.
        """
        lines_a = text_a.splitlines(keepends=True)
        lines_b = text_b.splitlines(keepends=True)

        # If texts are identical, return empty result
        if lines_a == lines_b:
            return DiffResult(
                operations=[],
                summary=DiffSummary(lines_added=0, lines_deleted=0, lines_modified=0),
            )

        # Use SequenceMatcher for more structured diff parsing
        operations: list[DiffOperation] = []
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            elif tag == "replace":
                # Lines were modified: pair up old and new lines
                old_lines = lines_a[i1:i2]
                new_lines = lines_b[j1:j2]
                min_len = min(len(old_lines), len(new_lines))

                # Pair modifications
                for k in range(min_len):
                    operations.append(
                        DiffOperation(
                            operation="modification",
                            line_number=j1 + k + 1,  # 1-indexed line in target
                            content=new_lines[k].rstrip("\n").rstrip("\r\n"),
                            old_content=old_lines[k].rstrip("\n").rstrip("\r\n"),
                        )
                    )

                # Remaining old lines are deletions
                for k in range(min_len, len(old_lines)):
                    operations.append(
                        DiffOperation(
                            operation="deletion",
                            line_number=i1 + k + 1,  # 1-indexed line in source
                            content=old_lines[k].rstrip("\n").rstrip("\r\n"),
                        )
                    )

                # Remaining new lines are additions
                for k in range(min_len, len(new_lines)):
                    operations.append(
                        DiffOperation(
                            operation="addition",
                            line_number=j1 + k + 1,  # 1-indexed line in target
                            content=new_lines[k].rstrip("\n").rstrip("\r\n"),
                        )
                    )

            elif tag == "delete":
                for k in range(i1, i2):
                    operations.append(
                        DiffOperation(
                            operation="deletion",
                            line_number=k + 1,  # 1-indexed line in source
                            content=lines_a[k].rstrip("\n").rstrip("\r\n"),
                        )
                    )

            elif tag == "insert":
                for k in range(j1, j2):
                    operations.append(
                        DiffOperation(
                            operation="addition",
                            line_number=k + 1,  # 1-indexed line in target
                            content=lines_b[k].rstrip("\n").rstrip("\r\n"),
                        )
                    )

        # Compute summary
        additions = sum(1 for op in operations if op.operation == "addition")
        deletions = sum(1 for op in operations if op.operation == "deletion")
        modifications = sum(1 for op in operations if op.operation == "modification")

        summary = DiffSummary(
            lines_added=additions,
            lines_deleted=deletions,
            lines_modified=modifications,
        )

        return DiffResult(operations=operations, summary=summary)
