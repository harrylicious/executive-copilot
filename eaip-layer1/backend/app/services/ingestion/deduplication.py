"""Deduplication engine for the ingestion pipeline.

Detects exact and near-duplicate documents using MD5 content hashing
and MinHash similarity estimation. Checks incoming files against
existing content hashes stored in the database.
"""

import hashlib
import logging
import struct
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.file import File
from app.models.ingestion_job import IngestionJob

logger = logging.getLogger(__name__)

# MinHash parameters
_NUM_PERM: int = 128  # Number of hash permutations for MinHash signatures
_HASH_PRIME: int = 2**61 - 1  # Mersenne prime for universal hashing
_MAX_HASH: int = (1 << 32) - 1  # Max 32-bit hash value


@dataclass
class MinHashSignature:
    """A MinHash signature representing a document's shingle set.

    Attributes:
        values: The MinHash signature vector (list of minimum hash values).
        num_perm: Number of permutations used to generate the signature.
    """

    values: list[int]
    num_perm: int = _NUM_PERM


@dataclass
class DeduplicationResult:
    """Result of deduplication check.

    Attributes:
        is_duplicate: Whether the file is a duplicate (exact or near).
        duplicate_type: Type of duplicate detected ("exact", "near", or None).
        duplicate_file_id: ID of the existing file this is a duplicate of.
        similarity_score: Similarity score for near-duplicates (0.0 to 1.0).
        content_hash: The computed MD5 hash of the file content.
        details: Additional context about the deduplication outcome.
    """

    is_duplicate: bool
    duplicate_type: str | None = None
    duplicate_file_id: int | None = None
    similarity_score: float | None = None
    content_hash: str = ""
    details: dict = field(default_factory=dict)


