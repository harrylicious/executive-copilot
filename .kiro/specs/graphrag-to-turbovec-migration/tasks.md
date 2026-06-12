# Implementation Plan: GraphRAG to TurboVec Migration

## Overview

This plan migrates the Executive Copilot's retrieval backend from GraphRAG with ChromaDB to a dual-index TurboVec vector store with keyword-based intent routing. Tasks are ordered to establish foundations first (configuration, dependencies, removals), then build new components (TurboVec store, query router, Excel loader), update existing services (RAG chain, retrieval service, API layer), and finally wire everything together with incremental ingestion and comprehensive tests.

## Tasks

- [x] 1. Update dependencies and configuration
  - [x] 1.1 Update `requirements.txt` to remove GraphRAG dependencies and add TurboVec
    - Remove `chromadb`, `spacy`, `networkx`, `leidenalg`, `igraph` from `requirements.txt`
    - Add `turbovec[langchain]>=0.1.0` and `pandas>=1.5.0`
    - Retain all other existing dependencies unchanged
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 3.7_

  - [x] 1.2 Create `TurboVecSettings` configuration class in `app/config.py`
    - Add `TurboVecSettings(BaseSettings)` with `env_prefix = "KB_"`
    - Define fields: `chunk_size=600`, `chunk_overlap=80`, `master_top_k=8`, `dept_top_k=5`, `master_first_supplement_k=2`, `index_cache_dir="./index_cache"`, `master_dir="master"`, `embedding_model="all-MiniLM-L6-v2"`
    - Add validation: integer range checks (1-100 for top_k values), fallback to defaults for invalid values with warning log
    - Add chunk_overlap validation: if `chunk_overlap > chunk_size // 2`, fall back to default 80
    - Remove `GraphRAGSettings` and `vector_store_path` referencing `./chroma_db`
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8, 5.1, 5.2, 5.3, 5.4, 2.4_

  - [x]* 1.3 Write property tests for configuration validation (Properties 7 and 8)
    - **Property 7: Configuration validation with fallback** — For any integer config constant with a defined valid range, setting an env var to a non-integer or out-of-range value SHALL result in the default being applied
    - **Property 8: Chunk overlap validation** — For any configured `chunk_overlap` exceeding `chunk_size // 2`, the configuration SHALL fall back to default 80
    - **Validates: Requirements 11.1, 11.2, 11.3, 11.7, 5.4**

- [x] 2. Remove GraphRAG components and ChromaDB
  - [x] 2.1 Delete GraphRAG service files and database models
    - Delete `app/services/entity_extractor.py`, `app/services/relationship_extractor.py`, `app/services/relationship_engine.py`, `app/services/community_detector.py`, `app/services/graphrag_engine.py`
    - Delete `app/services/vector_store.py` (ChromaDB vector store)
    - Delete `app/models/entity.py`, `app/models/entity_relationship.py`, `app/models/community.py`, `app/models/relationship.py`
    - Delete `app/routers/graph.py`, `app/schemas/graph.py`, `app/schemas/relationship.py`
    - _Requirements: 1.1, 1.5, 1.6, 2.1, 2.2_

  - [x] 2.2 Remove GraphRAG imports and references from remaining modules
    - Remove imports of deleted modules from `__init__.py` files, router registrations, and model registrations
    - Remove graph router registration from `app/main.py` (or equivalent)
    - Remove GraphRAG-related startup logic (entity extraction, relationship extraction, community detection) from lifespan function
    - Remove `GraphRAGSettings` references from config imports
    - Ensure no remaining module imports from or invokes functions in the deleted modules
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.6, 2.1, 2.2, 2.3, 2.4_

  - [x] 2.3 Update or remove test files referencing GraphRAG modules
    - Remove or update test files that import from deleted GraphRAG/ChromaDB modules
    - Ensure the full test suite passes without import errors or skipped-due-to-missing-module failures
    - _Requirements: 1.7, 2.1_

