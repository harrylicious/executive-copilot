# Requirements Document

## Introduction

This document specifies requirements for a comprehensive data ingestion pipeline for the Executive Copilot Knowledge Base Manager. The pipeline replaces the current simple file upload flow with a multi-stage system that includes: an Upload Gateway with REST API connectors and scheduled batch loaders, a validation pipeline with schema checks, deduplication, and access rule enforcement, a preprocessing stage with OCR, parsing, normalization, and PII redaction, and an advanced chunking strategy combining semantic chunking with sliding window for long documents.

The pipeline integrates with the existing FastAPI backend (Python 3.11+), SQLAlchemy/SQLite database, ChromaDB vector store, and React/TypeScript frontend.

## Glossary

- **Ingestion_Pipeline**: The end-to-end system that receives, validates, preprocesses, chunks, and indexes documents into the Knowledge Base.
- **Upload_Gateway**: The REST API layer that accepts file uploads and provides connectors for external data sources.
- **Batch_Loader**: A scheduled component that periodically fetches documents from configured external sources (shared drives, cloud storage, APIs).
- **Validation_Pipeline**: The stage that enforces schema compliance, detects duplicates, and verifies department-level access rules before processing.
- **Preprocessor**: The stage that performs OCR on scanned documents, parses various file formats, normalizes text, and redacts PII.
- **Semantic_Chunker**: The chunking component that splits documents based on semantic boundaries (headings, paragraphs, topic shifts) rather than fixed token counts.
- **Sliding_Window_Chunker**: The chunking component that uses overlapping fixed-size windows for very long documents or sections without clear semantic boundaries.
- **PII_Redactor**: The component that detects and masks personally identifiable information (names, phone numbers, ID numbers, email addresses) before storage.
- **Ingestion_Job**: A trackable unit of work representing one document's journey through the pipeline stages.
- **Schema_Validator**: The component that checks incoming documents against expected structural rules per file type.
- **Deduplication_Engine**: The component that detects duplicate or near-duplicate documents using content hashing and similarity comparison.
- **Department_Access_Rule**: A rule that restricts which departments can ingest documents into specific subfolders based on sensitivity levels.
- **OCR_Engine**: The component that extracts text from scanned/image-based documents using Tesseract (local) or AWS Textract (cloud).

## Requirements

### Requirement 1: Upload Gateway REST API

**User Story:** As a knowledge base administrator, I want to upload documents through a REST API with progress tracking, so that I can ingest files programmatically and monitor upload status.

#### Acceptance Criteria

1. WHEN a file is submitted to the upload endpoint, THE Upload_Gateway SHALL accept the file, assign an Ingestion_Job identifier, and return the job identifier within 500ms.
2. WHEN a multipart upload request is received, THE Upload_Gateway SHALL validate that the file size does not exceed 100MB before accepting the file content.
3. WHEN a file exceeds the maximum allowed size, THE Upload_Gateway SHALL reject the request with HTTP 413 status and a descriptive error message.
4. WHEN an upload is accepted, THE Upload_Gateway SHALL store the raw file in a staging area separate from the indexed Knowledge Base.
5. THE Upload_Gateway SHALL support concurrent uploads of at least 10 files simultaneously without degradation.
6. WHEN a batch upload request containing multiple files is received, THE Upload_Gateway SHALL create one Ingestion_Job per file and return all job identifiers in a single response.
7. WHEN an upload request lacks required metadata (department, subfolder), THE Upload_Gateway SHALL reject the request with HTTP 422 status and list the missing fields.

### Requirement 2: Scheduled Batch Loader

**User Story:** As a knowledge base administrator, I want to configure scheduled batch loading from external sources, so that documents from shared drives and cloud storage are automatically ingested on a recurring basis.

#### Acceptance Criteria

