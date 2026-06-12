# Requirements Document

## Introduction

This feature migrates the Executive Copilot's retrieval backend from GraphRAG (entity extraction, relationship mapping, community detection, community summaries) with ChromaDB to a streamlined dual-index TurboVec vector store with keyword-based intent routing. The migration removes all graph-related logic and dependencies (spacy, networkx, leidenalg, igraph, chromadb), replaces the vector store with turbovec[langchain] (TurboQuantVectorStore, bit_width=4), introduces a query router that detects Bahasa Indonesia keywords to route queries to the appropriate index, updates the system prompt to Indonesian, and enhances the Excel loader to produce structured row-per-sheet documents.

## Glossary

- **Executive_Copilot**: The FastAPI application serving as an intelligent business assistant for Indonesian executives.
- **TurboVec_Store**: The replacement vector store using `turbovec[langchain]` with `TurboQuantVectorStore` at `bit_width=4`.
- **Master_Index**: A TurboVec index containing documents from the `master/` directory (master barang, outlet, distributor).
- **Dept_Index**: A TurboVec index containing documents from all department directories except `master/`.
- **Query_Router**: A component that inspects the user query for Bahasa Indonesia keywords and determines which index to query and how to filter results.
- **Index_Cache**: The directory `./index_cache/` where serialized TurboVec indexes are persisted as `.tv` files.
- **Document_Chunker**: The existing token-based text chunker that splits documents into overlapping chunks.
- **Excel_Loader**: The component that reads `.xlsx`/`.xls` files, converting each sheet's rows into structured text documents.
- **RAG_Chain**: The LangChain-based Retrieval-Augmented Generation chain that assembles context and invokes the LLM.
- **Retrieval_Service**: The service layer that coordinates vector search and context assembly for downstream LLM consumption.
- **Knowledge_Base_Path**: The root directory `./knowledge_base/{department}/{subfolder}/` containing departmental documents.

## Requirements

### Requirement 1: Remove GraphRAG Components

**User Story:** As a maintainer, I want all GraphRAG-specific logic removed from the codebase, so that the system no longer depends on graph construction, entity extraction, relationship mapping, or community detection.

#### Acceptance Criteria

1. THE Executive_Copilot SHALL NOT contain the source files `entity_extractor`, `relationship_extractor`, `relationship_engine`, `community_detector`, or `graphrag_engine` in its services directory, and no remaining module SHALL import from or invoke functions defined in those modules.
2. THE Executive_Copilot SHALL NOT depend on the packages `spacy`, `networkx`, `leidenalg`, or `igraph` in its requirements file, and the application SHALL start without those packages installed.
3. THE Retrieval_Service SHALL perform vector-similarity-only search and SHALL NOT invoke graph neighborhood lookups, community summary retrieval, or combined local-global search merging that depends on graph or community data.
4. WHEN the application starts, THE Executive_Copilot SHALL NOT execute entity extraction, relationship extraction, or community detection during the startup lifespan, and SHALL NOT log or reference `GraphRAGSettings` fields related to `entity_extraction_method`, `community_resolution`, or `max_community_size`.
5. THE Executive_Copilot SHALL remove the database models `Entity`, `EntityRelationship`, `Community`, and `Relationship` and their source files, and SHALL NOT create their corresponding database tables during the lifespan startup.
6. THE Executive_Copilot SHALL NOT register or serve the graph router (e.g., `/api/graph` endpoints), and any HTTP request to a previously existing graph endpoint SHALL return a 404 status.
7. THE Executive_Copilot SHALL remove or update all test files that reference removed GraphRAG modules so that the full test suite passes without import errors or skipped-due-to-missing-module failures.

### Requirement 2: Remove ChromaDB Dependency

**User Story:** As a maintainer, I want ChromaDB replaced entirely, so that the system uses TurboVec as its sole vector store backend.

#### Acceptance Criteria