- [x] 3. Implement TurboVec dual-index store
  - [x] 3.1 Create `app/services/turbovec_store.py` with `TurboVecStore` class
    - Implement `__init__` accepting `TurboVecSettings` and embedding model
    - Implement `build_indexes(knowledge_base_path)` — scan knowledge base, partition docs: `master/` → `master_index`, others → `dept_index`
    - Use `TurboQuantVectorStore` with `bit_width=4` for both indexes
    - Implement `load_from_cache()` — load from `./index_cache/master.tv` and `./index_cache/dept.tv`, return True if both loaded successfully
    - Implement `save_to_cache()` — persist both indexes, create `./index_cache/` if needed
    - Implement `similarity_search(query_embedding, index, top_k, filename_filter)` — search specified index with optional metadata filter
    - Handle error cases: empty knowledge base (log error, raise exception), corrupted cache (log warning, rebuild)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 10.1, 10.2, 10.3, 10.4_

  - [x]* 3.2 Write property test for document partitioning (Property 11)
    - **Property 11: Document partitioning into dual indexes** — For any knowledge base with a `master/` subdirectory and other directories, all `master/` docs go to `master_index`, all others to `dept_index`, with no document in both
    - **Validates: Requirements 3.1**

  - [x] 3.3 Implement `add_documents` method for incremental ingestion
    - Implement `add_documents(dir_path, label, target="dept")` on `TurboVecStore`
    - Load supported files (`.txt`, `.md`, `.csv`, `.json`, `.docx`, `.xlsx`, `.xls`, `.pdf`), chunk with configured params, embed, attach `label` as metadata, add to target index
    - Save updated index to cache after successful addition
    - Raise error if `dir_path` not found, no supported files, or invalid `target` (not "master"/"dept")
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 3.4 Write property tests for incremental ingestion (Properties 9 and 10)
    - **Property 9: Incremental ingestion label attachment** — For any valid `add_documents` call, all resulting chunks SHALL have the provided `label` in metadata
    - **Property 10: Incremental ingestion error handling** — For invalid `dir_path`, no supported files, or invalid `target`, SHALL raise error without modifying indexes
    - **Validates: Requirements 8.2, 8.4, 8.5**

- [x] 4. Implement Query Router
  - [x] 4.1 Create `app/services/query_router.py` with `QueryRouter` class
    - Define `RoutingDecision` dataclass with `mode`, `filename_filter`, `master_top_k`, `dept_top_k`
    - Define `KEYWORD_SETS` with priority order: barang/produk/item/sku/kode barang → "barang", outlet/toko/gerai → "outlet", distributor/dist/agen → "distributor"
    - Implement `_detect_intent(query)` — lowercase query, substring match against keyword sets in priority order
    - Implement `route(query)` — return `RoutingDecision` based on detected intent
    - Implement `retrieve(query, query_embedding, store)` — execute routing + retrieval pipeline
    - Handle `master_first` mode: top 8 from master (with filter, fallback to all if filter returns <1), top 2 supplement from dept, master ordered first
    - Handle `dept_only` mode: top 5 from dept, descending similarity
    - Handle empty/whitespace queries: route to dept_only with no filter
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9_

  - [x]* 4.2 Write property tests for query routing (Properties 1, 2, and 3)
    - **Property 1: Keyword routing correctness** — For any query containing a master keyword, SHALL route to `master_index` with correct filename filter per priority order
    - **Property 2: Non-matching queries default to department** — For any query without master keywords (including empty/whitespace), SHALL produce `dept_only` with no filter
    - **Property 3: Master-first retrieval ordering invariant** — For any `master_first` query, master results appear before dept supplement, each group ordered by descending similarity
    - **Validates: Requirements 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9**

- [x] 5. Checkpoint - Ensure core components work
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement enhanced Excel Loader
  - [x] 6.1 Create `app/services/excel_loader.py` with `ExcelLoader` class
    - Implement `load(file_path)` — read `.xlsx`/`.xls` using pandas, return one Document per non-empty sheet
    - Implement `_process_sheet(df, sheet_name, file_path)` — use first non-empty row as headers, convert each row to `KolomA: nilaiA | KolomB: nilaiB` format, omit NaN/empty columns
    - Implement `_format_row(row, columns)` — format single row with pipe separators
    - Join all formatted rows with newline separator for page_content
    - Set metadata: `sheet_name`, `source` (file path), `filename`
    - Skip sheets with only headers and zero non-empty data rows
    - Skip files that cannot be read (corruption/unsupported format) — produce no Documents
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x]* 6.2 Write property tests for Excel Loader (Properties 4 and 5)
    - **Property 4: Excel loader structured row format** — For any valid Excel file with data, Documents SHALL have page_content with `Column: Value | Column: Value` format per row, joined by newlines, with correct metadata
    - **Property 5: Empty sheets produce no Documents** — For any sheet with only header and zero non-empty data rows, no Document SHALL be produced
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**

