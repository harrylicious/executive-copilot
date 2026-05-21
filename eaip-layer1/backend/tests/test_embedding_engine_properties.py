"""Property-based tests for EmbeddingEngine orchestration.

Property 2: Re-chunking a modified file replaces all previous chunks

For any file that has been previously chunked, when the file's content_hash changes
and re-chunking is triggered, the system SHALL contain zero chunks with the old content
and only chunks derived from the new content for that file_id.

**Validates: Requirements 1.5**
"""

import hashlib
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path

import hypothesis.strategies as st
from hypothesis import given, settings, assume
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.chunk import Chunk
from app.models.file import File
from app.services.document_chunker import DocumentChunker
from app.services.embedding_engine import EmbeddingEngine
from app.config import GraphRAGSettings


# Strategy for generating non-empty text content that produces meaningful chunks
text_content = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=50,
    max_size=2000,
).filter(lambda t: len(t.strip()) >= 20)

# Strategy for generating pairs of distinct text contents (old and new)
distinct_text_pairs = st.tuples(text_content, text_content).filter(
    lambda pair: pair[0].strip() != pair[1].strip()
)

# Strategy for departments
departments = st.sampled_from([
    "engineering", "marketing", "finance", "hr", "legal", "operations"
])


def _compute_hash(content: str) -> str:
    """Compute a content hash for a given text string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class TestProperty2ReChunkingReplacement:
    """Property 2: Re-chunking a modified file replaces all previous chunks.

    **Validates: Requirements 1.5**
    """

    @given(
        text_pair=distinct_text_pairs,
        department=departments,
    )
    @settings(max_examples=20, deadline=None)
    def test_rechunking_replaces_all_previous_chunks(
        self, text_pair: tuple[str, str], department: str
    ):
        """For any file that has been previously chunked, when the file's content_hash
        changes and re-chunking is triggered, the system contains zero chunks with the
        old content and only chunks derived from the new content for that file_id.

        **Validates: Requirements 1.5**
        """
        old_content, new_content = text_pair

        # Ensure the two contents produce different hashes
        old_hash = _compute_hash(old_content)
        new_hash = _compute_hash(new_content)
        assume(old_hash != new_hash)

        # Set up an in-memory SQLite database
        engine = create_engine("sqlite:///:memory:", echo=False)
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Create a temporary directory for the file and vector store
        tmp_dir = tempfile.mkdtemp()
        try:
            # Create the file on disk with old content
            file_path = Path(tmp_dir) / "test_file.txt"
            file_path.write_text(old_content, encoding="utf-8")

            # Insert a File record into the database
            now = datetime.now(timezone.utc)
            db_file = File(
                name="test_file.txt",
                path=str(file_path),
                department=department,
                size=len(old_content),
                content_hash=old_hash,
                created_at=now,
                modified_at=now,
                embedding_status=None,  # Never embedded
            )
            session.add(db_file)
            session.commit()
            session.refresh(db_file)
            file_id = db_file.id

            # Configure the embedding engine with a temp vector store path
            vector_store_path = str(Path(tmp_dir) / "chroma_db")
            config = GraphRAGSettings(
                chunk_size=128,
                chunk_overlap=20,
                vector_store_path=vector_store_path,
            )

            # First embedding run: process the file with old content
            embedding_engine = EmbeddingEngine(db=session, config=config)
            result1 = embedding_engine.run_single(file_id)

            # Verify chunks were created from old content
            old_chunks = session.query(Chunk).filter(Chunk.file_id == file_id).all()
            assume(len(old_chunks) > 0)  # Need at least one chunk to test replacement

            # Record old chunk texts for later comparison
            old_chunk_texts = [c.text for c in old_chunks]
            old_chunk_count = len(old_chunks)

            # Now simulate a file modification: write new content and update hash
            file_path.write_text(new_content, encoding="utf-8")
            db_file.content_hash = new_hash
            db_file.embedding_status = "pending"  # Mark as needing re-embedding
            db_file.size = len(new_content)
            session.commit()

            # Second embedding run: re-process the file with new content
            embedding_engine2 = EmbeddingEngine(db=session, config=config)
            result2 = embedding_engine2.run_single(file_id)

            # Verify: the system contains zero chunks with old content
            current_chunks = (
                session.query(Chunk).filter(Chunk.file_id == file_id).all()
            )

            current_chunk_texts = [c.text for c in current_chunks]

            # No old chunk text should remain in the database for this file
            for old_text in old_chunk_texts:
                assert old_text not in current_chunk_texts, (
                    f"Old chunk text still present after re-chunking: "
                    f"'{old_text[:50]}...'"
                )

            # All current chunks should be derived from the new content
            # Verify by re-chunking the new content independently and comparing
            chunker = DocumentChunker(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
            )
            expected_chunks = chunker.chunk(new_content)

            if expected_chunks:
                expected_texts = [c.text for c in expected_chunks]
                assert len(current_chunks) == len(expected_texts), (
                    f"Expected {len(expected_texts)} chunks from new content, "
                    f"got {len(current_chunks)}"
                )
                for chunk in current_chunks:
                    assert chunk.text in expected_texts, (
                        f"Chunk text '{chunk.text[:50]}...' not derived from new content"
                    )

            # Verify chunk indices are sequential starting at 0
            if current_chunks:
                indices = sorted(c.chunk_index for c in current_chunks)
                expected_indices = list(range(len(current_chunks)))
                assert indices == expected_indices, (
                    f"Chunk indices {indices} are not sequential from 0"
                )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            session.close()
            engine.dispose()


# ============================================================================
# Property 5: Re-embedding replaces all previous embeddings for a file
#
# For any previously embedded file, when re-embedding is triggered, the
# Vector_Store SHALL contain only the newly generated embeddings for that
# file_id and zero embeddings from the prior embedding run.
#
# **Validates: Requirements 2.6**
# ============================================================================

from app.services.embedding_model import EmbeddingModel
from app.services.vector_store import ChromaVectorStore

# Load the embedding model once at module level to avoid repeated model loading
_EMBEDDING_MODEL = EmbeddingModel(model_name="all-MiniLM-L6-v2")
_EXPECTED_DIMENSION = 384

# Strategy for generating non-empty text that produces meaningful chunks
_non_empty_text = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "P", "Z"),
        blacklist_characters="\x00",
    ),
    min_size=10,
    max_size=2000,
).filter(lambda t: len(t.strip()) >= 5)

# Strategy for generating valid file IDs
_file_ids = st.integers(min_value=1, max_value=10000)


class TestProperty5ReEmbeddingReplacement:
    """Property 5: Re-embedding replaces all previous embeddings for a file.

    For any previously embedded file, when re-embedding is triggered, the
    Vector_Store SHALL contain only the newly generated embeddings for that
    file_id and zero embeddings from the prior embedding run.

    **Validates: Requirements 2.6**
    """

    @given(
        original_text=_non_empty_text,
        new_text=_non_empty_text,
        file_id=_file_ids,
        department=departments,
    )
    @settings(max_examples=30, deadline=60000)
    def test_re_embedding_replaces_all_previous_embeddings(
        self, original_text: str, new_text: str, file_id: int, department: str
    ):
        """When re-embedding is triggered, the Vector_Store contains only the
        newly generated embeddings for that file_id and zero embeddings from
        the prior embedding run.

        **Validates: Requirements 2.6**
        """
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)

        # Generate chunks from original text
        original_chunks = chunker.chunk(original_text)
        assume(len(original_chunks) > 0)

        # Generate chunks from new text
        new_chunks = chunker.chunk(new_text)
        assume(len(new_chunks) > 0)

        # Generate embeddings for both sets
        original_embeddings = _EMBEDDING_MODEL.embed_texts(
            [c.text for c in original_chunks]
        )
        new_embeddings = _EMBEDDING_MODEL.embed_texts(
            [c.text for c in new_chunks]
        )

        assume(len(original_embeddings) == len(original_chunks))
        assume(len(new_embeddings) == len(new_chunks))

        tmp_dir = tempfile.mkdtemp()
        try:
            config = GraphRAGSettings(vector_store_path=tmp_dir)
            vector_store = ChromaVectorStore(config)
            metadata = {"department": department}

            # Step 1: Store original embeddings (first embedding run)
            vector_store.upsert_chunks(
                file_id, original_chunks, original_embeddings, metadata
            )

            # Verify original embeddings are stored
            original_results = vector_store.collection.get(
                where={"file_id": file_id},
                include=["metadatas", "embeddings", "documents"],
            )
            assert len(original_results["ids"]) == len(original_chunks)

            # Step 2: Re-embed with new content (triggers replacement)
            vector_store.upsert_chunks(
                file_id, new_chunks, new_embeddings, metadata
            )

            # Step 3: Verify only new embeddings exist
            after_results = vector_store.collection.get(
                where={"file_id": file_id},
                include=["metadatas", "embeddings", "documents"],
            )

            # Should have exactly the number of new chunks
            assert len(after_results["ids"]) == len(new_chunks), (
                f"Expected {len(new_chunks)} embeddings after re-embedding, "
                f"got {len(after_results['ids'])}. "
                f"Original had {len(original_chunks)} chunks."
            )

            # Verify all stored chunk indices match the new chunks
            stored_indices = sorted(
                m["chunk_index"] for m in after_results["metadatas"]
            )
            expected_indices = sorted(c.chunk_index for c in new_chunks)
            assert stored_indices == expected_indices, (
                f"Stored chunk indices {stored_indices} don't match "
                f"new chunk indices {expected_indices}"
            )

            # Verify stored documents match the new chunk texts
            stored_docs = set(after_results["documents"])
            new_texts = set(c.text for c in new_chunks)
            assert stored_docs == new_texts, (
                "Stored documents don't match new chunk texts. "
                "Old embeddings may still be present."
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        original_text=_non_empty_text,
        new_text=_non_empty_text,
        file_id=_file_ids,
        other_file_id=_file_ids,
        department=departments,
    )
    @settings(max_examples=30, deadline=60000)
    def test_re_embedding_does_not_affect_other_files(
        self,
        original_text: str,
        new_text: str,
        file_id: int,
        other_file_id: int,
        department: str,
    ):
        """Re-embedding one file does not remove or alter embeddings for other files.

        **Validates: Requirements 2.6**
        """
        # Ensure different file IDs
        assume(file_id != other_file_id)

        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)

        # Generate chunks for both files
        file_chunks = chunker.chunk(original_text)
        other_chunks = chunker.chunk(new_text)
        assume(len(file_chunks) > 0)
        assume(len(other_chunks) > 0)

        file_embeddings = _EMBEDDING_MODEL.embed_texts(
            [c.text for c in file_chunks]
        )
        other_embeddings = _EMBEDDING_MODEL.embed_texts(
            [c.text for c in other_chunks]
        )

        assume(len(file_embeddings) == len(file_chunks))
        assume(len(other_embeddings) == len(other_chunks))

        tmp_dir = tempfile.mkdtemp()
        try:
            config = GraphRAGSettings(vector_store_path=tmp_dir)
            vector_store = ChromaVectorStore(config)
            metadata = {"department": department}

            # Store embeddings for both files
            vector_store.upsert_chunks(
                file_id, file_chunks, file_embeddings, metadata
            )
            vector_store.upsert_chunks(
                other_file_id, other_chunks, other_embeddings, metadata
            )

            # Re-embed the first file with new content
            re_embed_chunks = chunker.chunk(
                "This is completely new content for re-embedding test."
            )
            assume(len(re_embed_chunks) > 0)
            re_embed_embeddings = _EMBEDDING_MODEL.embed_texts(
                [c.text for c in re_embed_chunks]
            )
            assume(len(re_embed_embeddings) == len(re_embed_chunks))

            vector_store.upsert_chunks(
                file_id, re_embed_chunks, re_embed_embeddings, metadata
            )

            # Verify other file's embeddings are untouched
            other_results = vector_store.collection.get(
                where={"file_id": other_file_id},
                include=["metadatas", "documents"],
            )

            assert len(other_results["ids"]) == len(other_chunks), (
                f"Other file's embeddings changed: expected {len(other_chunks)}, "
                f"got {len(other_results['ids'])}"
            )

            # Verify other file's documents are unchanged
            stored_other_docs = set(other_results["documents"])
            expected_other_docs = set(c.text for c in other_chunks)
            assert stored_other_docs == expected_other_docs, (
                "Other file's stored documents were altered during re-embedding."
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    @given(
        text=_non_empty_text,
        file_id=_file_ids,
        department=departments,
    )
    @settings(max_examples=30, deadline=60000)
    def test_re_embedding_with_same_content_produces_same_count(
        self, text: str, file_id: int, department: str
    ):
        """Re-embedding the same content produces the same number of embeddings
        (idempotent replacement).

        **Validates: Requirements 2.6**
        """
        chunker = DocumentChunker(chunk_size=128, chunk_overlap=20)
        chunks = chunker.chunk(text)
        assume(len(chunks) > 0)

        embeddings = _EMBEDDING_MODEL.embed_texts([c.text for c in chunks])
        assume(len(embeddings) == len(chunks))

        tmp_dir = tempfile.mkdtemp()
        try:
            config = GraphRAGSettings(vector_store_path=tmp_dir)
            vector_store = ChromaVectorStore(config)
            metadata = {"department": department}

            # First embedding
            vector_store.upsert_chunks(file_id, chunks, embeddings, metadata)

            # Re-embed with same content
            vector_store.upsert_chunks(file_id, chunks, embeddings, metadata)

            # Verify count is still the same (no duplicates)
            results = vector_store.collection.get(
                where={"file_id": file_id},
                include=["metadatas"],
            )

            assert len(results["ids"]) == len(chunks), (
                f"Expected {len(chunks)} embeddings after re-embedding same content, "
                f"got {len(results['ids'])}. Duplicates may exist."
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


# ============================================================================
# Property 6: Incremental job processes exactly the files needing embedding
#
# For any set of indexed files with various states (never embedded, hash
# changed/pending, hash unchanged/embedded), an incremental embedding job SHALL
# process exactly those files where embedding_status is None or "pending", and
# SHALL skip all files whose embedding_status is "embedded".
#
# **Validates: Requirements 3.1, 3.8**
# ============================================================================

from unittest.mock import patch
from app.models.embedding_log import EmbeddingLog

# Strategy for embedding status values
embedding_status_st = st.sampled_from([None, "pending", "embedded"])

# Strategy for generating a list of file states (embedding_status values)
file_states_st = st.lists(
    embedding_status_st,
    min_size=1,
    max_size=15,
)


def _create_test_db():
    """Create a fresh in-memory SQLite database with all tables."""
    db_engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(db_engine)
    Session = sessionmaker(bind=db_engine)
    return db_engine, Session


def _create_files_with_states(session, states: list) -> list:
    """Create test file records with specified embedding_status values."""
    now = datetime.now(timezone.utc)
    files = []
    for i, status in enumerate(states):
        f = File(
            name=f"test_file_{i}.txt",
            path=f"dept/test_file_{i}.txt",
            department="TestDept",
            size=1000 + i,
            content_hash=f"hash_{i}",
            created_at=now,
            modified_at=now,
            embedding_status=status,
        )
        session.add(f)
        files.append(f)
    session.flush()
    session.commit()
    return files


class TestProperty6IncrementalJobFileSelection:
    """Property 6: Incremental job processes exactly the files needing embedding.

    **Validates: Requirements 3.1, 3.8**
    """

    @given(file_states=file_states_st)
    @settings(max_examples=100, deadline=None)
    def test_incremental_processes_only_none_and_pending_files(
        self, file_states: list,
    ):
        """An incremental embedding job SHALL process exactly those files where
        embedding_status is None or "pending", and SHALL skip all files whose
        embedding_status is "embedded".

        **Validates: Requirements 3.1, 3.8**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Create files with the generated states
            files = _create_files_with_states(session, file_states)

            # Determine which files SHOULD be processed
            expected_file_ids = {
                f.id for f in files
                if f.embedding_status is None or f.embedding_status == "pending"
            }
            # Determine which files SHOULD be skipped
            skipped_file_ids = {
                f.id for f in files
                if f.embedding_status == "embedded"
            }

            # Track which files are actually processed
            processed_file_ids = set()

            # Mock _process_file to record which files are processed
            def mock_process_file(file):
                processed_file_ids.add(file.id)
                return 0, []  # 0 chunks, no errors

            # Create the EmbeddingEngine with mocked dependencies
            config = GraphRAGSettings()

            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):

                emb_engine = EmbeddingEngine(db=session, config=config)
                # Replace _process_file with our tracking mock
                emb_engine._process_file = mock_process_file

                # Run incremental job
                result = emb_engine.run_incremental()

            # PROPERTY: processed files == files with status None or "pending"
            assert processed_file_ids == expected_file_ids, (
                f"Incremental job processed files {processed_file_ids} "
                f"but expected to process {expected_file_ids}. "
                f"File states: {[(f.id, f.embedding_status) for f in files]}"
            )

            # PROPERTY: no "embedded" file was processed
            incorrectly_processed = processed_file_ids & skipped_file_ids
            assert len(incorrectly_processed) == 0, (
                f"Incremental job incorrectly processed embedded files: "
                f"{incorrectly_processed}. "
                f"File states: {[(f.id, f.embedding_status) for f in files]}"
            )

            # PROPERTY: files_processed count matches
            assert result.files_processed == len(expected_file_ids), (
                f"Result reports files_processed={result.files_processed} "
                f"but {len(expected_file_ids)} files needed processing"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(file_states=file_states_st)
    @settings(max_examples=100, deadline=None)
    def test_incremental_skips_all_embedded_files(
        self, file_states: list,
    ):
        """An incremental embedding job SHALL skip all files whose
        embedding_status is "embedded" (content_hash unchanged).

        **Validates: Requirements 3.8**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Create files with the generated states
            files = _create_files_with_states(session, file_states)

            # Track which files are actually processed
            processed_file_ids = set()

            def mock_process_file(file):
                processed_file_ids.add(file.id)
                return 0, []

            config = GraphRAGSettings()

            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):

                emb_engine = EmbeddingEngine(db=session, config=config)
                emb_engine._process_file = mock_process_file

                emb_engine.run_incremental()

            # PROPERTY: no file with embedding_status == "embedded" was processed
            embedded_file_ids = {
                f.id for f in files if f.embedding_status == "embedded"
            }
            incorrectly_processed = processed_file_ids & embedded_file_ids
            assert len(incorrectly_processed) == 0, (
                f"Incremental job processed {len(incorrectly_processed)} "
                f"embedded files that should have been skipped: "
                f"{incorrectly_processed}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        num_none=st.integers(min_value=0, max_value=5),
        num_pending=st.integers(min_value=0, max_value=5),
        num_embedded=st.integers(min_value=0, max_value=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_incremental_processes_exact_count_by_status_category(
        self,
        num_none: int,
        num_pending: int,
        num_embedded: int,
    ):
        """The number of files processed equals exactly the count of files
        with embedding_status None plus the count with embedding_status "pending".

        **Validates: Requirements 3.1, 3.8**
        """
        total = num_none + num_pending + num_embedded
        assume(total > 0)

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Build file states list with exact counts per category
            states = (
                [None] * num_none
                + ["pending"] * num_pending
                + ["embedded"] * num_embedded
            )
            files = _create_files_with_states(session, states)

            processed_file_ids = set()

            def mock_process_file(file):
                processed_file_ids.add(file.id)
                return 0, []

            config = GraphRAGSettings()

            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):

                emb_engine = EmbeddingEngine(db=session, config=config)
                emb_engine._process_file = mock_process_file

                result = emb_engine.run_incremental()

            # PROPERTY: exactly num_none + num_pending files are processed
            expected_count = num_none + num_pending
            assert len(processed_file_ids) == expected_count, (
                f"Expected {expected_count} files processed "
                f"(None={num_none}, pending={num_pending}), "
                f"but got {len(processed_file_ids)}"
            )
            assert result.files_processed == expected_count, (
                f"Result.files_processed={result.files_processed} "
                f"doesn't match expected {expected_count}"
            )

        finally:
            session.close()
            db_engine.dispose()


# ============================================================================
# Property 7: Job summary accurately reflects processing outcomes
#
# For any embedding job execution, the returned summary's files_processed count
# SHALL equal the number of files actually processed, chunks_generated SHALL
# equal the total chunks created, and errors list SHALL contain one entry per
# file that encountered a failure.
#
# **Validates: Requirements 3.5**
# ============================================================================

from app.services.document_chunker import ChunkResult


# Strategy for generating per-file chunk counts (0 means extraction failure)
_chunks_per_file_st = st.lists(
    st.integers(min_value=0, max_value=5),
    min_size=1,
    max_size=10,
)


class TestProperty7JobSummaryAccuracy:
    """Property 7: Job summary accurately reflects processing outcomes.

    **Validates: Requirements 3.5**
    """

    @given(chunks_per_file=_chunks_per_file_st)
    @settings(max_examples=100, deadline=None)
    def test_job_summary_counts_match_actual_processing(
        self, chunks_per_file: list[int],
    ):
        """The returned summary's files_processed, chunks_generated, and errors
        list accurately reflect the actual processing outcomes.

        **Validates: Requirements 3.5**
        """
        n_files = len(chunks_per_file)

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            files = _create_files_with_states(session, [None] * n_files)

            # Track call index to determine behavior per file
            call_idx = [0]

            def mock_extract(file_path, file_format):
                idx = call_idx[0]
                call_idx[0] += 1
                if chunks_per_file[idx] == 0:
                    return None  # Simulate extraction failure
                return f"Content for file {idx}"

            def mock_chunk(text):
                # Find which file this is for based on text
                idx = int(text.split()[-1]) if text.startswith("Content for file") else 0
                count = chunks_per_file[idx]
                return [
                    ChunkResult(
                        text=f"Chunk {j} of file {idx}",
                        chunk_index=j,
                        start_offset=j * 10,
                        end_offset=(j + 1) * 10,
                    )
                    for j in range(count)
                ]

            config = GraphRAGSettings()

            with patch("app.services.embedding_engine.TextExtractor") as MockExtractor, \
                 patch("app.services.embedding_engine.DocumentChunker") as MockChunker, \
                 patch("app.services.embedding_engine.EmbeddingModel") as MockModel, \
                 patch("app.services.embedding_engine.ChromaVectorStore") as MockVectorStore, \
                 patch("app.services.embedding_engine.GraphRAGEngine") as MockGraphRAG:

                MockExtractor.return_value.extract.side_effect = mock_extract
                MockChunker.return_value.chunk.side_effect = mock_chunk
                MockModel.return_value.embed_texts.return_value = [[0.1] * 384]
                MockVectorStore.return_value.upsert_chunks.return_value = None
                MockGraphRAG.return_value.extract_entities_and_relationships.return_value = None

                engine = EmbeddingEngine(db=session, config=config)
                result = engine.run_incremental()

            # PROPERTY: files_processed == total files attempted
            assert result.files_processed == n_files, (
                f"Expected files_processed={n_files}, got {result.files_processed}"
            )

            # PROPERTY: chunks_generated == sum of chunks from successful files
            expected_chunks = sum(c for c in chunks_per_file if c > 0)
            assert result.chunks_generated == expected_chunks, (
                f"Expected chunks_generated={expected_chunks}, "
                f"got {result.chunks_generated}"
            )

            # PROPERTY: errors list has one entry per failed file
            expected_errors = sum(1 for c in chunks_per_file if c == 0)
            assert len(result.errors) == expected_errors, (
                f"Expected {expected_errors} errors, got {len(result.errors)}"
            )

        finally:
            session.close()
            db_engine.dispose()


# ============================================================================
# Property 8: Partial failure does not halt remaining file processing
#
# For any embedding job where K out of N files fail (0 < K < N), the job SHALL
# still process all N-K remaining files successfully, and the job status SHALL
# be "partial_success".
#
# **Validates: Requirements 3.6**
# ============================================================================

# Strategy for total number of files (need at least 2 for partial failure)
_total_files_strategy = st.integers(min_value=2, max_value=15)

# Strategy for the fraction of files that fail (between 0 exclusive and 1 exclusive)
_failure_fraction_strategy = st.floats(min_value=0.1, max_value=0.9)


class TestProperty8PartialFailureResilience:
    """Property 8: Partial failure does not halt remaining file processing.

    For any embedding job where K out of N files fail (0 < K < N), the job
    SHALL still process all N-K remaining files successfully, and the job
    status SHALL be "partial_success".

    **Validates: Requirements 3.6**
    """

    @given(
        total_files=_total_files_strategy,
        failure_fraction=_failure_fraction_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_partial_failure_processes_remaining_files(
        self, total_files: int, failure_fraction: float
    ):
        """For any job where K out of N files fail (0 < K < N), the remaining
        N-K files are still processed successfully.

        **Validates: Requirements 3.6**
        """
        # Compute K (number of failing files) ensuring 0 < K < N
        k_failures = max(1, min(total_files - 1, int(failure_fraction * total_files)))
        assume(0 < k_failures < total_files)

        n_successes = total_files - k_failures

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            files = _create_files_with_states(session, [None] * total_files)
            config = GraphRAGSettings()

            # Build a set of file indices that should fail
            failing_indices = set(range(k_failures))

            # Track which files the extractor is called with
            call_count = [0]

            def mock_extract_side_effect(file_path, file_format):
                """Return None for failing files, valid text for others."""
                idx = call_count[0]
                call_count[0] += 1
                if idx in failing_indices:
                    return None  # Simulates extraction failure
                return f"Valid content for file {idx}."

            with patch("app.services.embedding_engine.TextExtractor") as MockExtractor, \
                 patch("app.services.embedding_engine.DocumentChunker") as MockChunker, \
                 patch("app.services.embedding_engine.EmbeddingModel") as MockModel, \
                 patch("app.services.embedding_engine.ChromaVectorStore") as MockVectorStore, \
                 patch("app.services.embedding_engine.GraphRAGEngine") as MockGraphRAG:

                MockExtractor.return_value.extract.side_effect = mock_extract_side_effect
                MockChunker.return_value.chunk.return_value = [
                    ChunkResult(
                        text="Test chunk content",
                        chunk_index=0,
                        start_offset=0,
                        end_offset=18,
                    )
                ]
                MockModel.return_value.embed_texts.return_value = [[0.1] * 384]
                MockVectorStore.return_value.upsert_chunks.return_value = None
                MockGraphRAG.return_value.extract_entities_and_relationships.return_value = None

                engine = EmbeddingEngine(db=session, config=config)
                result = engine.run_incremental()

            # Property assertions:
            # 1. All N files were attempted (files_processed == N)
            assert result.files_processed == total_files, (
                f"Expected files_processed={total_files}, got {result.files_processed}. "
                f"The engine should attempt all files regardless of failures."
            )

            # 2. The successful files produced chunks (N-K files × 1 chunk each)
            assert result.chunks_generated == n_successes, (
                f"Expected chunks_generated={n_successes} (from {n_successes} "
                f"successful files), got {result.chunks_generated}. "
                f"Failures in K={k_failures} files should not prevent "
                f"processing of remaining files."
            )

            # 3. The job status is "partial_success"
            assert result.status == "partial_success", (
                f"Expected status='partial_success' when {k_failures}/{total_files} "
                f"files fail, got '{result.status}'."
            )

            # 4. Errors list contains exactly K entries (one per failed file)
            assert len(result.errors) == k_failures, (
                f"Expected {k_failures} errors (one per failed file), "
                f"got {len(result.errors)}."
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        total_files=_total_files_strategy,
        failure_fraction=_failure_fraction_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_partial_failure_does_not_halt_processing_order(
        self, total_files: int, failure_fraction: float
    ):
        """Failures at any position in the file list do not prevent subsequent
        files from being processed.

        **Validates: Requirements 3.6**
        """
        k_failures = max(1, min(total_files - 1, int(failure_fraction * total_files)))
        assume(0 < k_failures < total_files)

        n_successes = total_files - k_failures

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            files = _create_files_with_states(session, [None] * total_files)
            config = GraphRAGSettings()

            # Spread failures evenly across the file list (not just at the start)
            # This tests that failures in the middle don't halt later files
            step = total_files / k_failures
            failing_indices = set(int(i * step) for i in range(k_failures))
            # Ensure we have exactly k_failures indices within range
            while len(failing_indices) < k_failures:
                for idx in range(total_files):
                    if idx not in failing_indices:
                        failing_indices.add(idx)
                        break
            # Trim if we accidentally got too many
            failing_indices = set(list(failing_indices)[:k_failures])

            call_count = [0]

            def mock_extract_side_effect(file_path, file_format):
                idx = call_count[0]
                call_count[0] += 1
                if idx in failing_indices:
                    return None
                return f"Content for file {idx}."

            with patch("app.services.embedding_engine.TextExtractor") as MockExtractor, \
                 patch("app.services.embedding_engine.DocumentChunker") as MockChunker, \
                 patch("app.services.embedding_engine.EmbeddingModel") as MockModel, \
                 patch("app.services.embedding_engine.ChromaVectorStore") as MockVectorStore, \
                 patch("app.services.embedding_engine.GraphRAGEngine") as MockGraphRAG:

                MockExtractor.return_value.extract.side_effect = mock_extract_side_effect
                MockChunker.return_value.chunk.return_value = [
                    ChunkResult(
                        text="Chunk text",
                        chunk_index=0,
                        start_offset=0,
                        end_offset=10,
                    )
                ]
                MockModel.return_value.embed_texts.return_value = [[0.2] * 384]
                MockVectorStore.return_value.upsert_chunks.return_value = None
                MockGraphRAG.return_value.extract_entities_and_relationships.return_value = None

                engine = EmbeddingEngine(db=session, config=config)
                result = engine.run_incremental()

            # The engine must process all files regardless of where failures occur
            assert result.files_processed == total_files, (
                f"Expected all {total_files} files to be attempted, "
                f"got {result.files_processed}."
            )

            # Successful files still produce chunks
            assert result.chunks_generated == n_successes, (
                f"Expected {n_successes} chunks from successful files, "
                f"got {result.chunks_generated}."
            )

            # Status must be partial_success
            assert result.status == "partial_success", (
                f"Expected 'partial_success' with failures at indices "
                f"{sorted(failing_indices)}, got '{result.status}'."
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        total_files=_total_files_strategy,
        failure_fraction=_failure_fraction_strategy,
    )
    @settings(max_examples=50, deadline=None)
    def test_partial_failure_with_exception_does_not_halt(
        self, total_files: int, failure_fraction: float
    ):
        """Files that raise unexpected exceptions do not halt processing of
        remaining files.

        **Validates: Requirements 3.6**
        """
        k_failures = max(1, min(total_files - 1, int(failure_fraction * total_files)))
        assume(0 < k_failures < total_files)

        n_successes = total_files - k_failures

        db_engine, Session = _create_test_db()
        session = Session()

        try:
            files = _create_files_with_states(session, [None] * total_files)
            config = GraphRAGSettings()

            # Failures are the first K files (via exception in extraction)
            failing_indices = set(range(k_failures))
            call_count = [0]

            def mock_extract_side_effect(file_path, file_format):
                idx = call_count[0]
                call_count[0] += 1
                if idx in failing_indices:
                    raise RuntimeError(f"Simulated failure for file {idx}")
                return f"Good content for file {idx}."

            with patch("app.services.embedding_engine.TextExtractor") as MockExtractor, \
                 patch("app.services.embedding_engine.DocumentChunker") as MockChunker, \
                 patch("app.services.embedding_engine.EmbeddingModel") as MockModel, \
                 patch("app.services.embedding_engine.ChromaVectorStore") as MockVectorStore, \
                 patch("app.services.embedding_engine.GraphRAGEngine") as MockGraphRAG:

                MockExtractor.return_value.extract.side_effect = mock_extract_side_effect
                MockChunker.return_value.chunk.return_value = [
                    ChunkResult(
                        text="Chunk data",
                        chunk_index=0,
                        start_offset=0,
                        end_offset=10,
                    )
                ]
                MockModel.return_value.embed_texts.return_value = [[0.3] * 384]
                MockVectorStore.return_value.upsert_chunks.return_value = None
                MockGraphRAG.return_value.extract_entities_and_relationships.return_value = None

                engine = EmbeddingEngine(db=session, config=config)
                result = engine.run_incremental()

            # All files attempted
            assert result.files_processed == total_files, (
                f"Expected {total_files} files attempted, got {result.files_processed}. "
                f"Exceptions in {k_failures} files must not halt the batch."
            )

            # Successful files still produce chunks
            assert result.chunks_generated == n_successes, (
                f"Expected {n_successes} chunks, got {result.chunks_generated}."
            )

            # Status is partial_success
            assert result.status == "partial_success", (
                f"Expected 'partial_success', got '{result.status}'."
            )

            # Each failed file produces an error entry
            assert len(result.errors) == k_failures, (
                f"Expected {k_failures} error entries, got {len(result.errors)}."
            )

        finally:
            session.close()
            db_engine.dispose()


# ============================================================================
# Property 9: Every completed job produces exactly one log entry
#
# For any embedding job that completes (regardless of status), exactly one
# record SHALL be inserted into the embedding_log table with the correct
# timestamp, file count, chunk count, and status.
#
# **Validates: Requirements 3.7**
# ============================================================================

from app.services.embedding_engine import EmbeddingJobResult as _EmbeddingJobResult

# Strategy for number of files processed
_p9_files_processed_st = st.integers(min_value=0, max_value=10)

# Strategy for chunks generated
_p9_chunks_generated_st = st.integers(min_value=0, max_value=50)

# Strategy for job status outcomes
_p9_job_status_st = st.sampled_from(["success", "partial_success", "error"])

# Strategy for number of errors
_p9_num_errors_st = st.integers(min_value=0, max_value=10)


class TestProperty9JobLogging:
    """Property 9: Every completed job produces exactly one log entry.

    For any embedding job that completes (regardless of status), exactly one
    record SHALL be inserted into the embedding_log table with the correct
    timestamp, file count, chunk count, and status.

    **Validates: Requirements 3.7**
    """

    @given(
        files_processed=_p9_files_processed_st,
        chunks_generated=_p9_chunks_generated_st,
        num_errors=_p9_num_errors_st,
        status=_p9_job_status_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_log_job_inserts_exactly_one_record(
        self,
        files_processed: int,
        chunks_generated: int,
        num_errors: int,
        status: str,
    ):
        """For any embedding job that completes, exactly one record is inserted
        into the embedding_log table.

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            # Verify embedding_log is empty before the job
            initial_count = session.query(EmbeddingLog).count()
            assert initial_count == 0

            # Create an EmbeddingJobResult with the generated parameters
            errors = [
                {"file_id": i, "file_path": f"path_{i}.txt", "error": f"error_{i}"}
                for i in range(num_errors)
            ]
            result = _EmbeddingJobResult(
                files_processed=files_processed,
                chunks_generated=chunks_generated,
                errors=errors,
                status=status,
            )

            # Create an EmbeddingEngine and call _log_job directly
            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            engine._log_job(result)

            # Verify exactly one log entry was created
            log_entries = session.query(EmbeddingLog).all()
            assert len(log_entries) == 1, (
                f"Expected exactly 1 log entry, got {len(log_entries)}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        files_processed=_p9_files_processed_st,
        chunks_generated=_p9_chunks_generated_st,
        num_errors=_p9_num_errors_st,
        status=_p9_job_status_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_log_entry_has_correct_file_and_chunk_counts(
        self,
        files_processed: int,
        chunks_generated: int,
        num_errors: int,
        status: str,
    ):
        """The log entry's files_processed and chunks_generated fields match
        the job result values.

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            errors = [
                {"file_id": i, "file_path": f"path_{i}.txt", "error": f"error_{i}"}
                for i in range(num_errors)
            ]
            result = _EmbeddingJobResult(
                files_processed=files_processed,
                chunks_generated=chunks_generated,
                errors=errors,
                status=status,
            )

            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            engine._log_job(result)

            log_entry = session.query(EmbeddingLog).first()
            assert log_entry.files_processed == files_processed, (
                f"Expected files_processed={files_processed}, "
                f"got {log_entry.files_processed}"
            )
            assert log_entry.chunks_generated == chunks_generated, (
                f"Expected chunks_generated={chunks_generated}, "
                f"got {log_entry.chunks_generated}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        files_processed=_p9_files_processed_st,
        chunks_generated=_p9_chunks_generated_st,
        num_errors=_p9_num_errors_st,
        status=_p9_job_status_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_log_entry_has_correct_status_mapping(
        self,
        files_processed: int,
        chunks_generated: int,
        num_errors: int,
        status: str,
    ):
        """The log entry's status field correctly maps from the job result status.

        Job status "success" or "partial_success" maps to log status "completed".
        Job status "error" maps to log status "failed".

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            errors = [
                {"file_id": i, "file_path": f"path_{i}.txt", "error": f"error_{i}"}
                for i in range(num_errors)
            ]
            result = _EmbeddingJobResult(
                files_processed=files_processed,
                chunks_generated=chunks_generated,
                errors=errors,
                status=status,
            )

            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            engine._log_job(result)

            log_entry = session.query(EmbeddingLog).first()

            # Map expected status
            expected_log_status_map = {
                "success": "completed",
                "partial_success": "completed",
                "error": "failed",
            }
            expected_status = expected_log_status_map[status]

            assert log_entry.status == expected_status, (
                f"For job status '{status}', expected log status "
                f"'{expected_status}', got '{log_entry.status}'"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        files_processed=_p9_files_processed_st,
        chunks_generated=_p9_chunks_generated_st,
        num_errors=_p9_num_errors_st,
        status=_p9_job_status_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_log_entry_has_valid_timestamp(
        self,
        files_processed: int,
        chunks_generated: int,
        num_errors: int,
        status: str,
    ):
        """The log entry has a timestamp that is a valid UTC datetime set at
        approximately the time the job was logged.

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            errors = [
                {"file_id": i, "file_path": f"path_{i}.txt", "error": f"error_{i}"}
                for i in range(num_errors)
            ]
            result = _EmbeddingJobResult(
                files_processed=files_processed,
                chunks_generated=chunks_generated,
                errors=errors,
                status=status,
            )

            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            before = datetime.now(timezone.utc)
            engine._log_job(result)
            after = datetime.now(timezone.utc)

            log_entry = session.query(EmbeddingLog).first()

            assert log_entry.timestamp is not None, "Log entry timestamp is None"

            # The timestamp should be between before and after (inclusive)
            # SQLite may strip timezone info, so compare naive datetimes
            ts = log_entry.timestamp
            if ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            before_naive = before.replace(tzinfo=None)
            after_naive = after.replace(tzinfo=None)

            assert before_naive <= ts <= after_naive, (
                f"Log timestamp {ts} is not between {before_naive} and {after_naive}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        files_processed=_p9_files_processed_st,
        chunks_generated=_p9_chunks_generated_st,
        num_errors=_p9_num_errors_st,
        status=_p9_job_status_st,
    )
    @settings(max_examples=100, deadline=None)
    def test_log_entry_errors_count_matches_errors_list_length(
        self,
        files_processed: int,
        chunks_generated: int,
        num_errors: int,
        status: str,
    ):
        """The log entry's errors_count field equals the length of the errors list
        from the job result.

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            errors = [
                {"file_id": i, "file_path": f"path_{i}.txt", "error": f"error_{i}"}
                for i in range(num_errors)
            ]
            result = _EmbeddingJobResult(
                files_processed=files_processed,
                chunks_generated=chunks_generated,
                errors=errors,
                status=status,
            )

            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            engine._log_job(result)

            log_entry = session.query(EmbeddingLog).first()
            assert log_entry.errors_count == num_errors, (
                f"Expected errors_count={num_errors}, "
                f"got {log_entry.errors_count}"
            )

        finally:
            session.close()
            db_engine.dispose()

    @given(
        num_jobs=st.integers(min_value=2, max_value=5),
        status=_p9_job_status_st,
    )
    @settings(max_examples=30, deadline=None)
    def test_multiple_jobs_produce_one_log_entry_each(
        self,
        num_jobs: int,
        status: str,
    ):
        """When multiple jobs complete sequentially, each produces exactly one
        log entry, resulting in N total entries for N jobs.

        **Validates: Requirements 3.7**
        """
        db_engine, Session = _create_test_db()
        session = Session()

        try:
            config = GraphRAGSettings()
            with patch("app.services.embedding_engine.TextExtractor"), \
                 patch("app.services.embedding_engine.DocumentChunker"), \
                 patch("app.services.embedding_engine.EmbeddingModel"), \
                 patch("app.services.embedding_engine.ChromaVectorStore"), \
                 patch("app.services.embedding_engine.GraphRAGEngine"):
                engine = EmbeddingEngine(db=session, config=config)

            for i in range(num_jobs):
                result = _EmbeddingJobResult(
                    files_processed=i + 1,
                    chunks_generated=(i + 1) * 5,
                    errors=[],
                    status=status,
                )
                engine._log_job(result)

            # Verify exactly num_jobs log entries exist
            log_entries = session.query(EmbeddingLog).all()
            assert len(log_entries) == num_jobs, (
                f"Expected {num_jobs} log entries after {num_jobs} jobs, "
                f"got {len(log_entries)}"
            )

            # Verify each entry has distinct data matching its job
            for i, entry in enumerate(log_entries):
                assert entry.files_processed == i + 1, (
                    f"Entry {i}: expected files_processed={i + 1}, "
                    f"got {entry.files_processed}"
                )
                assert entry.chunks_generated == (i + 1) * 5, (
                    f"Entry {i}: expected chunks_generated={(i + 1) * 5}, "
                    f"got {entry.chunks_generated}"
                )

        finally:
            session.close()
            db_engine.dispose()
