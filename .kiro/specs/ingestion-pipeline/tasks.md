# Implementation Plan: Ingestion Pipeline

## Overview

This plan implements a multi-stage data ingestion pipeline for the Executive Copilot Knowledge Base Manager. The pipeline replaces the current simple file upload flow with a structured system including: Upload Gateway, Validation (schema, deduplication, access rules), Preprocessing (OCR, normalization, PII redaction), Chunking (semantic + sliding window), and Embedding/Indexing. Implementation builds incrementally from data models through pipeline stages to frontend dashboard.

## Tasks

- [x] 1. Set up ingestion pipeline project structure and data models
  - [x] 1.1 Create ingestion configuration and data models
    - Add `IngestionSettings` to `app/config.py` with all pipeline configuration fields (max_file_size_mb, staging_path, supported_formats, OCR settings, chunking parameters, etc.)
    - Create `app/models/ingestion_job.py` with `IngestionJob` SQLAlchemy model (id, file_name, file_size, department, subfolder, status, current_stage, error fields, staging_path, content_hash, timestamps, file_id FK)
    - Create `app/models/ingestion_stage_log.py` with `IngestionStageLog` model (job_id FK, stage, status, started_at, completed_at, details JSON)
    - Create `app/models/batch_loader_config.py` with `BatchLoaderConfig` model (id, name, source_path, source_type, cron_expression, department, subfolder, is_active, timestamps)
    - Create `app/models/batch_execution_log.py` with `BatchExecutionLog` model (config_id FK, started_at, completed_at, files_found, files_submitted, files_skipped, errors JSON, status)
    - Create `app/models/pii_redaction_log.py` with `PIIRedactionLog` model (job_id FK, category, original_start, original_end, placeholder, confidence, flagged_for_review)
    - Extend existing `app/models/chunk.py` with `section_path`, `chunking_method`, and `job_id` columns
    - Update `app/models/__init__.py` to export all new models
    - _Requirements: 11.1, 2.1, 2.4, 8.3_

  - [x] 1.2 Create Pydantic schemas for ingestion API
    - Create `app/schemas/ingestion.py` with `UploadRequest`, `UploadResponse`, `BatchUploadResponse`, `IngestionJobResponse`, `StageLogResponse`, `JobListResponse`, `ErrorResponse` schemas
    - Create `app/schemas/batch_loader.py` with `BatchLoaderConfigCreate`, `BatchLoaderConfigResponse`, `BatchExecutionLogResponse` schemas
    - _Requirements: 1.1, 1.6, 1.7, 11.4, 11.6_

  - [x] 1.3 Create database migration for ingestion tables
    - Create staging directory at configured path
    - Add Alembic migration or direct table creation for all new models (ingestion_jobs, ingestion_stage_logs, batch_loader_configs, batch_execution_logs, pii_redaction_logs)
    - Add new columns to existing chunks table
    - _Requirements: 11.1, 11.5_

- [x] 2. Implement validation pipeline
  - [x] 2.1 Implement Schema Validator
    - Create `app/services/ingestion/schema_validator.py` with `SchemaValidator` class
    - Implement `SUPPORTED_FORMATS` set and `MAGIC_BYTES` dictionary for all supported file types (.txt, .md, .json, .docx, .pdf, .csv, .xlsx, .xls, .png, .jpg, .tiff)
    - Implement `validate()` method checking extension support, magic bytes verification, and format-specific structural checks
    - Implement `_check_magic_bytes()`, `_validate_json()`, `_validate_pdf()` helper methods
    - _Requirements: 3.1, 3.2, 3.4, 3.5, 3.6_

  - [ ]* 2.2 Write property test for Schema Validator
    - **Property 7: Schema validation correctness**
    - **Validates: Requirements 3.1, 3.2, 3.4, 3.5**

  - [x] 2.3 Implement Deduplication Engine
    - Create `app/services/ingestion/deduplication.py` with `DeduplicationEngine` class
    - Implement `compute_content_hash()` using MD5 for exact duplicate detection
    - Implement `compute_minhash()` for near-duplicate detection using MinHash signatures
    - Implement `find_near_duplicates()` with configurable similarity threshold (default 0.9)
    - Implement `check_duplicate()` orchestrating exact and near-duplicate checks against the database
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ]* 2.4 Write property tests for Deduplication Engine
    - **Property 8: Exact duplicate detection**
    - **Property 9: Near-duplicate detection**
    - **Property 10: Deduplication confluence**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.6**

  - [x] 2.5 Implement Access Rule Enforcer
    - Create `app/services/ingestion/access_rules.py` with `AccessRuleEnforcer` class
    - Implement `enforce()` method checking department existence, subfolder validity, and confidential access authorization
    - Implement `_validate_department()`, `_validate_subfolder()`, `_check_confidential_access()` helpers
    - Integrate with existing `app/utils/department_config.py` for department/subfolder lookups
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 2.6 Write property tests for Access Rule Enforcer
    - **Property 11: Access rule validation**
    - **Property 12: Sensitivity level annotation**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.5**