1. WHEN a Batch_Loader schedule is configured with a source path and cron expression, THE Batch_Loader SHALL execute at the specified intervals.
2. WHEN the Batch_Loader executes, THE Batch_Loader SHALL scan the configured source path for new or modified files since the last execution.
3. WHEN new files are detected during a batch scan, THE Batch_Loader SHALL submit each file to the Ingestion_Pipeline as an Ingestion_Job with the configured department and subfolder metadata.
4. WHILE a Batch_Loader is executing, THE Batch_Loader SHALL record the scan start time, files found count, files submitted count, and any errors in a batch execution log.
5. IF a configured source path is unreachable during scheduled execution, THEN THE Batch_Loader SHALL log the connectivity error, skip the current execution, and retry at the next scheduled interval.
6. WHEN a Batch_Loader configuration is created, THE Batch_Loader SHALL validate that the source path format is supported (local filesystem path or S3 URI).
7. THE Batch_Loader SHALL track previously ingested files by content hash to avoid resubmitting unchanged files.

### Requirement 3: Schema Validation

**User Story:** As a knowledge base administrator, I want incoming documents validated against expected schemas, so that malformed or corrupted files are rejected before processing.

#### Acceptance Criteria

1. WHEN a file enters the Validation_Pipeline, THE Schema_Validator SHALL verify that the file extension matches a supported format (.txt, .md, .json, .docx, .pdf, .csv, .xlsx, .xls, .png, .jpg, .tiff).
2. WHEN a file has a supported extension, THE Schema_Validator SHALL verify that the file content matches the declared format (magic bytes validation).
3. IF a file fails schema validation, THEN THE Schema_Validator SHALL mark the Ingestion_Job as "validation_failed" with a specific error code and human-readable reason.
4. WHEN a JSON file is submitted, THE Schema_Validator SHALL verify that the content is parseable as valid JSON.
5. WHEN a PDF file is submitted, THE Schema_Validator SHALL verify that the file header contains a valid PDF signature.
6. THE Schema_Validator SHALL complete validation of a single file within 2 seconds for files up to 50MB.

### Requirement 4: Deduplication

**User Story:** As a knowledge base administrator, I want duplicate documents detected and flagged during ingestion, so that the Knowledge Base does not contain redundant content.

#### Acceptance Criteria

1. WHEN a file enters the Validation_Pipeline, THE Deduplication_Engine SHALL compute an MD5 content hash and compare it against all existing file hashes in the database.
2. WHEN an exact duplicate is detected (identical content hash), THE Deduplication_Engine SHALL mark the Ingestion_Job as "duplicate_exact" and reference the existing file identifier.
3. WHEN a near-duplicate is detected (content similarity above 90% measured by MinHash), THE Deduplication_Engine SHALL mark the Ingestion_Job as "duplicate_near" and reference the similar file identifier.
4. WHEN a duplicate is detected, THE Deduplication_Engine SHALL not proceed with further pipeline stages unless the administrator explicitly overrides the duplicate flag.
5. THE Deduplication_Engine SHALL complete hash-based deduplication within 1 second for files up to 50MB.
6. FOR ALL files processed, parsing then hashing then comparing SHALL produce consistent deduplication decisions regardless of processing order (confluence property).

### Requirement 5: Department Access Rule Enforcement

**User Story:** As a knowledge base administrator, I want access rules enforced during ingestion, so that documents are only stored in authorized department subfolders matching their sensitivity level.

#### Acceptance Criteria

1. WHEN a file is submitted with department and subfolder metadata, THE Validation_Pipeline SHALL verify that the department exists in the configured department list.
2. WHEN a file is submitted with a subfolder, THE Validation_Pipeline SHALL verify that the subfolder is valid for the specified department.
3. IF a file targets a subfolder with "Confidential" sensitivity level, THEN THE Validation_Pipeline SHALL verify that the submitting source has explicit authorization for confidential ingestion.
4. IF a file fails access rule validation, THEN THE Validation_Pipeline SHALL mark the Ingestion_Job as "access_denied" with the specific rule that was violated.
5. WHEN a file passes all access rule checks, THE Validation_Pipeline SHALL annotate the Ingestion_Job with the resolved sensitivity level for downstream processing.

