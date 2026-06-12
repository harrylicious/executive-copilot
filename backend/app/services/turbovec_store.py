"""TurboVec dual-index vector store service.

Manages two TurboQuantVectorStore indexes (master and department) with
cache persistence, document partitioning, and similarity search with
optional metadata filtering.
"""

import logging
import os
from pathlib import Path
from typing import Any

from langchain_core.embeddings import Embeddings

from app.config import TurboVecSettings
from app.services.document_chunker import DocumentChunker
from app.services.embedding_model import EmbeddingModel
from app.services.excel_loader import ExcelLoader
from app.services.text_extractor import TextExtractor
from turbovec.langchain import TurboQuantVectorStore

logger = logging.getLogger(__name__)

# Supported file extensions for document loading
SUPPORTED_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".docx", ".xlsx", ".xls", ".pdf"}


class _LangChainEmbeddingAdapter(Embeddings):
    """Adapter to make our EmbeddingModel compatible with LangChain's Embeddings interface."""

    def __init__(self, embedding_model: EmbeddingModel):
        self._model = embedding_model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._model.embed_texts(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._model.embed_query(text)


class TurboVecStore:
    """Dual-index TurboVec vector store with master and department indexes.

    Partitions documents from the knowledge base into two indexes:
    - master_index: documents from the master/ directory
    - dept_index: documents from all other department directories

    Both indexes use TurboQuantVectorStore with bit_width=4 for
    quantized vector storage.
    """

    def __init__(self, settings: TurboVecSettings, embedding_model: EmbeddingModel):
        """Initialize with settings and embedding model.

        Args:
            settings: TurboVec configuration including cache paths and chunking params.
            embedding_model: The embedding model used to generate vector embeddings.
        """
        self.settings = settings
        self.embedding_model = embedding_model
        self._lc_embedding = _LangChainEmbeddingAdapter(embedding_model)
        self.text_extractor = TextExtractor()
        self.chunker = DocumentChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            model_name=settings.embedding_model,
        )
        self.master_index: TurboQuantVectorStore | None = None
        self.dept_index: TurboQuantVectorStore | None = None

    def build_indexes(self, knowledge_base_path: str) -> None:
        """Build both indexes from scratch by scanning the knowledge base.

        Scans the knowledge base directory with two top-level directories:
        - master/ → master_index (master data: barang, outlet, distributor)
        - departments/ → dept_index (all department-specific documents)

        Any other top-level directories are also scanned into dept_index
        for backward compatibility.

        Args:
            knowledge_base_path: Root path to the knowledge base directory.

        Raises:
            ValueError: If the knowledge base path does not exist or contains
                no supported files.
        """
        kb_path = Path(knowledge_base_path)
        if not kb_path.exists() or not kb_path.is_dir():
            logger.error(
                f"Knowledge base path does not exist or is not a directory: {knowledge_base_path}"
            )
            raise ValueError(
                f"Knowledge base path does not exist: {knowledge_base_path}"
            )

        master_dir_name = self.settings.master_dir
        master_docs: list[dict] = []
        dept_docs: list[dict] = []

        # Scan all subdirectories in the knowledge base
        for top_dir in sorted(kb_path.iterdir()):
            if not top_dir.is_dir():
                continue

            dir_name = top_dir.name
            is_master = dir_name == master_dir_name

            if is_master:
                # Master directory: index all files directly into master_index
                files = self._find_supported_files(top_dir)
                for file_path in files:
                    chunks = self._process_file(file_path, "master")
                    master_docs.extend(chunks)
            elif dir_name == "departments":
                # Departments directory: recurse into each sub-department
                for dept_dir in sorted(top_dir.iterdir()):
                    if not dept_dir.is_dir():
                        continue
                    department = dept_dir.name
                    files = self._find_supported_files(dept_dir)
                    for file_path in files:
                        chunks = self._process_file(file_path, department)
                        dept_docs.extend(chunks)
            else:
                # Backward compatibility: any other top-level dir → dept_index
                files = self._find_supported_files(top_dir)
                for file_path in files:
                    chunks = self._process_file(file_path, dir_name)
                    dept_docs.extend(chunks)

        # Check if the knowledge base is empty
        if not master_docs and not dept_docs:
            logger.error(
                f"Knowledge base at '{knowledge_base_path}' contains no supported documents"
            )
            raise ValueError(
                f"Empty knowledge base: no supported documents found in '{knowledge_base_path}'"
            )

        # Build master index
        self.master_index = self._build_index(master_docs)
        logger.info(
            f"Built master_index with {len(master_docs)} document chunks"
        )

        # Build department index
        self.dept_index = self._build_index(dept_docs)
        logger.info(
            f"Built dept_index with {len(dept_docs)} document chunks"
        )

    def load_from_cache(self) -> bool:
        """Attempt to load indexes from cache directories.

        Loads master_index from ./index_cache/master/ and dept_index
        from ./index_cache/dept/. Both directories must exist and be
        loadable for this method to succeed.

        Returns:
            True if both indexes were loaded successfully from cache,
            False otherwise.
        """
        cache_dir = Path(self.settings.index_cache_dir)
        master_cache = cache_dir / "master"
        dept_cache = cache_dir / "dept"

        if not master_cache.exists() or not dept_cache.exists():
            logger.info("Cache directories not found, indexes need to be built fresh")
            return False

        try:
            self.master_index = TurboQuantVectorStore.load(
                master_cache, embedding=self._lc_embedding
            )
            logger.info(f"Loaded master_index from cache: {master_cache}")
        except Exception as e:
            logger.warning(
                f"Failed to load master_index from cache (corrupted?): {e}"
            )
            self.master_index = None
            return False

        try:
            self.dept_index = TurboQuantVectorStore.load(
                dept_cache, embedding=self._lc_embedding
            )
            logger.info(f"Loaded dept_index from cache: {dept_cache}")
        except Exception as e:
            logger.warning(
                f"Failed to load dept_index from cache (corrupted?): {e}"
            )
            self.dept_index = None
            return False

        return True

    def save_to_cache(self) -> None:
        """Persist both indexes to their cache directories.

        Creates the index_cache directory structure if it does not exist.
        Saves master_index to master/ and dept_index to dept/.
        """
        cache_dir = Path(self.settings.index_cache_dir)
        master_cache = cache_dir / "master"
        dept_cache = cache_dir / "dept"

        if self.master_index is not None:
            self.master_index.dump(master_cache)
            logger.info(f"Saved master_index to cache: {master_cache}")

        if self.dept_index is not None:
            self.dept_index.dump(dept_cache)
            logger.info(f"Saved dept_index to cache: {dept_cache}")

    def similarity_search(
        self,
        query_embedding: list[float],
        index: str,
        top_k: int,
        filename_filter: str | None = None,
    ) -> list[dict]:
        """Search a specific index with optional filename filter.

        Args:
            query_embedding: The query vector embedding.
            index: Which index to search - "master" or "dept".
            top_k: Maximum number of results to return.
            filename_filter: Optional filename substring filter for metadata matching.

        Returns:
            List of result dicts with 'content', 'metadata', and 'score' keys,
            ordered by descending similarity score.

        Raises:
            ValueError: If index is not "master" or "dept".
        """
        if index == "master":
            target_index = self.master_index
        elif index == "dept":
            target_index = self.dept_index
        else:
            raise ValueError(f"Invalid index '{index}': must be 'master' or 'dept'")

        if target_index is None:
            logger.warning(f"Index '{index}' is not initialized, returning empty results")
            return []

        # Build metadata filter if filename_filter is provided
        metadata_filter: dict[str, Any] | None = None
        if filename_filter:
            metadata_filter = {"filename": filename_filter}

        # Perform similarity search using the LangChain VectorStore interface
        results_with_scores = target_index.similarity_search_with_score(
            query="",  # unused when we override with by_vector below
            k=top_k,
            filter=metadata_filter,
        ) if False else self._search_by_vector(target_index, query_embedding, top_k, metadata_filter)

        return results_with_scores

    def _search_by_vector(
        self,
        target_index: TurboQuantVectorStore,
        query_embedding: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None,
    ) -> list[dict]:
        """Perform vector similarity search and convert results to dict format.

        If metadata_filter is provided and the index doesn't natively support
        filtering, performs post-retrieval filtering with an over-fetch strategy.
        """
        import numpy as np
        from langchain_core.documents import Document

        qvec = np.asarray(query_embedding, dtype=np.float32)
        if qvec.ndim == 1:
            qvec = qvec[None, :]
        if not qvec.flags["C_CONTIGUOUS"]:
            qvec = np.ascontiguousarray(qvec)

        # Over-fetch when filtering to ensure we get enough results after post-filter
        fetch_k = top_k * 3 if metadata_filter else top_k

        # Use the internal _search_vector for score access
        if hasattr(target_index, '_search_vector'):
            # Build a filter callable or dict for the LangChain interface
            lc_filter = metadata_filter if metadata_filter else None
            try:
                raw_results = target_index._search_vector(qvec, fetch_k, filter=lc_filter)
            except (TypeError, Exception):
                # Fallback: search without filter and post-filter manually
                raw_results = target_index._search_vector(qvec, fetch_k, filter=None)
        else:
            # Fallback: use similarity_search_by_vector (no scores)
            try:
                docs = target_index.similarity_search_by_vector(
                    embedding=query_embedding,
                    k=fetch_k,
                    filter=metadata_filter,
                )
            except (TypeError, Exception):
                docs = target_index.similarity_search_by_vector(
                    embedding=query_embedding,
                    k=fetch_k,
                )
            raw_results = [(doc, 1.0) for doc in docs]

        results: list[dict] = []
        for doc, score in raw_results:
            metadata = doc.metadata if hasattr(doc, 'metadata') else {}

            # Post-filter: if metadata_filter specified, check substring match
            if metadata_filter:
                match = True
                for key, value in metadata_filter.items():
                    doc_value = str(metadata.get(key, "")).lower()
                    filter_value = str(value).lower()
                    if filter_value not in doc_value:
                        match = False
                        break
                if not match:
                    continue

            results.append({
                "content": doc.page_content,
                "metadata": metadata,
                "score": float(score),
            })

            if len(results) >= top_k:
                break

        return results

    def add_documents(
        self,
        dir_path: str,
        label: str,
        target: str = "dept",
    ) -> None:
        """Incrementally add documents to an existing index.

        Loads supported files from dir_path, chunks them, generates
        embeddings, attaches the label as metadata, and adds them to
        the target index.

        Args:
            dir_path: Directory path containing files to ingest.
            label: String label attached as metadata to each document
                for downstream filename-based filtering.
            target: Which index to add to - "master" or "dept".

        Raises:
            ValueError: If dir_path doesn't exist, has no supported files,
                or target is invalid.
        """
        # Validate target
        if target not in ("master", "dept"):
            raise ValueError(
                f"Invalid target '{target}': must be 'master' or 'dept'"
            )

        # Validate directory
        path = Path(dir_path)
        if not path.exists() or not path.is_dir():
            raise ValueError(
                f"Directory path not found: {dir_path}"
            )

        # Find supported files
        files = self._find_supported_files(path)
        if not files:
            raise ValueError(
                f"No supported files found in '{dir_path}'. "
                f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        # Process files into document chunks with label metadata
        docs: list[dict] = []
        for file_path in files:
            chunks = self._process_file(file_path, label)
            # Override filename metadata with label for filtering
            for chunk in chunks:
                chunk["metadata"]["filename"] = label
            docs.extend(chunks)

        if not docs:
            raise ValueError(
                f"No content could be extracted from files in '{dir_path}'"
            )

        # Get the target index
        if target == "master":
            target_index = self.master_index
        else:
            target_index = self.dept_index

        if target_index is None:
            raise ValueError(
                f"Target index '{target}' is not initialized. "
                "Build or load indexes first."
            )

        # Add texts with metadata via the LangChain interface
        texts = [doc["content"] for doc in docs]
        metadatas = [doc["metadata"] for doc in docs]

        target_index.add_texts(
            texts=texts,
            metadatas=metadatas,
        )

        # Save updated index to cache
        self.save_to_cache()
        logger.info(
            f"Added {len(docs)} document chunks to '{target}' index "
            f"from '{dir_path}' with label '{label}'"
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _find_supported_files(self, directory: Path) -> list[Path]:
        """Recursively find all files with supported extensions in a directory.

        Args:
            directory: The directory to scan.

        Returns:
            Sorted list of Path objects for supported files.
        """
        files: list[Path] = []
        for root, _dirs, filenames in os.walk(directory):
            for filename in filenames:
                file_path = Path(root) / filename
                if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(file_path)
        return sorted(files)

    def _process_file(self, file_path: Path, department: str) -> list[dict]:
        """Extract text from a file, chunk it, and produce document dicts.

        For Excel files (.xlsx/.xls), uses ExcelLoader to produce structured
        per-sheet documents with column headers, then chunks each sheet
        independently with sheet-aware metadata. This ensures each sheet's
        data is properly categorized for filtering.

        For other file types, uses the generic TextExtractor.

        Args:
            file_path: Path to the file to process.
            department: The department/label name for metadata.

        Returns:
            List of dicts with 'content' and 'metadata' keys.
        """
        suffix = file_path.suffix.lower()

        # Use ExcelLoader for Excel files to get structured per-sheet documents
        if suffix in (".xlsx", ".xls"):
            return self._process_excel_file(file_path, department)

        text = self.text_extractor.extract(file_path, file_path.suffix)
        if not text:
            return []

        chunks = self.chunker.chunk(text)
        if not chunks:
            return []

        # Derive a category tag from the filename for filtering.
        # E.g. "Master_Barang_Satuan_Bertingkat_Inventory" → "barang"
        filename_lower = file_path.stem.lower()
        category = self._detect_file_category(filename_lower)

        docs: list[dict] = []
        for chunk in chunks:
            doc = {
                "content": chunk.text,
                "metadata": {
                    "file_id": hash(str(file_path)) % (10**9),
                    "chunk_index": chunk.chunk_index,
                    "department": department,
                    "filename": category if category else file_path.stem.lower(),
                    "source_file": file_path.stem,
                    "sheet_name": None,
                },
            }
            docs.append(doc)

        return docs

    def _process_excel_file(self, file_path: Path, department: str) -> list[dict]:
        """Process an Excel file using ExcelLoader for structured per-sheet extraction.

        For master data files, uses a per-row indexing strategy where each row
        becomes its own document. This ensures precise lookup of individual
        products, outlets, and vendors.

        For other files, uses the standard chunking approach.

        Falls back to the generic TextExtractor if ExcelLoader fails.

        Args:
            file_path: Path to the .xlsx/.xls file.
            department: The department/label name for metadata.

        Returns:
            List of dicts with 'content' and 'metadata' keys.
        """
        excel_loader = ExcelLoader()
        documents = excel_loader.load(file_path)

        if not documents:
            # Fallback to generic text extraction
            logger.warning(
                f"ExcelLoader returned no documents for '{file_path}', "
                f"falling back to generic text extraction"
            )
            text = self.text_extractor.extract(file_path, file_path.suffix)
            if not text:
                return []
            chunks = self.chunker.chunk(text)
            if not chunks:
                return []
            filename_lower = file_path.stem.lower()
            category = self._detect_file_category(filename_lower)
            docs: list[dict] = []
            for chunk in chunks:
                docs.append({
                    "content": chunk.text,
                    "metadata": {
                        "file_id": hash(str(file_path)) % (10**9),
                        "chunk_index": chunk.chunk_index,
                        "department": department,
                        "filename": category if category else file_path.stem.lower(),
                        "source_file": file_path.stem,
                        "sheet_name": None,
                    },
                })
            return docs

        # Process each sheet document separately
        all_docs: list[dict] = []
        file_category = self._detect_file_category(file_path.stem.lower())

        for doc in documents:
            sheet_name = doc.metadata.get("sheet_name", "")
            text = doc.page_content
            if not text:
                continue

            # Determine category from sheet name first, then fall back to file name
            sheet_category = self._detect_file_category(sheet_name.lower())
            category = sheet_category or file_category or file_path.stem.lower()

            # For master data, use per-row indexing for precise lookups
            # Each row becomes its own document for exact matching
            is_master_data = category in ("barang", "outlet", "distributor")

            if is_master_data:
                rows = text.split("\n")
                for row_idx, row in enumerate(rows):
                    row_stripped = row.strip()
                    if not row_stripped:
                        continue
                    all_docs.append({
                        "content": row_stripped,
                        "metadata": {
                            "file_id": hash(str(file_path)) % (10**9),
                            "chunk_index": row_idx,
                            "department": department,
                            "filename": category,
                            "source_file": file_path.stem,
                            "sheet_name": sheet_name,
                        },
                    })
            else:
                # Non-master sheets: use standard chunking
                chunks = self.chunker.chunk(text)
                if not chunks:
                    continue
                for chunk in chunks:
                    all_docs.append({
                        "content": chunk.text,
                        "metadata": {
                            "file_id": hash(str(file_path)) % (10**9),
                            "chunk_index": chunk.chunk_index,
                            "department": department,
                            "filename": category,
                            "source_file": file_path.stem,
                            "sheet_name": sheet_name,
                        },
                    })

        return all_docs

    def _detect_file_category(self, filename_lower: str) -> str | None:
        """Detect the category of a file or sheet based on its name.

        Maps name substrings to category labels used for metadata filtering.
        Returns the first matching category or None if no match.

        Handles both filename patterns (e.g. "master_barang_satuan...") and
        sheet name patterns (e.g. "mbarang", "moutlet", "mpd").

        Args:
            filename_lower: Lowercased filename stem or sheet name.

        Returns:
            Category string ("barang", "outlet", "distributor") or None.
        """
        category_keywords = {
            "barang": ["barang", "produk", "item", "sku", "inventory", "mbarang"],
            "outlet": ["outlet", "toko", "gerai", "cabang", "moutlet"],
            "distributor": ["distributor", "dist", "agen", "supplier", "mpd"],
        }
        for category, keywords in category_keywords.items():
            for keyword in keywords:
                if keyword in filename_lower:
                    return category
        return None

    def _build_index(self, docs: list[dict]) -> TurboQuantVectorStore:
        """Build a TurboQuantVectorStore from document chunks.

        Generates embeddings for all documents and creates a quantized
        vector index with bit_width=4.

        Args:
            docs: List of document dicts with 'content' and 'metadata'.

        Returns:
            A TurboQuantVectorStore populated with the document embeddings.
        """
        if not docs:
            # Create an empty index
            return TurboQuantVectorStore(
                embedding=self._lc_embedding,
                bit_width=4,
            )

        texts = [doc["content"] for doc in docs]
        metadatas = [doc["metadata"] for doc in docs]

        store = TurboQuantVectorStore.from_texts(
            texts=texts,
            embedding=self._lc_embedding,
            metadatas=metadatas,
            bit_width=4,
        )

        return store