- [x] 3. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Implement preprocessing pipeline
  - [x] 4.1 Implement OCR Engine
    - Create `app/services/ingestion/ocr_engine.py` with `OCREngine` class
    - Implement `_needs_ocr()` to detect image-only PDFs and image files
    - Implement `_run_tesseract()` for local OCR with confidence scoring
    - Implement `_run_textract()` stub for AWS Textract integration
    - Implement `extract_text()` orchestrating OCR provider selection and confidence flagging (threshold 0.6)
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7_

  - [ ]* 4.2 Write property test for OCR confidence flagging
    - **Property 13: OCR confidence flagging**
    - **Validates: Requirements 6.6**

  - [x] 4.3 Implement Text Normalizer
    - Create `app/services/ingestion/normalizer.py` with `TextNormalizer` class
    - Implement `_normalize_unicode()` converting to NFC form
    - Implement `_collapse_whitespace()` preserving paragraph boundaries (double newlines)
    - Implement `_remove_control_chars()` keeping only newlines and tabs
    - Implement `_extract_structure()` to produce `StructureMetadata` (headings, sections, page numbers)
    - Implement `normalize()` orchestrating all normalization steps
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 4.4 Write property tests for Text Normalizer
    - **Property 14: Text normalization correctness**
    - **Property 15: Normalization idempotence**
    - **Validates: Requirements 7.2, 7.3, 7.4, 7.6**

  - [x] 4.5 Implement PII Redactor
    - Create `app/services/ingestion/pii_redactor.py` with `PIIRedactor` class
    - Implement `_detect_nik()` for Indonesian NIK numbers (16 digits)
    - Implement `_detect_phone()` for Indonesian phone format
    - Implement `_detect_email()` for email addresses
    - Implement `_detect_names()` for person names
    - Implement `_is_in_code_block()` to skip PII in code blocks (triple backticks or 4+ space indent)
    - Implement `redact()` with confidence-based flagging (threshold 0.7) and category-specific placeholders
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 4.6 Write property tests for PII Redactor
    - **Property 16: PII detection and placeholder replacement**
    - **Property 17: PII redaction offset logging**
    - **Property 18: PII code block exclusion**
    - **Property 19: PII confidence-based flagging**
    - **Property 20: PII and normalization confluence**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6**

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement chunking pipeline
  - [x] 6.1 Implement Semantic Chunker
    - Create `app/services/ingestion/semantic_chunker.py` with `SemanticChunker` class
    - Implement `_identify_boundaries()` detecting headings, section breaks, and topic transitions from `StructureMetadata`
    - Implement `_split_at_boundaries()` splitting text at identified semantic boundaries
    - Implement `_merge_small_sections()` combining sections below minimum token count (256)
    - Implement `chunk()` producing chunks with target size 256-1024 tokens, delegating oversized sections to Sliding Window Chunker
    - Prepend parent section heading to each chunk and record metadata (chunk_index, start_offset, end_offset, section_path, chunking_method)
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 6.2 Write property tests for Semantic Chunker
    - **Property 21: Semantic chunk size bounds with delegation**
    - **Property 22: Chunk heading and metadata completeness**
    - **Property 23: Chunking round-trip**
    - **Validates: Requirements 9.2, 9.3, 9.4, 9.5, 9.6**

  - [x] 6.3 Implement Sliding Window Chunker
    - Create `app/services/ingestion/sliding_window_chunker.py` with `SlidingWindowChunker` class
    - Implement `_find_sentence_boundary()` aligning to sentence endings within 10% tolerance of target split point
    - Implement `_merge_final_chunk()` merging final chunk with previous if below 128 tokens
    - Implement `chunk()` with configurable window_size (default 512) and overlap (default 64)
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 6.4 Write property tests for Sliding Window Chunker
    - **Property 24: Sliding window sentence alignment**
    - **Property 25: Sliding window minimum chunk size**
    - **Property 26: Sliding window completeness**
    - **Validates: Requirements 10.3, 10.4, 10.5**