1. THE Executive_Copilot SHALL NOT import or reference the `chromadb` package in any source, test, or configuration file.
2. THE Executive_Copilot SHALL NOT reference the `ChromaVectorStore` class or the `./chroma_db` directory in any source or configuration file.
3. THE Executive_Copilot SHALL NOT include `chromadb` in its requirements file or pyproject.toml dependencies.
4. THE Executive_Copilot SHALL NOT contain the `vector_store_path` configuration field referencing `./chroma_db` in the settings module.

### Requirement 3: Implement TurboVec Dual-Index Vector Store

**User Story:** As a developer, I want a dual-index TurboVec vector store with master and department indexes, so that documents are organized for efficient intent-based retrieval.

#### Acceptance Criteria

1. THE TurboVec_Store SHALL create exactly two indexes: `master_index` for documents in the `master/` directory and `dept_index` for documents in all other department directories.
2. THE TurboVec_Store SHALL use `TurboQuantVectorStore` with `bit_width=4` for both indexes.
3. THE TurboVec_Store SHALL persist the `master_index` as `./index_cache/master.tv` and the `dept_index` as `./index_cache/dept.tv`, creating the `./index_cache/` directory if it does not already exist.
4. WHEN the application starts and cache files exist at both `./index_cache/master.tv` and `./index_cache/dept.tv`, THE TurboVec_Store SHALL load indexes from those cached files.
5. WHEN the application starts and either or both cache files do not exist, THE TurboVec_Store SHALL build both indexes fresh from the knowledge base documents and save them to the cache directory.
6. IF index building fails due to an empty knowledge base directory, missing embedding model, or an unrecoverable error during embedding, THEN THE TurboVec_Store SHALL log an error message indicating the failure reason and raise an exception that prevents the application from starting with incomplete indexes.
7. THE Executive_Copilot SHALL include `turbovec[langchain]` in its requirements file as a replacement for `chromadb`.

### Requirement 4: Implement Query Router with Bahasa Indonesia Keyword Detection

**User Story:** As a user querying in Bahasa Indonesia, I want my queries automatically routed to the correct index based on keywords, so that I receive relevant master data or departmental documents without specifying which source to search.

#### Acceptance Criteria

1. THE Query_Router SHALL implement a `_detect_intent(query)` method that lowercases the query and checks for Bahasa Indonesia keywords using substring matching against the lowercased query string.
2. WHEN the query contains any of the keywords `barang`, `produk`, `item`, `sku`, `kode barang`, THE Query_Router SHALL route to `master_index` with a filename filter for "barang".
3. WHEN the query contains any of the keywords `outlet`, `toko`, `gerai`, THE Query_Router SHALL route to `master_index` with a filename filter for "outlet".
4. WHEN the query contains any of the keywords `distributor`, `dist`, `agen`, THE Query_Router SHALL route to `master_index` with a filename filter for "distributor".
5. WHEN the query matches keywords from multiple master keyword sets, THE Query_Router SHALL use the first matching set in evaluation order (barang, outlet, distributor) to determine the filename filter.
6. WHEN the query does not match any master keyword set, THE Query_Router SHALL route to `dept_index` only.
7. WHEN the routing mode is `master_first`, THE Query_Router SHALL retrieve top 8 results from `master_index` (filtered by detected type, with fallback to all master documents if the filter returns fewer than 1 result) plus top 2 supplementary results from `dept_index`, with master chunks ordered first and results within each group ordered by descending similarity score.
8. WHEN the routing mode is `dept_only`, THE Query_Router SHALL retrieve top 5 results from `dept_index` ordered by descending similarity score.
9. IF the query is empty or contains only whitespace, THEN THE Query_Router SHALL route to `dept_index` only with no filename filter applied.

### Requirement 5: Update Document Chunking Configuration

**User Story:** As a developer, I want the chunking parameters updated to the new configuration values, so that document chunks are sized appropriately for TurboVec retrieval.

