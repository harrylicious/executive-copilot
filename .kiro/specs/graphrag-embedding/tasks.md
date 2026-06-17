# Implementation Plan: GraphRAG Embedding

## Overview

This plan implements the GraphRAG Embedding feature by extending the existing Knowledge Base Manager backend with vector embedding generation, semantic knowledge graph construction, and retrieval endpoints. The implementation follows a bottom-up approach: schema and configuration first, then processing pipeline components, then orchestration, and finally retrieval endpoints with wiring.

## Tasks

- [x] 1. Database schema extensions and configuration
  - [x] 1.1 Create SQLAlchemy models for GraphRAG tables
    - Create `app/models/chunk.py` with the `Chunk` model (id, file_id FK, chunk_index, text, start_offset, end_offset, embedding as JSON)
    - Create `app/models/entity.py` with the `Entity` model (id, name, normalized_name, entity_type, description, source_chunk_ids as JSON)
    - Create `app/models/entity_relationship.py` with the `EntityRelationship` model (id, source_entity_id FK, target_entity_id FK, description, strength, source_chunk_id FK)
    - Create `app/models/community.py` with the `Community` model (id, level, member_entity_ids as JSON, summary, summary_embedding as JSON)
    - Create `app/models/embedding_log.py` with the `EmbeddingLog` model (id, timestamp, files_processed, chunks_generated, errors_count, status)
    - Add `embedding_status` column to existing `File` model in `app/models/file.py`
    - Update `app/models/__init__.py` to export all new models
    - Ensure additive schema creation using `Base.metadata.create_all()` that preserves existing tables
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

  - [x] 1.2 Extend application configuration with GraphRAG settings
    - Add `GraphRAGSettings` class to `app/config.py` using pydantic `BaseSettings` with `KB_` env prefix
    - Implement validators for chunk_size (64-4096), chunk_overlap (0 to chunk_size//2), top_k (1-100), max_context_tokens (256-16384), community_resolution (0.1-10.0), max_community_size (2-10000)
    - Implement validator for entity_extraction_method accepting only "rule-based" or "llm-based"
    - Apply default values when validation fails and log warnings for rejected values
    - Wire `GraphRAGSettings` into the application startup in `app/main.py`
    - _Requirements: 12.1, 12.2, 12.3, 12.5, 12.6_

  - [x] 1.3 Write property test for configuration validation
    - **Property 27: Configuration validation applies defaults for out-of-range values**
    - **Validates: Requirements 12.5**

  - [x] 1.4 Write property test for additive schema creation
    - **Property 26: Additive schema creation preserves existing tables and data**
    - **Validates: Requirements 11.6**

- [x] 2. Text extraction and document chunking
  - [x] 2.1 Implement TextExtractor service
    - Create `app/services/text_extractor.py` with the `TextExtractor` class
    - Implement `_extract_plaintext` for `.txt` files
    - Implement `_extract_markdown` for `.md` files
    - Implement `_extract_json` for `.json` files (pretty-print JSON content as text)
    - Implement `_extract_docx` for `.docx` files using `python-docx`
    - Return `None` for unsupported formats and log a warning with file path and format
    - Handle extraction failures by logging error and returning `None`
    - _Requirements: 1.1, 1.4, 1.6_

  - [x] 2.2 Implement DocumentChunker service
    - Create `app/services/document_chunker.py` with `ChunkResult` dataclass and `DocumentChunker` class
    - Implement token-based chunking using the embedding model's tokenizer
    - Support configurable chunk_size and chunk_overlap parameters
    - Preserve metadata: chunk_index (sequential from 0), start_offset, end_offset
    - Return empty list for empty text, single chunk for text shorter than chunk_size
    - _Requirements: 1.2, 1.3, 1.7, 1.8_

  - [x] 2.3 Write property test for chunking validity
    - **Property 1: Chunking produces valid segments that reconstruct the source text**
    - **Validates: Requirements 1.2, 1.3**

  - [x] 2.4 Write unit tests for TextExtractor
    - Test each supported format with known content
    - Test unsupported format returns None
    - Test extraction failure handling
    - _Requirements: 1.1, 1.4, 1.6_

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Vector embedding generation and storage
  - [x] 4.1 Implement EmbeddingModel wrapper
    - Create `app/services/embedding_model.py` with the `EmbeddingModel` class
    - Initialize with configurable model name (default: "all-MiniLM-L6-v2")
    - Implement `embed_texts` for batch embedding generation
    - Implement `embed_query` for single query embedding
    - Handle model loading failure by logging error and raising on startup
    - _Requirements: 2.1, 2.3, 12.4_

  - [x] 4.2 Implement ChromaVectorStore service
    - Create `app/services/vector_store.py` with the `ChromaVectorStore` class
    - Initialize ChromaDB PersistentClient with configurable path
    - Implement `upsert_chunks` to store embeddings with metadata (file_id, chunk_index, department, chunk text)
    - Implement `delete_by_file` to remove all embeddings for a file_id
    - Implement `similarity_search` with top_k, min_score filtering, and optional metadata filters
    - Handle vector store unavailability by logging error
    - _Requirements: 2.2, 2.6, 2.7, 7.2_

  - [x] 4.3 Write property test for embedding generation
    - **Property 3: Embedding generation produces one vector per chunk with correct metadata**
    - **Validates: Requirements 2.1, 2.2**

  - [x] 4.4 Write property test for document-level embedding
    - **Property 4: Document-level embedding equals the mean of chunk embeddings**
    - **Validates: Requirements 2.5**

- [x] 5. Entity and relationship extraction
  - [x] 5.1 Implement EntityExtractor service
    - Create `app/services/entity_extractor.py` with `ExtractedEntity` dataclass and `EntityExtractor` class
    - Implement rule-based extraction using spaCy NER (`en_core_web_sm`)
    - Map spaCy entity labels to the allowed type set: person, organization, concept, location, event, document
    - Limit extraction to 50 entities per chunk
    - Normalize entity names using case-folding and whitespace trimming
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6_

  - [x] 5.2 Implement RelationshipExtractor service
    - Create `app/services/relationship_extractor.py` with `ExtractedRelationship` dataclass and `RelationshipExtractor` class
    - Extract relationships between all entity pairs co-occurring in the same chunk
    - Generate relationship descriptions and strength scores (0.0-1.0)
    - Limit description to 256 characters
    - _Requirements: 5.1, 5.2, 5.5_

  - [x] 5.3 Write property test for entity extraction invariants
    - **Property 10: Entity extraction invariants**
    - **Validates: Requirements 4.1, 4.2, 4.4**

  - [x] 5.4 Write property test for entity deduplication
    - **Property 11: Entity deduplication by normalized name**
    - **Validates: Requirements 4.3**

  - [x] 5.5 Write property test for relationship constraints
    - **Property 12: Relationships connect co-occurring entities with valid fields**
    - **Validates: Requirements 5.1, 5.2**

- [ ] 6. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. GraphRAG engine and community detection
  - [x] 7.1 Implement GraphRAGEngine service
    - Create `app/services/graphrag_engine.py` with the `GraphRAGEngine` class
    - Implement `extract_entities_and_relationships` to process chunks for a file
    - Implement `_deduplicate_entities` to merge entities with same normalized name and type
    - Implement `_merge_into_file_graph` to add entity nodes and semantic edges without removing manual relationships
    - Implement file re-processing: remove all previously extracted entities and relationships for a file before re-extraction
    - Implement `get_graph_neighborhood` to retrieve entities and relationships within 1 hop of a chunk
    - _Requirements: 4.3, 5.3, 5.4, 7.3_

  - [x] 7.2 Implement CommunityDetector service
    - Create `app/services/community_detector.py` with the `CommunityDetector` class
    - Implement hierarchical community detection using Leiden algorithm via `leidenalg` and `igraph`
    - Build networkx graph from entities and relationships, convert to igraph for Leiden
    - Produce 2-5 hierarchy levels with configurable resolution
    - Skip community detection when fewer than 3 entities exist (log info message)
    - Implement `generate_summary` producing natural language summaries ≤500 tokens per community
    - Generate summary embeddings for global search comparison
    - Remove all previous communities before regeneration
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [x] 7.3 Write property test for graph merge preserving manual relationships
    - **Property 13: Graph merge preserves manual relationships**
    - **Validates: Requirements 5.3**

  - [x] 7.4 Write property test for file re-processing cleanup
    - **Property 14: File re-processing replaces extracted entities and relationships**
    - **Validates: Requirements 5.4**

  - [x] 7.5 Write property test for community hierarchy levels
    - **Property 15: Community hierarchy levels are within bounds**
    - **Validates: Requirements 6.2**

  - [x] 7.6 Write property test for community summary token limit
    - **Property 16: Community summaries are within token limit**
    - **Validates: Requirements 6.4**

  - [x] 7.7 Write property test for community re-detection
    - **Property 17: Community re-detection replaces all previous communities**
    - **Validates: Requirements 6.6**

- [x] 8. Embedding engine orchestration
  - [x] 8.1 Implement EmbeddingEngine orchestrator
    - Create `app/services/embedding_engine.py` with `EmbeddingJobResult` dataclass and `EmbeddingEngine` class
    - Implement `run_incremental` to process files with changed content_hash or no prior embedding
    - Implement `run_full` to re-embed all indexed files regardless of hash
    - Implement `run_single` to embed a specific file by ID
    - Implement `_process_file` pipeline: extract → chunk → embed → store in ChromaDB → store chunks in SQLite → trigger graph extraction
    - Implement `_compute_document_embedding` as element-wise mean of chunk embeddings
    - Handle file-level errors without halting the batch (continue processing remaining files)
    - Handle chunk-level errors without halting the file (continue processing remaining chunks)
    - Log each job in the embedding_log table with timestamp, counts, and status
    - Determine job status: all success → "success", some failures → "partial_success", all failures → "error"
    - _Requirements: 3.1, 3.2, 3.3, 3.5, 3.6, 3.7, 3.8, 2.4, 2.5, 2.6_

  - [x] 8.2 Write property test for incremental job file selection
    - **Property 6: Incremental job processes exactly the files needing embedding**
    - **Validates: Requirements 3.1, 3.8**

  - [x] 8.3 Write property test for job summary accuracy
    - **Property 7: Job summary accurately reflects processing outcomes**
    - **Validates: Requirements 3.5**

  - [x] 8.4 Write property test for partial failure resilience
    - **Property 8: Partial failure does not halt remaining file processing**
    - **Validates: Requirements 3.6**

  - [x] 8.5 Write property test for job logging
    - **Property 9: Every completed job produces exactly one log entry**
    - **Validates: Requirements 3.7**

  - [x] 8.6 Write property test for re-chunking replacement
    - **Property 2: Re-chunking a modified file replaces all previous chunks**
    - **Validates: Requirements 1.5**

  - [x] 8.7 Write property test for re-embedding replacement
    - **Property 5: Re-embedding replaces all previous embeddings for a file**
    - **Validates: Requirements 2.6**

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Retrieval service implementation
  - [ ] 10.1 Implement local search in RetrievalService
    - Create `app/services/retrieval_service.py` with `SearchResult` dataclass and `RetrievalService` class
    - Implement `local_search`: generate query embedding, perform similarity search, enrich with 1-hop graph neighborhood
    - Implement `_compute_combined_score` as weighted sum (similarity_weight × vector_similarity + graph_weight × graph_relevance)
    - Implement `_normalize_graph_relevance` to normalize connection count to 0-1 scale
    - Rank results by combined score in descending order
    - Include source file metadata (name, department, path) with each result
    - Return empty result set when no chunks meet minimum similarity threshold
    - Reject queries that are empty or exceed 1000 characters
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

  - [ ] 10.2 Implement global search in RetrievalService
    - Implement `global_search`: generate query embedding, compare against community summary embeddings
    - Return ranked community summaries with member entities and up to 3 document references per community
    - Support configurable number of communities to return (default 3, max 20)
    - Include relevance score (cosine similarity) for each community
    - Return empty results with metadata when no communities exist or none meet minimum relevance threshold
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ] 10.3 Implement combined search and context assembly
    - Implement `combined_search`: merge local and global results interleaved by descending relevance score
    - Local results take precedence when scores are equal
    - Implement `_truncate_to_token_limit` to enforce max context token limit (1000-16000, default 4000)
    - Truncate by removing lowest-relevance items first
    - Return structured JSON with all required fields: chunks, entities, relationships, community_summaries, source_attributions, metadata
    - Include metadata: query_time_ms, total_chunks_searched, retrieval_mode
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 10.4 Write property test for local search ranking
    - **Property 18: Local search results are ranked by combined score**
    - **Validates: Requirements 7.2, 7.4**

  - [x] 10.5 Write property test for graph neighborhood enrichment
    - **Property 19: Graph neighborhood enrichment includes exactly 1-hop neighbors**
    - **Validates: Requirements 7.3**

  - [x] 10.6 Write property test for global search relevance scores
    - **Property 20: Global search relevance scores are valid cosine similarities**
    - **Validates: Requirements 8.4**

  - [ ] 10.7 Write property test for token limit truncation
    - **Property 21: Combined search respects token limit by truncating lowest-relevance items**
    - **Validates: Requirements 9.3**

  - [ ] 10.8 Write property test for response structure
    - **Property 22: Retrieval response contains all required structural fields**
    - **Validates: Requirements 9.1, 9.4**

  - [ ] 10.9 Write property test for combined search merge ordering
    - **Property 23: Combined search merges results by relevance with correct tie-breaking**
    - **Validates: Requirements 9.2**