class DeduplicationEngine:
    """Detects exact and near-duplicate documents.

    Uses MD5 content hashing for exact duplicate detection and MinHash
    signatures for near-duplicate detection with configurable similarity
    threshold.
    """

    def __init__(self, similarity_threshold: float = 0.9) -> None:
        """Initialize the deduplication engine.

        Args:
            similarity_threshold: MinHash similarity threshold for
                near-duplicate detection (default 0.9).
        """
        self.similarity_threshold = similarity_threshold
        # Generate fixed random coefficients for MinHash permutations.
        # Using deterministic seeds for reproducibility.
        self._a_coeffs, self._b_coeffs = self._generate_hash_coefficients()

    def _generate_hash_coefficients(self) -> tuple[list[int], list[int]]:
        """Generate random coefficients for universal hash functions.

        Uses a deterministic seed so that MinHash signatures are
        reproducible across runs.

        Returns:
            Tuple of (a_coefficients, b_coefficients) lists.
        """
        import random

        rng = random.Random(42)  # Fixed seed for reproducibility
        a_coeffs = [rng.randint(1, _HASH_PRIME - 1) for _ in range(_NUM_PERM)]
        b_coeffs = [rng.randint(0, _HASH_PRIME - 1) for _ in range(_NUM_PERM)]
        return a_coeffs, b_coeffs

    def compute_content_hash(self, file_path: Path) -> str:
        """Compute MD5 hash of file content for exact duplicate detection.

        Reads the file in chunks to handle large files efficiently.

        Args:
            file_path: Path to the file to hash.

        Returns:
            Hexadecimal MD5 digest string.

        Raises:
            OSError: If the file cannot be read.
        """
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
        return md5.hexdigest()

    def compute_minhash(self, text: str) -> MinHashSignature:
        """Compute MinHash signature for near-duplicate detection.

        Generates character-level shingles (k=5) from the text and
        computes a MinHash signature using universal hashing.

        Args:
            text: The text content to compute the signature for.

        Returns:
            MinHashSignature containing the signature vector.
        """
        # Generate shingles (k-grams of characters)
        k = 5
        shingles = set()
        normalized = text.lower().strip()
        for i in range(len(normalized) - k + 1):
            shingles.add(normalized[i : i + k])

        # If text is too short for shingles, use the whole text as one shingle
        if not shingles:
            shingles.add(normalized if normalized else "")

        # Compute hash values for each shingle
        shingle_hashes = []
        for shingle in shingles:
            # Use a simple hash: CRC32 of the shingle bytes
            h = struct.unpack("<I", hashlib.md5(shingle.encode("utf-8")).digest()[:4])[0]
            shingle_hashes.append(h)

        # Compute MinHash signature using universal hashing
        signature = []
        for i in range(_NUM_PERM):
            min_hash = _MAX_HASH
            a = self._a_coeffs[i]
            b = self._b_coeffs[i]
            for h in shingle_hashes:
                # Universal hash: ((a * h + b) mod prime) mod max_hash
                permuted = ((a * h + b) % _HASH_PRIME) % (_MAX_HASH + 1)
                if permuted < min_hash:
                    min_hash = permuted
            signature.append(min_hash)

        return MinHashSignature(values=signature, num_perm=_NUM_PERM)

    def estimate_similarity(
        self, sig_a: MinHashSignature, sig_b: MinHashSignature
    ) -> float:
        """Estimate Jaccard similarity between two MinHash signatures.

        Args:
            sig_a: First MinHash signature.
            sig_b: Second MinHash signature.

        Returns:
            Estimated Jaccard similarity (0.0 to 1.0).

        Raises:
            ValueError: If signatures have different number of permutations.
        """
        if sig_a.num_perm != sig_b.num_perm:
            raise ValueError(
                f"Cannot compare signatures with different num_perm: "
                f"{sig_a.num_perm} vs {sig_b.num_perm}"
            )

        matches = sum(
            1 for a, b in zip(sig_a.values, sig_b.values) if a == b
        )
        return matches / sig_a.num_perm

    def find_near_duplicates(
        self,
        signature: MinHashSignature,
        db: Session,
        threshold: float | None = None,
    ) -> list[int]:
        """Find near-duplicate files by comparing MinHash signatures.

        Compares the given signature against all existing files in the
        database that have extracted text content. Returns file IDs of
        files whose similarity exceeds the threshold.

        Args:
            signature: MinHash signature of the new document.
            db: SQLAlchemy database session.
            threshold: Similarity threshold (default uses instance threshold).

        Returns:
            List of file IDs that are near-duplicates.
        """
        if threshold is None:
            threshold = self.similarity_threshold

        near_duplicates: list[int] = []

        # Query files that have extracted text (needed for MinHash comparison)
        existing_files = (
            db.query(File)
            .filter(File.extracted_text.isnot(None))
            .filter(File.is_deleted == False)  # noqa: E712
            .all()
        )

        for file in existing_files:
            if not file.extracted_text:
                continue

            existing_sig = self.compute_minhash(file.extracted_text)
            similarity = self.estimate_similarity(signature, existing_sig)

            if similarity >= threshold:
                near_duplicates.append(file.id)
                logger.debug(
                    f"Near-duplicate found: file_id={file.id}, "
                    f"similarity={similarity:.3f}"
                )

        return near_duplicates

    def check_duplicate(self, file_path: Path, db: Session) -> DeduplicationResult:
        """Orchestrate exact and near-duplicate checks against the database.

        Performs checks in order:
        1. Compute MD5 content hash and check for exact duplicates.
        2. If no exact duplicate, extract text and compute MinHash for
           near-duplicate detection.

        Args:
            file_path: Path to the file to check.
            db: SQLAlchemy database session.

        Returns:
            DeduplicationResult with duplicate status and details.
        """
        # Step 1: Compute content hash
        try:
            content_hash = self.compute_content_hash(file_path)
        except OSError as e:
            logger.error(f"Failed to compute content hash for '{file_path}': {e}")
            return DeduplicationResult(
                is_duplicate=False,
                content_hash="",
                details={"error": f"Failed to read file: {e}"},
            )

        # Step 2: Check for exact duplicate by content hash
        existing_file = (
            db.query(File)
            .filter(File.content_hash == content_hash)
            .filter(File.is_deleted == False)  # noqa: E712
            .first()
        )

        # Also check ingestion jobs for files still being processed
        if existing_file is None:
            existing_job = (
                db.query(IngestionJob)
                .filter(IngestionJob.content_hash == content_hash)
                .filter(
                    IngestionJob.status.notin_(
                        ["failed", "validation_failed", "access_denied"]
                    )
                )
                .first()
            )
            if existing_job and existing_job.file_id:
                existing_file = (
                    db.query(File)
                    .filter(File.id == existing_job.file_id)
                    .first()
                )

        if existing_file is not None:
            logger.info(
                f"Exact duplicate detected: '{file_path.name}' matches "
                f"file_id={existing_file.id} (hash={content_hash})"
            )
            return DeduplicationResult(
                is_duplicate=True,
                duplicate_type="exact",
                duplicate_file_id=existing_file.id,
                content_hash=content_hash,
                details={
                    "existing_file_name": existing_file.name,
                    "existing_file_id": existing_file.id,
                },
            )

        # Step 3: Near-duplicate detection via MinHash
        # Read file text content for MinHash comparison
        text_content = self._extract_text_for_minhash(file_path)
        if text_content:
            signature = self.compute_minhash(text_content)
            near_duplicate_ids = self.find_near_duplicates(signature, db)

            if near_duplicate_ids:
                # Return the first near-duplicate found
                duplicate_file_id = near_duplicate_ids[0]
                duplicate_file = (
                    db.query(File).filter(File.id == duplicate_file_id).first()
                )

                # Compute similarity for reporting
                if duplicate_file and duplicate_file.extracted_text:
                    existing_sig = self.compute_minhash(duplicate_file.extracted_text)
                    similarity = self.estimate_similarity(signature, existing_sig)
                else:
                    similarity = self.similarity_threshold

                logger.info(
                    f"Near-duplicate detected: '{file_path.name}' is similar to "
                    f"file_id={duplicate_file_id} (similarity={similarity:.3f})"
                )
                return DeduplicationResult(
                    is_duplicate=True,
                    duplicate_type="near",
                    duplicate_file_id=duplicate_file_id,
                    similarity_score=similarity,
                    content_hash=content_hash,
                    details={
                        "existing_file_name": (
                            duplicate_file.name if duplicate_file else None
                        ),
                        "existing_file_id": duplicate_file_id,
                        "similarity": similarity,
                        "threshold": self.similarity_threshold,
                    },
                )

        # No duplicates found
        return DeduplicationResult(
            is_duplicate=False,
            content_hash=content_hash,
            details={"checked_exact": True, "checked_near": bool(text_content)},
        )

    def _extract_text_for_minhash(self, file_path: Path) -> str | None:
        """Extract text content from a file for MinHash computation.

        Attempts to read the file as UTF-8 text. For binary formats,
        returns None (near-duplicate detection relies on text content).

        Args:
            file_path: Path to the file.

        Returns:
            Text content if readable, None otherwise.
        """
        # Only attempt text extraction for text-based formats
        text_extensions = {".txt", ".md", ".json", ".csv"}
        suffix = file_path.suffix.lower()

        if suffix in text_extensions:
            try:
                return file_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(
                    f"Could not read text from '{file_path}' for MinHash: {e}"
                )
                return None

        # For other formats, try to read as text (best effort)
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            # Only use if we got meaningful text content
            if len(content.strip()) > 50:
                return content
        except OSError:
            pass

        return None