#### Acceptance Criteria

1. THE Document_Chunker SHALL default to a `chunk_size` of 600 tokens when instantiated without an explicit `chunk_size` argument.
2. THE Document_Chunker SHALL default to a `chunk_overlap` of 80 tokens when instantiated without an explicit `chunk_overlap` argument.
3. THE configuration settings SHALL define `CHUNK_SIZE = 600` and `CHUNK_OVERLAP = 80` as the default values, overridable via the `KB_CHUNK_SIZE` and `KB_CHUNK_OVERLAP` environment variables.
4. IF the configured `chunk_overlap` exceeds `chunk_size // 2`, THEN THE configuration settings SHALL fall back to the default `chunk_overlap` of 80.
5. WHEN the application starts with updated chunking defaults, THE indexing pipeline SHALL re-chunk and re-index all knowledge base documents using the new `chunk_size` and `chunk_overlap` values.

### Requirement 6: Enhance Excel Loader for Structured Row Output

**User Story:** As a user with Excel-based master data, I want each sheet converted into a structured document with column-value pairs per row, so that tabular data is properly searchable.

#### Acceptance Criteria

1. WHEN an `.xlsx` or `.xls` file is loaded, THE Excel_Loader SHALL read each sheet using pandas and convert all sheets into Documents.
2. WHEN processing a sheet, THE Excel_Loader SHALL convert each row into the format `KolomA: nilaiA | KolomB: nilaiB` using the actual column headers and cell values, omitting columns whose cell value is empty or NaN for that row.
3. THE Excel_Loader SHALL join all formatted rows within a sheet using a newline character as the separator to form the Document's page content.
4. THE Excel_Loader SHALL produce one Document per sheet with metadata containing the sheet name, source file path, and filename.
5. IF a sheet contains only a header row and zero non-empty data rows (rows where all cell values are NaN or empty), THEN THE Excel_Loader SHALL skip that sheet and produce no Document for it.
6. IF the Excel file cannot be read due to corruption or unsupported format, THEN THE Excel_Loader SHALL skip the file and produce no Documents for it.
7. WHEN processing a sheet, THE Excel_Loader SHALL use the first non-empty row as column headers and treat subsequent rows as data rows.

### Requirement 7: Replace System Prompt with Indonesian Business Assistant Prompt

**User Story:** As a product owner, I want the system prompt replaced with a formal Indonesian business assistant prompt, so that the copilot responds consistently in Bahasa Indonesia with proper business context rules.

#### Acceptance Criteria

1. THE RAG_Chain SHALL use the following exact system prompt template:
   ```
   Kamu adalah Executive Copilot, asisten bisnis cerdas untuk para eksekutif.
   Jawab pertanyaan berdasarkan konteks dokumen yang diberikan.
   Aturan:
   - Jawab dalam Bahasa Indonesia yang formal dan ringkas
   - Jika pertanyaan tentang data barang/produk, gunakan data dari master barang
   - Jika pertanyaan tentang outlet/toko, gunakan data dari master outlet
   - Jika pertanyaan tentang distributor/agen, gunakan data dari master distributor
   - Sertakan angka/data spesifik jika tersedia di konteks
   - Jika data tidak tersedia di konteks, katakan "Data tidak ditemukan dalam dokumen yang tersedia"
   - JANGAN mengarang data yang tidak ada di konteks
   Konteks dokumen:
   {context}
   Pertanyaan: {question}
   Jawaban:
   ```
2. THE RAG_Chain SHALL NOT contain the previous English-language `_RAG_SYSTEM_PROMPT` string, the `_LANGUAGE_INSTRUCTIONS` dictionary, or the `{language_instruction}` placeholder pattern.
3. THE RAG_Chain SHALL substitute `{context}` with the retrieved document chunks concatenated as a single string where each chunk is separated by a blank line, and SHALL substitute `{question}` with the user query text as received from the request.
4. WHEN the retriever returns zero documents for a query, THE RAG_Chain SHALL still invoke the LLM with the system prompt template where `{context}` is substituted with an empty string, allowing the prompt's built-in rule to produce the "Data tidak ditemukan dalam dokumen yang tersedia" response.
5. THE RAG_Chain SHALL send the fully substituted prompt template as a single message to the LLM (the template already contains both instructions and the user question, so no separate user message with the query is appended).

