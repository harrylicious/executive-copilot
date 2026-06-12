"""OCR Engine for extracting text from image-based documents.

Supports Tesseract (local) and AWS Textract (cloud) as OCR providers.
Detects whether a file needs OCR processing and returns extracted text
with a confidence score. Flags low-confidence results for manual review.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import ingestion_settings

logger = logging.getLogger(__name__)

# Image file extensions that always require OCR
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}


@dataclass
class OCRResult:
    """Result of OCR text extraction.

    Attributes:
        text: The extracted text content.
        confidence: Confidence score between 0.0 and 1.0.
        needs_manual_review: Whether the result should be flagged for manual review.
        provider: The OCR provider used ("tesseract" or "textract").
        page_count: Number of pages processed.
    """

    text: str
    confidence: float
    needs_manual_review: bool = False
    provider: str = "tesseract"
    page_count: int = 1
    error: str | None = None


class OCREngine:
    """Extracts text from image-based documents using OCR.

    Uses Tesseract as the default local OCR provider, with an optional
    AWS Textract integration for cloud-based processing.

    The engine detects whether a file needs OCR (image files always,
    PDFs only if they contain no extractable text), runs the configured
    OCR provider, and flags results below the confidence threshold
    for manual review.
    """

    def __init__(
        self,
        ocr_provider: str | None = None,
        confidence_threshold: float | None = None,
    ):
        """Initialize the OCR Engine.

        Args:
            ocr_provider: OCR provider to use ("tesseract" or "textract").
                Defaults to ingestion_settings.ocr_provider.
            confidence_threshold: Minimum confidence score before flagging
                for manual review. Defaults to ingestion_settings.ocr_confidence_threshold.
        """
        self.ocr_provider = ocr_provider or ingestion_settings.ocr_provider
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else ingestion_settings.ocr_confidence_threshold
        )

    def extract_text(self, file_path: Path) -> OCRResult:
        """Extract text from a file using OCR.

        Orchestrates the OCR process:
        1. Checks if the file needs OCR processing.
        2. Selects the configured OCR provider.
        3. Runs OCR and returns the result with confidence scoring.
        4. Flags for manual review if confidence is below threshold.

        Args:
            file_path: Path to the file to process.

        Returns:
            OCRResult with extracted text, confidence score, and review flag.
        """
        if not file_path.exists():
            return OCRResult(
                text="",
                confidence=0.0,
                needs_manual_review=True,
                provider=self.ocr_provider,
                error=f"File not found: {file_path}",
            )

        if not self._needs_ocr(file_path):
            return OCRResult(
                text="",
                confidence=1.0,
                needs_manual_review=False,
                provider=self.ocr_provider,
                error="File does not need OCR processing",
            )

        # Select and run OCR provider
        try:
            if self.ocr_provider == "textract":
                text, confidence = self._run_textract(file_path)
            else:
                text, confidence = self._run_tesseract(file_path)
        except Exception as e:
            logger.error(f"OCR processing failed for '{file_path}': {e}")
            return OCRResult(
                text="",
                confidence=0.0,
                needs_manual_review=True,
                provider=self.ocr_provider,
                error=str(e),
            )

        # Flag for manual review if confidence is below threshold
        needs_review = confidence < self.confidence_threshold

        if needs_review:
            logger.warning(
                f"OCR confidence {confidence:.2f} below threshold "
                f"{self.confidence_threshold} for '{file_path}'. "
                f"Flagging for manual review."
            )

        return OCRResult(
            text=text,
            confidence=confidence,
            needs_manual_review=needs_review,
            provider=self.ocr_provider,
        )

    def _needs_ocr(self, file_path: Path) -> bool:
        """Determine if a file needs OCR processing.

        Image files (.png, .jpg, .tiff, etc.) always need OCR.
        PDF files need OCR only if they contain no extractable text
        (i.e., they are image-only/scanned PDFs).

        Args:
            file_path: Path to the file to check.

        Returns:
            True if the file needs OCR processing, False otherwise.
        """
        suffix = file_path.suffix.lower()

        # Image files always need OCR
        if suffix in IMAGE_EXTENSIONS:
            return True

        # PDF files need OCR only if they have no extractable text
        if suffix == ".pdf":
            return self._is_image_only_pdf(file_path)

        # Other file types don't need OCR
        return False

    def _is_image_only_pdf(self, file_path: Path) -> bool:
        """Check if a PDF contains no extractable text (image-only).

        Attempts to extract text from the PDF using PyMuPDF (fitz).
        If no text is found across all pages, the PDF is considered
        image-only and needs OCR.

        Args:
            file_path: Path to the PDF file.

        Returns:
            True if the PDF has no extractable text, False otherwise.
        """
        try:
            import fitz

            doc = fitz.open(str(file_path))
            try:
                for page in doc:
                    text = page.get_text().strip()
                    if text:
                        # Found extractable text, no OCR needed
                        return False
                # No text found in any page — image-only PDF
                return True
            finally:
                doc.close()
        except ImportError:
            logger.warning(
                "PyMuPDF (fitz) not installed. Cannot check PDF text content. "
                "Assuming OCR is needed."
            )
            return True
        except Exception as e:
            logger.error(f"Error checking PDF text content for '{file_path}': {e}")
            # If we can't read the PDF, assume OCR is needed
            return True

    def _run_tesseract(self, file_path: Path) -> tuple[str, float]:
        """Run Tesseract OCR on a file.

        For PDF files, converts each page to an image first using PyMuPDF,
        then runs Tesseract on each page image. For image files, runs
        Tesseract directly.

        Returns the extracted text and an average confidence score.

        Args:
            file_path: Path to the file to process.

        Returns:
            Tuple of (extracted_text, confidence_score).

        Raises:
            ImportError: If pytesseract is not installed.
            RuntimeError: If Tesseract processing fails.
        """
        try:
            import pytesseract
            from PIL import Image
        except ImportError as e:
            raise ImportError(
                "pytesseract and/or Pillow are not installed. "
                "Install them with: pip install pytesseract Pillow"
            ) from e

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return self._run_tesseract_on_pdf(file_path)
        else:
            return self._run_tesseract_on_image(file_path)

    def _run_tesseract_on_image(self, file_path: Path) -> tuple[str, float]:
        """Run Tesseract OCR on a single image file.

        Args:
            file_path: Path to the image file.

        Returns:
            Tuple of (extracted_text, confidence_score).
        """
        import pytesseract
        from PIL import Image

        image = Image.open(file_path)
        # Get detailed OCR data including confidence
        ocr_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        # Extract text and compute average confidence
        text_parts = []
        confidences = []

        for i, conf in enumerate(ocr_data["conf"]):
            word = ocr_data["text"][i].strip()
            if word:  # Skip empty entries
                text_parts.append(word)
                # Tesseract returns confidence as 0-100, convert to 0-1
                conf_value = int(conf)
                if conf_value >= 0:  # -1 means no confidence available
                    confidences.append(conf_value / 100.0)

        text = " ".join(text_parts)
        confidence = sum(confidences) / len(confidences) if confidences else 0.0

        return text, confidence

    def _run_tesseract_on_pdf(self, file_path: Path) -> tuple[str, float]:
        """Run Tesseract OCR on a PDF by converting pages to images.

        Uses PyMuPDF to render each page as an image, then runs
        Tesseract on each page image.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Tuple of (extracted_text, confidence_score).
        """
        try:
            import fitz
        except ImportError as e:
            raise ImportError(
                "PyMuPDF (fitz) is not installed. "
                "Install it with: pip install PyMuPDF"
            ) from e

        import pytesseract
        from PIL import Image
        import io

        doc = fitz.open(str(file_path))
        all_text_parts = []
        all_confidences = []

        try:
            for page in doc:
                # Render page to image at 300 DPI for better OCR quality
                pix = page.get_pixmap(dpi=300)
                img_data = pix.tobytes("png")
                image = Image.open(io.BytesIO(img_data))

                # Run Tesseract on the page image
                ocr_data = pytesseract.image_to_data(
                    image, output_type=pytesseract.Output.DICT
                )

                page_text_parts = []
                for i, conf in enumerate(ocr_data["conf"]):
                    word = ocr_data["text"][i].strip()
                    if word:
                        page_text_parts.append(word)
                        conf_value = int(conf)
                        if conf_value >= 0:
                            all_confidences.append(conf_value / 100.0)

                if page_text_parts:
                    all_text_parts.append(" ".join(page_text_parts))
        finally:
            doc.close()

        text = "\n\n".join(all_text_parts)
        confidence = (
            sum(all_confidences) / len(all_confidences) if all_confidences else 0.0
        )

        return text, confidence

    def _run_textract(self, file_path: Path) -> tuple[str, float]:
        """Run AWS Textract OCR on a file (stub implementation).

        This is a stub for future AWS Textract integration. When implemented,
        it will use the AWS SDK (boto3) to send the document to Textract
        and retrieve the extracted text with confidence scores.

        Args:
            file_path: Path to the file to process.

        Returns:
            Tuple of (extracted_text, confidence_score).

        Raises:
            NotImplementedError: Always, as this is a stub.
        """
        raise NotImplementedError(
            "AWS Textract integration is not yet implemented. "
            "Please use 'tesseract' as the OCR provider, or implement "
            "the Textract integration with boto3. Expected implementation: "
            "1. Upload file to S3 or send bytes directly. "
            "2. Call textract.detect_document_text() or start_document_text_detection(). "
            "3. Parse Block objects for LINE/WORD types. "
            "4. Compute average confidence from Block.Confidence fields. "
            "5. Return concatenated text and normalized confidence score."
        )