- [x] 7. Update RAG Chain with Indonesian system prompt
  - [x] 7.1 Update `app/services/langchain/rag_chain.py` with new Indonesian prompt
    - Replace `_RAG_SYSTEM_PROMPT` with the exact Indonesian system prompt template from Requirement 7.1
    - Remove `_LANGUAGE_INSTRUCTIONS` dictionary and `{language_instruction}` placeholder
    - Update `invoke` method: substitute `{context}` with chunks joined by blank lines, `{question}` with query text
    - Send fully substituted template as a single message to LLM (no separate user message)
    - When retriever returns zero documents, substitute `{context}` with empty string (prompt's rule handles the response)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x]* 7.2 Write property test for RAG chain prompt substitution (Property 6)
    - **Property 6: RAG chain prompt substitution** — For any list of document chunks and any query string, the RAG chain SHALL produce a prompt with `{context}` replaced by chunks joined by blank lines and `{question}` replaced by query text
    - **Validates: Requirements 7.3, 7.5**

- [x] 8. Checkpoint - Ensure all new components pass tests
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Update Retrieval Service and API layer
  - [x] 9.1 Update `app/services/retrieval_service.py` to use TurboVecStore and QueryRouter
    - Replace ChromaDB/GraphRAG logic with TurboVecStore + QueryRouter
    - Implement `local_search` — use QueryRouter for intent routing, perform vector similarity search via TurboVecStore
    - Implement `global_search` — use QueryRouter logic (community-based search removed, endpoint remains functional)
    - Implement `combined_search` — merged search using router with token budget
    - Accept existing parameters (top_k, min_score, similarity_weight, num_communities, min_relevance, max_tokens) even if some become no-ops
    - _Requirements: 9.3, 9.4, 9.5, 1.3_

  - [x] 9.2 Ensure all API endpoints preserve their contracts
    - Verify `/api/chat`, `/api/chat/stream`, `/api/search/local`, `/api/search/global`, `/api/search/combined` paths remain registered
    - Verify request schemas (`ChatRequest`, `LocalSearchRequest`, `GlobalSearchRequest`, `CombinedSearchRequest`) and response schemas (`ChatResponse`, `SearchResponse`) are unchanged
    - Verify error response status codes (400, 422, 500, 503, 504) remain for the same conditions
    - Ensure previously existing graph endpoints return 404
    - _Requirements: 9.1, 9.2, 9.5, 9.6, 1.6_

- [x] 10. Update application startup/lifespan
  - [x] 10.1 Update lifespan function to initialize TurboVec indexes
    - Implement TurboVec initialization within `asynccontextmanager`-based lifespan
    - Load from cache if both `.tv` files exist; build from scratch if missing
    - Handle corrupted cache: log warning, discard, rebuild affected index
    - Handle empty knowledge base: create empty indexes, save, log warning
    - All initialization must complete before `yield`
    - Remove all GraphRAG startup logic (entity extraction, community detection, etc.)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 1.4, 5.5_

- [x] 11. Checkpoint - Full integration verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 12. Integration and smoke tests
  - [x]* 12.1 Write integration tests for the full startup and query pipeline
    - Test full startup lifecycle with TurboVec initialization (cache load path and fresh build path)
    - Test end-to-end query flow: router → index → RAG chain → response
    - Test that application starts successfully without graph dependencies installed
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 9.1, 1.2_

  - [x]* 12.2 Write smoke tests to verify removal completeness
    - Verify removed files no longer exist in services directory
    - Verify no imports of removed modules anywhere in codebase
    - Verify `requirements.txt` contains `turbovec[langchain]`, `pandas`; lacks `chromadb`, `spacy`, `networkx`, `leidenalg`, `igraph`
    - Verify all API endpoints still registered and reachable
    - _Requirements: 1.1, 1.2, 2.1, 2.2, 2.3, 12.1, 12.2, 12.3, 12.4, 9.1_

- [x] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis with `@settings(max_examples=100)`
- Unit tests validate specific examples and edge cases
- The design uses Python — all implementations target the existing Python/FastAPI codebase
- The `.hypothesis/` directory already exists in the project, confirming Hypothesis is available

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3"] },
    { "id": 3, "tasks": ["3.1", "4.1", "6.1"] },
    { "id": 4, "tasks": ["3.2", "3.3", "4.2", "6.2"] },
    { "id": 5, "tasks": ["3.4", "7.1"] },
    { "id": 6, "tasks": ["7.2", "9.1"] },
    { "id": 7, "tasks": ["9.2", "10.1"] },
    { "id": 8, "tasks": ["12.1", "12.2"] }
  ]
}
```