### Requirement 8: Add Incremental Document Ingestion Utility

**User Story:** As an administrator, I want to add new documents to an existing index without a full rebuild, so that new files are searchable immediately without reprocessing the entire knowledge base.

#### Acceptance Criteria

1. THE TurboVec_Store SHALL provide an `add_documents(dir_path, label, target="dept")` method where `label` is a string attached as metadata to each ingested document for downstream filename-based filtering by the Query_Router.
2. WHEN `add_documents` is called, THE TurboVec_Store SHALL load all supported files (`.txt`, `.md`, `.csv`, `.json`, `.docx`, `.xlsx`, `.xls`, `.pdf`) from `dir_path`, chunk them using the configured `CHUNK_SIZE` and `CHUNK_OVERLAP`, embed them, attach the provided `label` as document metadata, and add them to the index specified by `target` (`master_index` when target is "master", `dept_index` when target is "dept").
3. WHEN `add_documents` completes successfully, THE TurboVec_Store SHALL save the updated index to its corresponding cache file.
4. IF `dir_path` does not exist or contains no files with supported extensions (`.txt`, `.md`, `.csv`, `.json`, `.docx`, `.xlsx`, `.xls`, `.pdf`), THEN THE TurboVec_Store SHALL raise an error indicating whether the path was not found or no supported files were detected, without modifying the existing index.
5. IF the `target` parameter is not one of "master" or "dept", THEN THE TurboVec_Store SHALL raise an error indicating the invalid target value without modifying any index.

### Requirement 9: Preserve Existing API Contract

**User Story:** As a frontend developer, I want all existing FastAPI endpoints to maintain their current request and response shapes, so that no frontend changes are required after the migration.

#### Acceptance Criteria

1. THE Executive_Copilot SHALL maintain all existing endpoint paths under `/api/chat`, `/api/chat/stream`, `/api/search/local`, `/api/search/global`, and `/api/search/combined`.
2. THE Executive_Copilot SHALL preserve the request schemas (`ChatRequest`, `LocalSearchRequest`, `GlobalSearchRequest`, `CombinedSearchRequest`) and response schemas (`ChatResponse`, `SearchResponse`) without breaking changes.
3. WHEN the `/api/search/local` endpoint is called, THE Retrieval_Service SHALL perform vector similarity search using the TurboVec_Store with intent routing instead of graph-enriched search.
4. WHEN the `/api/search/global` or `/api/search/combined` endpoints are called, THE Retrieval_Service SHALL perform vector search using the Query_Router logic (the community-based global search concept is removed, but the endpoint remains functional by routing to the appropriate TurboVec index).
5. THE search endpoints SHALL continue to accept the same request parameters (top_k, min_score, similarity_weight, num_communities, min_relevance, max_tokens) even though some parameters may become no-ops after the migration.
6. THE error response status codes (400, 422, 500, 503, 504) SHALL remain unchanged for the same error conditions across all preserved endpoints.

### Requirement 10: Maintain Application Startup and Lifespan Pattern

**User Story:** As a developer, I want the application startup flow preserved with TurboVec initialization replacing ChromaDB and GraphRAG initialization, so that the deployment pattern remains unchanged.

#### Acceptance Criteria