- [ ] 11. API endpoints and Pydantic schemas
  - [ ] 11.1 Create Pydantic schemas for embedding and search
    - Create `app/schemas/embedding.py` with `EmbeddingJobRequest`, `EmbeddingJobResponse`, `EmbeddingStatusResponse`
    - Create `app/schemas/search.py` with `LocalSearchRequest`, `GlobalSearchRequest`, `CombinedSearchRequest`, `ChunkResult`, `CommunityResult`, `SearchResponse`
    - Add field validation constraints (min_length, max_length, ge, le) matching requirements
    - _Requirements: 7.6, 9.1_

  - [ ] 11.2 Create embedding API router
    - Create `app/routers/embeddings.py` with FastAPI router
    - Implement `POST /api/embeddings/run` — trigger incremental embedding job
    - Implement `POST /api/embeddings/run/full` — trigger full re-embedding
    - Implement `POST /api/embeddings/run/{file_id}` — trigger single file embedding (return 404 if file not found)
    - Implement `GET /api/embeddings/status` — return embedding status (total embedded, pending, last job timestamp)
    - Return job summary with files_processed, chunks_generated, errors list, and status
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 10.3_

  - [ ] 11.3 Create search API router
    - Create `app/routers/search.py` with FastAPI router
    - Implement `POST /api/search/local` — local search with top_k, min_score, similarity_weight params
    - Implement `POST /api/search/global` — global search with num_communities, min_relevance params
    - Implement `POST /api/search/combined` — combined search with max_tokens param
    - Return structured SearchResponse for all endpoints
    - _Requirements: 7.1, 7.6, 8.1, 8.5, 9.1, 9.4, 9.5_

  - [ ] 11.4 Register new routers in application main
    - Add embedding and search routers to `app/main.py`
    - Ensure GraphRAG schema tables are created on startup (additive, preserving existing tables)
    - Validate embedding model availability on startup and log error if missing
    - _Requirements: 11.6, 12.4, 12.6_