### Requirement 6: OCR Processing

**User Story:** As a knowledge base administrator, I want scanned documents processed through OCR, so that text content from image-based PDFs and image files is extractable and searchable.

#### Acceptance Criteria

1. WHEN a PDF file contains no extractable text (image-only pages), THE OCR_Engine SHALL process the document through OCR to extract text content.
2. WHEN an image file (.png, .jpg, .tiff) is submitted, THE OCR_Engine SHALL extract text content from the image.
3. THE OCR_Engine SHALL support Tesseract as the default local OCR provider.
4. WHERE AWS Textract is configured, THE OCR_Engine SHALL use AWS Textract for OCR processing instead of Tesseract.
5. WHEN OCR processing completes, THE OCR_Engine SHALL store the extracted text with a confidence score indicating extraction quality.
6. IF OCR extraction produces a confidence score below 0.6, THEN THE OCR_Engine SHALL flag the Ingestion_Job for manual review.
7. THE OCR_Engine SHALL process a single-page document within 10 seconds using Tesseract.

### Requirement 7: Document Parsing and Normalization

**User Story:** As a knowledge base administrator, I want all document formats parsed and normalized into a consistent text representation, so that downstream chunking and embedding operate on uniform input.

#### Acceptance Criteria

1. WHEN a document enters the Preprocessor, THE Preprocessor SHALL extract text content using format-specific parsers (extending the existing TextExtractor).
2. WHEN text is extracted, THE Preprocessor SHALL normalize Unicode characters to NFC form.
3. WHEN text is extracted, THE Preprocessor SHALL collapse consecutive whitespace into single spaces while preserving paragraph boundaries (double newlines).
4. WHEN text is extracted, THE Preprocessor SHALL remove control characters except newlines and tabs.
5. THE Preprocessor SHALL preserve document structure metadata (headings, sections, page numbers) as annotations alongside the normalized text.
6. FOR ALL supported document formats, parsing then normalizing then printing back SHALL produce stable output (idempotence: normalizing twice produces the same result as normalizing once).

### Requirement 8: PII Redaction

**User Story:** As a knowledge base administrator, I want personally identifiable information automatically redacted before storage, so that sensitive personal data is not persisted in the Knowledge Base.

#### Acceptance Criteria

1. WHEN normalized text is produced, THE PII_Redactor SHALL scan for and mask the following PII categories: Indonesian NIK numbers (16 digits), phone numbers (Indonesian format), email addresses, and person names.
2. WHEN PII is detected, THE PII_Redactor SHALL replace the detected text with a category-specific placeholder (e.g., "[REDACTED_EMAIL]", "[REDACTED_PHONE]", "[REDACTED_NIK]", "[REDACTED_NAME]").
3. THE PII_Redactor SHALL preserve the character offsets of redacted spans in a separate redaction log for audit purposes.
4. THE PII_Redactor SHALL not modify text that matches PII patterns but appears within code blocks or structured data fields.
5. IF PII redaction encounters an ambiguous match (confidence below 0.7), THEN THE PII_Redactor SHALL flag the span for manual review rather than automatically redacting.
6. FOR ALL text inputs, redacting then normalizing SHALL produce the same result as normalizing then redacting (confluence property for PII redaction and normalization ordering).

### Requirement 9: Semantic Chunking

**User Story:** As a knowledge base administrator, I want documents chunked based on semantic boundaries, so that each chunk contains a coherent unit of meaning for better embedding quality.

#### Acceptance Criteria

