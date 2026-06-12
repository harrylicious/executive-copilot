"""PII Redactor service for the ingestion pipeline.

Detects and masks personally identifiable information (PII) including
Indonesian NIK numbers, phone numbers, email addresses, and person names.
Replaces detected PII with category-specific placeholders and logs
character offsets for audit purposes.
"""

import logging
import re
from dataclasses import dataclass, field

from app.config import ingestion_settings

logger = logging.getLogger(__name__)


@dataclass
class PIISpan:
    """A detected PII span in the text.

    Attributes:
        category: PII category (NIK, PHONE, EMAIL, NAME).
        start: Start character offset in the original text.
        end: End character offset in the original text.
        placeholder: Replacement placeholder string.
        confidence: Detection confidence score (0.0 to 1.0).
        flagged_for_review: Whether this span needs manual review.
    """

    category: str
    start: int
    end: int
    placeholder: str
    confidence: float
    flagged_for_review: bool = False


@dataclass
class RedactionResult:
    """Result of PII redaction on a text.

    Attributes:
        redacted_text: The text with PII replaced by placeholders.
        spans: List of all detected PII spans with metadata.
    """

    redacted_text: str
    spans: list[PIISpan] = field(default_factory=list)


class PIIRedactor:
    """Detects and masks PII with category-specific placeholders.

    Supports detection of:
    - Indonesian NIK numbers (exactly 16 consecutive digits)
    - Indonesian phone numbers (+62xxx, 08xxx, 021-xxx formats)
    - Email addresses
    - Person names (heuristic: capitalized multi-word sequences)

    PII patterns inside code blocks (triple backticks or 4+ space
    indentation) are skipped. Ambiguous matches below the confidence
    threshold are flagged for manual review instead of being redacted.
    """

    # Regex for Indonesian NIK: exactly 16 consecutive digits,
    # not preceded or followed by another digit
    _NIK_PATTERN = re.compile(r"(?<!\d)\d{16}(?!\d)")

    # Regex for Indonesian phone numbers:
    # +62 followed by digits (with optional separators)
    # 08xx followed by digits (with optional separators)
    # Area codes like 021, 022, 031 followed by digits (with optional separators)
    _PHONE_PATTERN = re.compile(
        r"(?<!\w)"
        r"(?:"
        r"\+62[\s\-]?\d[\d\s\-]{6,12}\d"  # +62 format
        r"|"
        r"08\d[\d\s\-]{6,11}\d"  # 08xx format
        r"|"
        r"0(?:21|22|24|31|61|71|411|511|711|21|251|253|254|261|263|264|271|272|274|275|281|282|283|284|285|286|287|289|291|292|293|294|295|296|297|298|341|342|343|344|351|352|353|354|355|356|357|358|361|362|363|364|365|366|368|370|371|372|373|374|376|380|381|382|383|384|385|386|387|388|389)[\s\-]?\d[\d\s\-]{4,9}\d"  # Area code format
        r")"
        r"(?!\w)"
    )

    # Regex for email addresses
    _EMAIL_PATTERN = re.compile(
        r"(?<![.\w])"
        r"[a-zA-Z0-9](?:[a-zA-Z0-9._%+\-]*[a-zA-Z0-9])?@"
        r"[a-zA-Z0-9](?:[a-zA-Z0-9.\-]*[a-zA-Z0-9])?\.[a-zA-Z]{2,}"
        r"(?![.\w])"
    )

    # Regex for person names: sequences of 2-4 capitalized words
    # (heuristic approach for Indonesian/general names)
    _NAME_PATTERN = re.compile(
        r"(?<![.\w])"
        r"(?:[A-Z][a-z]{1,20})"  # First name (capitalized)
        r"(?:\s+[A-Z][a-z]{1,20}){1,3}"  # 1-3 additional capitalized words
        r"(?![.\w])"
    )

    # Common words that look like names but aren't
    _NAME_EXCLUSIONS: set[str] = {
        "The", "This", "That", "These", "Those", "There", "Their",
        "They", "Then", "Than", "What", "When", "Where", "Which",
        "While", "With", "Would", "Will", "Were", "Was", "Have",
        "Has", "Had", "How", "Here", "His", "Her", "Him",
        "Some", "Such", "Each", "Every", "Other", "Another",
        "Many", "Much", "Most", "More", "Less", "Few",
        "All", "Any", "Both", "Either", "Neither",
        "New", "Old", "Good", "Bad", "Big", "Small",
        "First", "Last", "Next", "Long", "Short",
        "High", "Low", "Great", "Little",
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December",
        "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
        "Saturday", "Sunday",
        "Section", "Chapter", "Table", "Figure", "Page",
        "Note", "See", "Also", "For", "From", "Into",
        "About", "After", "Before", "Between", "Under", "Over",
        "Data", "File", "System", "Service", "Server", "Client",
        "Error", "Warning", "Info", "Debug", "Status",
        "True", "False", "None", "Null",
        "Class", "Function", "Method", "Module", "Package",
        "Return", "Import", "Export", "Default",
        "Public", "Private", "Protected", "Static",
        "Abstract", "Interface", "Implements", "Extends",
    }

    def __init__(self) -> None:
        """Initialize the PII Redactor with confidence threshold from config."""
        self._confidence_threshold = ingestion_settings.pii_confidence_threshold

    def redact(self, text: str) -> RedactionResult:
        """Detect and redact PII from text.

        Scans for NIK numbers, phone numbers, email addresses, and
        person names. Replaces high-confidence matches with category
        placeholders. Low-confidence matches are flagged for review
        but not redacted.

        Args:
            text: The input text to scan for PII.

        Returns:
            RedactionResult with redacted text and span metadata.
        """
        if not text:
            return RedactionResult(redacted_text=text, spans=[])

        # Detect all PII spans
        all_spans: list[PIISpan] = []
        all_spans.extend(self._detect_nik(text))
        all_spans.extend(self._detect_phone(text))
        all_spans.extend(self._detect_email(text))
        all_spans.extend(self._detect_names(text))

        # Filter out spans that are inside code blocks
        filtered_spans = [
            span for span in all_spans
            if not self._is_in_code_block(text, span)
        ]

        # Sort spans by start position (descending) for safe replacement
        filtered_spans.sort(key=lambda s: s.start, reverse=True)

        # Remove overlapping spans (keep higher confidence, or earlier detection)
        non_overlapping = self._remove_overlaps(filtered_spans)

        # Sort back to ascending for the result
        non_overlapping.sort(key=lambda s: s.start)

        # Apply confidence-based flagging
        for span in non_overlapping:
            if span.confidence < self._confidence_threshold:
                span.flagged_for_review = True

        # Build redacted text (replace from end to start to preserve offsets)
        redacted_text = text
        for span in sorted(non_overlapping, key=lambda s: s.start, reverse=True):
            if not span.flagged_for_review:
                redacted_text = (
                    redacted_text[:span.start]
                    + span.placeholder
                    + redacted_text[span.end:]
                )

        # Log redaction audit info
        for span in non_overlapping:
            action = "flagged" if span.flagged_for_review else "redacted"
            logger.info(
                f"PII {action}: category={span.category}, "
                f"start={span.start}, end={span.end}, "
                f"confidence={span.confidence:.2f}"
            )

        return RedactionResult(redacted_text=redacted_text, spans=non_overlapping)

    def _detect_nik(self, text: str) -> list[PIISpan]:
        """Detect Indonesian NIK numbers (exactly 16 consecutive digits).

        NIK (Nomor Induk Kependudukan) is the Indonesian national
        identification number consisting of exactly 16 digits.

        Args:
            text: Text to scan for NIK patterns.

        Returns:
            List of PIISpan objects for detected NIK numbers.
        """
        spans: list[PIISpan] = []
        for match in self._NIK_PATTERN.finditer(text):
            # High confidence for exact 16-digit match
            confidence = 0.9
            spans.append(PIISpan(
                category="NIK",
                start=match.start(),
                end=match.end(),
                placeholder="[REDACTED_NIK]",
                confidence=confidence,
            ))
        return spans

    def _detect_phone(self, text: str) -> list[PIISpan]:
        """Detect Indonesian phone numbers.

        Supports formats:
        - +62xxx (international format)
        - 08xxx (mobile format)
        - 0xx-xxx (landline with area code)

        Args:
            text: Text to scan for phone number patterns.

        Returns:
            List of PIISpan objects for detected phone numbers.
        """
        spans: list[PIISpan] = []
        for match in self._PHONE_PATTERN.finditer(text):
            matched_text = match.group()
            # Strip separators to count actual digits
            digits = re.sub(r"[^\d]", "", matched_text)

            # Indonesian phone numbers typically have 10-13 digits (including country code)
            # or 9-12 digits for local format
            confidence = 0.85
            if len(digits) < 9 or len(digits) > 15:
                confidence = 0.5

            spans.append(PIISpan(
                category="PHONE",
                start=match.start(),
                end=match.end(),
                placeholder="[REDACTED_PHONE]",
                confidence=confidence,
            ))
        return spans

    def _detect_email(self, text: str) -> list[PIISpan]:
        """Detect email addresses.

        Uses a standard email regex pattern to find email addresses
        in the text.

        Args:
            text: Text to scan for email patterns.

        Returns:
            List of PIISpan objects for detected email addresses.
        """
        spans: list[PIISpan] = []
        for match in self._EMAIL_PATTERN.finditer(text):
            # Email patterns are highly specific, so high confidence
            confidence = 0.95
            spans.append(PIISpan(
                category="EMAIL",
                start=match.start(),
                end=match.end(),
                placeholder="[REDACTED_EMAIL]",
                confidence=confidence,
            ))
        return spans

    def _detect_names(self, text: str) -> list[PIISpan]:
        """Detect person names using heuristic approach.

        Uses capitalized word sequences as a heuristic for name
        detection. Filters out common English words and known
        non-name patterns.

        Args:
            text: Text to scan for name patterns.

        Returns:
            List of PIISpan objects for detected names.
        """
        spans: list[PIISpan] = []
        for match in self._NAME_PATTERN.finditer(text):
            matched_text = match.group()
            words = matched_text.split()

            # Skip if any word is in the exclusion list
            if any(word in self._NAME_EXCLUSIONS for word in words):
                continue

            # Skip if it looks like a sentence start (preceded by . or newline)
            start_pos = match.start()
            if start_pos > 0:
                preceding = text[max(0, start_pos - 3):start_pos].rstrip()
                if preceding and preceding[-1] in ".!?\n":
                    # Lower confidence for sentence-start capitalization
                    confidence = 0.4
                else:
                    confidence = 0.65
            else:
                # At the very start of text, lower confidence
                confidence = 0.4

            # Boost confidence for longer names (3+ words)
            if len(words) >= 3:
                confidence = min(confidence + 0.15, 0.95)

            # Boost confidence if words look like typical Indonesian names
            # (2-8 chars per word, no unusual patterns)
            if all(2 <= len(w) <= 12 for w in words):
                confidence = min(confidence + 0.1, 0.95)

            spans.append(PIISpan(
                category="NAME",
                start=match.start(),
                end=match.end(),
                placeholder="[REDACTED_NAME]",
                confidence=confidence,
            ))
        return spans

    def _is_in_code_block(self, text: str, span: PIISpan) -> bool:
        """Check if a PII span is inside a code block.

        Code blocks are identified by:
        - Triple backtick fenced blocks (```...```)
        - Lines indented with 4 or more spaces

        Args:
            text: The full text containing the span.
            span: The PII span to check.

        Returns:
            True if the span is inside a code block, False otherwise.
        """
        # Check for fenced code blocks (triple backticks)
        # Find all fenced code block regions
        fence_pattern = re.compile(r"```[^\n]*\n(.*?)```", re.DOTALL)
        for fence_match in fence_pattern.finditer(text):
            block_start = fence_match.start()
            block_end = fence_match.end()
            if block_start <= span.start and span.end <= block_end:
                return True

        # Check for indented code blocks (4+ spaces at line start)
        # Find the line containing the span start
        line_start = text.rfind("\n", 0, span.start) + 1
        line_text = text[line_start:span.end]

        # Check if the line starts with 4+ spaces
        first_line = line_text.split("\n")[0] if "\n" in line_text else line_text
        leading_spaces = len(first_line) - len(first_line.lstrip(" "))
        if leading_spaces >= 4:
            return True

        return False

    def _remove_overlaps(self, spans: list[PIISpan]) -> list[PIISpan]:
        """Remove overlapping spans, keeping higher confidence ones.

        When two spans overlap, the one with higher confidence is kept.
        Spans are expected to be sorted by start position (descending).

        Args:
            spans: List of PIISpan objects sorted by start (descending).

        Returns:
            List of non-overlapping PIISpan objects.
        """
        if not spans:
            return []

        # Sort by start ascending for overlap detection
        sorted_spans = sorted(spans, key=lambda s: (s.start, -s.confidence))
        result: list[PIISpan] = []

        for span in sorted_spans:
            # Check if this span overlaps with any already-accepted span
            overlaps = False
            for accepted in result:
                if span.start < accepted.end and span.end > accepted.start:
                    # Overlap detected - keep the one with higher confidence
                    if span.confidence > accepted.confidence:
                        result.remove(accepted)
                        result.append(span)
                    overlaps = True
                    break

            if not overlaps:
                result.append(span)

        return result