- [ ] 12. Sync integration and embedding status management
  - [ ] 12.1 Integrate embedding status with file sync
    - Modify sync engine to set `embedding_status = "pending"` when new or modified files are detected
    - Implement cleanup on file deletion: remove chunks, embeddings (ChromaDB), entities, relationships for deleted files
    - Handle cleanup failure by setting `embedding_status = "removal_failed"`
    - Update `embedding_status` from "pending" to "embedded" after successful re-embedding
    - Replace document-level embedding on re-embed
    - _Requirements: 10.1, 10.2, 10.4, 10.5, 10.6_

  - [ ] 12.2 Write property test for embedding status transitions
    - **Property 24: Embedding status state transitions are correct**
    - **Validates: Requirements 10.1, 10.5**

  - [ ] 12.3 Write property test for deleted file cleanup
    - **Property 25: Deleted file cleanup removes all associated GraphRAG data**
    - **Validates: Requirements 10.2**

- [ ] 13. Install dependencies and finalize
  - [x] 13.1 Add new dependencies to project
    - Add production dependencies: `sentence-transformers>=2.2.0`, `chromadb>=0.4.0`, `spacy>=3.7.0`, `python-docx>=1.0.0`, `networkx>=3.0`, `leidenalg>=0.10.0`, `igraph>=0.11.0`, `tiktoken>=0.5.0`
    - Update `setup.py` or `pyproject.toml` with new dependencies
    - Add spaCy model download instruction: `python -m spacy download en_core_web_sm`
    - _Requirements: 2.3, 4.1, 6.1_

  - [ ] 13.2 Wire all components together and verify imports
    - Ensure all services are properly imported and instantiated in routers
    - Verify dependency injection of database sessions and config into services
    - Confirm all new models are imported in `app/models/__init__.py`
    - Confirm all new schemas are importable from `app/schemas/`
    - _Requirements: All_

- [ ] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The implementation uses Python with FastAPI, SQLAlchemy, ChromaDB, sentence-transformers, spaCy, and Leiden algorithm as specified in the design
- All configuration uses the `KB_` environment variable prefix with validation and safe defaults

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4", "2.1", "2.2", "13.1"] },
    { "id": 2, "tasks": ["2.3", "2.4", "4.1", "4.2"] },
    { "id": 3, "tasks": ["4.3", "4.4", "5.1", "5.2"] },
    { "id": 4, "tasks": ["5.3", "5.4", "5.5", "7.1", "7.2"] },
    { "id": 5, "tasks": ["7.3", "7.4", "7.5", "7.6", "7.7", "8.1"] },
    { "id": 6, "tasks": ["8.2", "8.3", "8.4", "8.5", "8.6", "8.7"] },
    { "id": 7, "tasks": ["10.1", "10.2", "11.1"] },
    { "id": 8, "tasks": ["10.3", "10.4", "10.5", "10.6"] },
    { "id": 9, "tasks": ["10.7", "10.8", "10.9", "11.2", "11.3"] },
    { "id": 10, "tasks": ["11.4", "12.1"] },
    { "id": 11, "tasks": ["12.2", "12.3", "13.2"] }
  ]
}
```