1. WHEN the application starts and cache files exist at `./index_cache/master.tv` and `./index_cache/dept.tv`, THE Executive_Copilot SHALL load the TurboVec indexes from those files before serving any requests.
2. WHEN the application starts and one or both cache files do not exist, THE Executive_Copilot SHALL build indexes by scanning the knowledge base, chunking documents, generating embeddings, and saving the indexes to the cache directory before serving any requests.
3. IF a cache file exists but cannot be loaded (corrupted or incompatible), THEN THE Executive_Copilot SHALL log a warning, discard the unreadable cache file, rebuild the affected index from the knowledge base, and save the rebuilt index to the cache directory.
4. IF the knowledge base directory contains no supported files during a fresh index build, THEN THE Executive_Copilot SHALL create empty indexes, save them to the cache directory, and log a warning indicating no documents were indexed.
5. THE Executive_Copilot SHALL implement TurboVec initialization within an `asynccontextmanager`-based lifespan function passed to the FastAPI application constructor, with all initialization completing before the `yield` statement.
6. THE Executive_Copilot SHALL define all new TurboVec configuration parameters (index cache directory, master directory name, top-k values) as fields on a `pydantic-settings` `BaseSettings` subclass using the `KB_` environment variable prefix, matching the existing configuration pattern.

### Requirement 11: Update Configuration Constants

**User Story:** As a developer, I want the new configuration constants centralized in the settings module, so that all TurboVec and routing parameters are configurable via environment variables.

#### Acceptance Criteria

1. THE configuration SHALL define `MASTER_TOP_K` with a default value of `8` as the number of results from master_index in master_first mode, accepting integer values from 1 to 100.
2. THE configuration SHALL define `DEPT_TOP_K` with a default value of `5` as the number of results from dept_index in dept_only mode, accepting integer values from 1 to 100.
3. THE configuration SHALL define `MASTER_FIRST_SUPPLEMENT_K` with a default value of `2` as the number of supplementary dept_index results in master_first mode, accepting integer values from 0 to 100.
4. THE configuration SHALL define `INDEX_CACHE_DIR` with a default value of `"./index_cache"` as the cache directory path for persisted TurboVec indexes.
5. THE configuration SHALL define `MASTER_DIR` with a default value of `"master"` as the directory name for master data within the knowledge base.
6. THE configuration SHALL allow overriding each constant via an environment variable using the `KB_` prefix followed by the uppercase constant name (e.g., `KB_MASTER_TOP_K`, `KB_DEPT_TOP_K`, `KB_INDEX_CACHE_DIR`, `KB_MASTER_DIR`, `KB_MASTER_FIRST_SUPPLEMENT_K`).
7. IF an environment variable for an integer constant contains a non-integer value or a value outside its valid range, THEN THE configuration SHALL apply the documented default value for that constant and log a warning identifying the rejected value.
8. THE configuration SHALL use the existing `pydantic-settings` BaseSettings pattern with `env_prefix = "KB_"` consistent with the current Settings class structure.

### Requirement 12: Update Dependencies

**User Story:** As a maintainer, I want the requirements.txt updated to reflect the new dependency set, so that the project installs correctly without unused packages.

#### Acceptance Criteria

1. THE requirements file SHALL add `turbovec[langchain]` as a dependency with a minimum version constraint.
2. THE requirements file SHALL add `pandas` as a dependency with a minimum version constraint (e.g., `>=1.5.0`).
3. THE requirements file SHALL remove `chromadb`, `spacy`, `networkx`, `leidenalg`, and `igraph` from the dependency list.
4. THE requirements file SHALL retain all other existing dependencies including `fastapi`, `uvicorn`, `sqlalchemy`, `pydantic`, `pydantic-settings`, `python-dotenv`, `python-multipart`, `sentence-transformers`, `tiktoken`, `langchain`, `langchain-openai`, `langgraph`, `langsmith`, `sse-starlette`, `python-docx`, `PyMuPDF`, and `openpyxl` with their current version constraints unchanged.
5. WHEN a maintainer runs `pip install -r requirements.txt` in a clean virtual environment, THE requirements file SHALL resolve all dependencies without conflicts and install successfully.