- [x] 7. Implement pipeline orchestrator and Upload Gateway
  - [x] 7.1 Implement Ingestion Orchestrator
    - Create `app/services/ingestion/orchestrator.py` with `IngestionOrchestrator` class
    - Implement `run_pipeline()` coordinating all stages: validation → preprocessing → chunking → embedding
    - Implement `_run_validation()` calling SchemaValidator, DeduplicationEngine, and AccessRuleEnforcer
    - Implement `_run_preprocessing()` calling OCREngine (if needed), TextNormalizer, and PIIRedactor
    - Implement `_run_chunking()` calling SemanticChunker (which delegates to SlidingWindowChunker as needed)
    - Implement `_run_embedding()` integrating with existing `embedding_engine.py` and `vector_store.py` to store chunks in ChromaDB
    - Update IngestionJob status at each stage transition, record stage logs, and handle errors with proper failure_stage/error_code/error_message
    - _Requirements: 11.2, 11.3_

  - [ ]* 7.2 Write property test for job status transitions
    - **Property 27: Job status transitions and failure recording**
    - **Validates: Requirements 11.2, 11.3**

  - [x] 7.3 Implement Upload Gateway router
    - Create `app/routers/ingestion.py` with FastAPI router
    - Implement `POST /api/ingestion/upload` endpoint: validate file size (≤100MB), validate required metadata (department), create IngestionJob, store file in staging area, dispatch to orchestrator via BackgroundTasks
    - Implement `POST /api/ingestion/upload/batch` endpoint: accept multiple files, create one IngestionJob per file, return all job IDs
    - Implement `GET /api/ingestion/jobs` endpoint: list jobs with filtering by status, department, date range, and pagination
    - Implement `GET /api/ingestion/jobs/{job_id}` endpoint: return full job detail with stage history
    - Register router in `app/main.py`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 11.4, 11.6_

  - [ ]* 7.4 Write property tests for Upload Gateway
    - **Property 1: File size acceptance boundary**
    - **Property 2: Batch upload job count**
    - **Property 3: Missing metadata detection**
    - **Property 28: Job list filtering correctness**
    - **Validates: Requirements 1.2, 1.6, 1.7, 11.6**