1. WHEN a normalized document with structure annotations is received, THE Semantic_Chunker SHALL split the document at semantic boundaries (headings, section breaks, topic transitions).
2. THE Semantic_Chunker SHALL produce chunks with a target size between 256 and 1024 tokens, splitting at the nearest semantic boundary.
3. WHEN a semantic section exceeds 1024 tokens, THE Semantic_Chunker SHALL delegate to the Sliding_Window_Chunker for that section.
4. THE Semantic_Chunker SHALL preserve parent section context by prepending the section heading to each chunk within that section.
5. THE Semantic_Chunker SHALL record chunk metadata including: chunk_index, start_offset, end_offset, section_path (hierarchical heading trail), and chunking_method ("semantic" or "sliding_window").
6. FOR ALL documents, the concatenation of all chunk texts (excluding prepended headings) SHALL reconstruct the original normalized document text without loss or duplication (round-trip property).

### Requirement 10: Sliding Window Chunking for Long Sections

**User Story:** As a knowledge base administrator, I want long document sections without clear semantic boundaries chunked using a sliding window approach, so that no content is lost and context is preserved across chunk boundaries.

#### Acceptance Criteria

1. WHEN a text section exceeds 1024 tokens and lacks internal semantic boundaries, THE Sliding_Window_Chunker SHALL split the section into overlapping chunks.
2. THE Sliding_Window_Chunker SHALL use a configurable window size (default 512 tokens) and overlap (default 64 tokens).
3. THE Sliding_Window_Chunker SHALL align chunk boundaries to sentence endings when a sentence boundary exists within 10% of the target split point.
4. THE Sliding_Window_Chunker SHALL produce chunks that each contain at least 128 tokens (minimum chunk size), merging the final chunk with the previous one if it falls below this threshold.
5. FOR ALL text sections processed by the Sliding_Window_Chunker, the union of all chunk token spans SHALL cover every token in the input section without gaps (completeness property).

### Requirement 11: Ingestion Job Tracking and Status

**User Story:** As a knowledge base administrator, I want to track the status of each ingestion job through all pipeline stages, so that I can monitor progress and diagnose failures.

#### Acceptance Criteria

1. WHEN an Ingestion_Job is created, THE Ingestion_Pipeline SHALL assign a status of "queued" and record the creation timestamp.
2. WHEN an Ingestion_Job transitions between pipeline stages, THE Ingestion_Pipeline SHALL update the job status to reflect the current stage ("validating", "preprocessing", "chunking", "embedding", "completed", "failed").
3. WHEN an Ingestion_Job fails at any stage, THE Ingestion_Pipeline SHALL record the failure stage, error code, and error message.
4. WHEN a GET request is made to the job status endpoint with a valid job identifier, THE Ingestion_Pipeline SHALL return the current status, stage history, and any error details.
5. THE Ingestion_Pipeline SHALL retain job history for at least 30 days before automatic cleanup.
6. WHEN a list request is made to the jobs endpoint, THE Ingestion_Pipeline SHALL support filtering by status, department, and date range.

### Requirement 12: Frontend Ingestion Dashboard

**User Story:** As a knowledge base administrator, I want a frontend dashboard showing ingestion pipeline status, so that I can monitor uploads, batch jobs, and processing progress visually.

#### Acceptance Criteria

1. WHEN the ingestion dashboard page loads, THE Frontend SHALL display a summary of active, completed, and failed Ingestion_Jobs from the last 24 hours.
2. WHEN an Ingestion_Job is in progress, THE Frontend SHALL display a progress indicator showing the current pipeline stage.
3. WHEN the user clicks on an Ingestion_Job, THE Frontend SHALL display the full stage history, timing, and any error details.
4. THE Frontend SHALL provide a file upload form that accepts drag-and-drop and file picker input with department and subfolder selection.
5. WHEN a file is uploaded through the Frontend, THE Frontend SHALL display real-time status updates as the file progresses through pipeline stages.
6. THE Frontend SHALL display the Batch_Loader configuration list with last execution time, next scheduled time, and execution status.
7. WHEN a validation or processing error occurs, THE Frontend SHALL display the error with actionable guidance for resolution.