- [x] 8. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Implement Batch Loader and Scheduler
  - [x] 9.1 Implement Batch Loader
    - Create `app/services/ingestion/batch_loader.py` with `BatchLoader` class
    - Implement `_scan_local_path()` scanning local filesystem for new/modified files since last execution
    - Implement `_scan_s3_uri()` stub for S3 source scanning
    - Implement `_is_already_ingested()` checking content hash against tracking store to skip unchanged files
    - Implement `execute_scan()` orchestrating scan, filtering, and job submission with execution logging (files_found, files_submitted, files_skipped, errors)
    - _Requirements: 2.2, 2.3, 2.4, 2.5, 2.7_

  - [ ]* 9.2 Write property tests for Batch Loader
    - **Property 4: Batch loader new file detection**
    - **Property 5: Source path format validation**
    - **Property 6: Batch loader skip already-ingested files**
    - **Validates: Requirements 2.2, 2.6, 2.7**

  - [x] 9.3 Implement Batch Scheduler
    - Create `app/services/ingestion/scheduler.py` with `BatchScheduler` class using APScheduler with SQLite job store
    - Implement `start()`, `add_schedule()`, `remove_schedule()`, `get_next_run()` methods
    - Implement `configure()` for validating source path format (local path or S3 URI)
    - _Requirements: 2.1, 2.6_

  - [x] 9.4 Implement Batch Loader API endpoints
    - Add to `app/routers/ingestion.py`: `POST /api/ingestion/batch-configs` (create config), `GET /api/ingestion/batch-configs` (list configs), `PUT /api/ingestion/batch-configs/{id}` (update), `DELETE /api/ingestion/batch-configs/{id}` (deactivate)
    - Add `GET /api/ingestion/batch-configs/{id}/executions` for execution history
    - _Requirements: 2.1, 2.4, 2.5, 2.6_

- [x] 10. Implement Frontend Ingestion Dashboard
  - [x] 10.1 Create ingestion API client and types
    - Create `src/types/ingestion.ts` with TypeScript interfaces for IngestionJob, StageLog, BatchLoaderConfig, BatchExecutionLog
    - Create `src/api/ingestion.ts` with API client functions: uploadFile, uploadBatch, getJobs, getJobDetail, getBatchConfigs, createBatchConfig
    - _Requirements: 12.1, 12.2, 12.3_

  - [x] 10.2 Implement Ingestion Dashboard page
    - Create `src/pages/IngestionDashboard.tsx` with summary cards (active, completed, failed jobs from last 24h)
    - Implement job list table with status filtering, department filtering, and date range selection
    - Implement job detail panel showing full stage history, timing, and error details
    - Add progress indicators showing current pipeline stage for in-progress jobs
    - _Requirements: 12.1, 12.2, 12.3, 12.7_

  - [x] 10.3 Implement File Upload component
    - Create `src/components/ingestion/FileUpload.tsx` with drag-and-drop and file picker support
    - Add department and subfolder selection dropdowns
    - Implement real-time status updates as file progresses through pipeline stages (polling job status)
    - _Requirements: 12.4, 12.5_

  - [x] 10.4 Implement Batch Loader configuration UI
    - Create `src/components/ingestion/BatchLoaderConfig.tsx` displaying batch loader configuration list
    - Show last execution time, next scheduled time, and execution status for each config
    - Add create/edit form for batch loader configurations
    - _Requirements: 12.6_

  - [x] 10.5 Wire ingestion dashboard into app routing
    - Add ingestion dashboard route to `src/App.tsx`
    - Add navigation link to the ingestion dashboard in the app sidebar/nav
    - _Requirements: 12.1_

  - [ ]* 10.6 Write frontend component tests
    - Write Vitest tests for IngestionDashboard, FileUpload, and BatchLoaderConfig components
    - Test rendering, user interactions, and API integration using MSW
    - _Requirements: 12.1, 12.4, 12.6_

- [x] 11. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (28 properties total)
- Unit tests validate specific examples and edge cases
- The pipeline uses Python 3.11+ with FastAPI, SQLAlchemy/SQLite, ChromaDB, and Hypothesis for property-based testing
- Frontend uses React/TypeScript with Vite, Vitest, and Tailwind CSS
- The existing `TextExtractor` and `DocumentChunker` services are extended, not replaced

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3"] },
    { "id": 2, "tasks": ["2.1", "2.3", "2.5", "4.1", "4.3", "4.5"] },
    { "id": 3, "tasks": ["2.2", "2.4", "2.6", "4.2", "4.4", "4.6", "6.1", "6.3"] },
    { "id": 4, "tasks": ["6.2", "6.4"] },
    { "id": 5, "tasks": ["7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "9.1", "9.3"] },
    { "id": 7, "tasks": ["7.4", "9.2", "9.4", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "10.4"] },
    { "id": 9, "tasks": ["10.5", "10.6"] }
  ]
}
```
