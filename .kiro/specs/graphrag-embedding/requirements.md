# Requirements Document

## Introduction

The GraphRAG Embedding feature extends the existing Knowledge Base Manager backend with vector embedding generation and Graph-based Retrieval Augmented Generation (GraphRAG) capabilities. This layer transforms indexed document content and the existing file relationship graph into vector embeddings, builds a semantic knowledge graph enriched with entity and community structures, and exposes retrieval endpoints that a downstream chatbot can consume. The system leverages the existing SQLAlchemy/SQLite metadata store, the file relationship graph, and the sync engine to trigger embedding pipelines on demand.

## Glossary

- **Embedding_Engine**: The backend service responsible for converting document text into vector representations using a configured embedding model
- **Vector_Store**: The persistent storage layer for document embeddings and their associated metadata, using a local vector database
- **Chunk**: A segment of document text produced by splitting a file's content according to a chunking strategy (fixed-size with overlap or semantic boundaries)
- **GraphRAG_Engine**: The service that builds and queries a semantic knowledge graph by extracting entities and relationships from document chunks, organizing them into communities, and generating community summaries
- **Entity**: A named concept, person, organization, topic, or object extracted from document text via NLP or LLM-based extraction
- **Community**: A cluster of densely connected entities within the knowledge graph, detected via graph community algorithms
- **Community_Summary**: A natural language summary describing the theme and key relationships within a community, used for global search
- **Local_Search**: A retrieval mode that finds relevant chunks and their graph neighborhood for a specific, focused query
- **Global_Search**: A retrieval mode that uses community summaries to answer broad, thematic queries across the entire knowledge base
- **Embedding_Model**: The machine learning model used to generate vector representations of text (e.g., sentence-transformers or OpenAI embedding models)
- **Retrieval_Endpoint**: An API endpoint that accepts a natural language query and returns ranked relevant context from the vector store and knowledge graph
- **Embedding_Job**: A background-triggered processing task that generates or updates embeddings for a set of files
- **Chunk_Overlap**: The number of tokens or characters shared between consecutive chunks to preserve context across boundaries

## Requirements

### Requirement 1: Document Chunking

**User Story:** As a developer, I want documents to be split into manageable chunks, so that embeddings capture focused semantic meaning and retrieval returns precise context.

#### Acceptance Criteria

1. WHEN an embedding job is triggered for a file, THE Embedding_Engine SHALL extract text content from the file based on its format (plain text, Markdown, JSON, DOCX)
2. THE Embedding_Engine SHALL split extracted text into chunks using a configurable chunking strategy with default parameters of 512 tokens per chunk and 50 tokens of overlap, where token boundaries are determined by the configured Embedding_Model tokenizer
3. THE Embedding_Engine SHALL preserve metadata for each chunk including source file ID, chunk index, start character offset, and end character offset relative to the extracted text
4. IF a file format is not supported for text extraction, THEN THE Embedding_Engine SHALL skip the file and log a warning with the file path and format
5. WHEN a file has been previously chunked and its content_hash has changed, THE Embedding_Engine SHALL delete existing chunks and re-chunk the file
6. IF text extraction fails for a supported file format, THEN THE Embedding_Engine SHALL skip the file, log an error with the file path and failure reason, and continue processing remaining files
7. IF the extracted text for a file contains fewer tokens than the configured chunk size, THEN THE Embedding_Engine SHALL produce a single chunk containing the entire extracted text
8. IF the extracted text for a file is empty after processing, THEN THE Embedding_Engine SHALL produce zero chunks for that file and log an informational message with the file path

### Requirement 2: Vector Embedding Generation

**User Story:** As a developer, I want text chunks converted into vector embeddings, so that semantic similarity search is possible across the knowledge base.

#### Acceptance Criteria

1. WHEN chunks are produced for a file, THE Embedding_Engine SHALL generate a vector embedding for each chunk using the configured Embedding_Model
2. THE Embedding_Engine SHALL store each embedding in the Vector_Store with associated metadata including source file ID, chunk index, chunk text, and department
3. THE Embedding_Engine SHALL support configurable embedding model selection via application settings with a default of the sentence-transformers all-MiniLM-L6-v2 model
4. IF the Embedding_Model fails to generate an embedding for a chunk, THEN THE Embedding_Engine SHALL log the error including the source file ID and chunk index, skip the failed chunk, and continue processing remaining chunks
5. THE Embedding_Engine SHALL generate a single document-level embedding per file by averaging its chunk embeddings for use in graph-level operations
6. WHEN a previously indexed file is re-processed, THE Embedding_Engine SHALL delete all existing embeddings for that file from the Vector_Store before storing the newly generated embeddings
7. IF the Vector_Store is unavailable when the Embedding_Engine attempts to store embeddings, THEN THE Embedding_Engine SHALL log the error and report the file as failed without discarding the generated embeddings from memory until the operation is retried or abandoned

### Requirement 3: Embedding Job Orchestration

**User Story:** As a user, I want to trigger embedding generation on demand, so that I control when processing resources are consumed.

#### Acceptance Criteria

1. WHEN a user triggers the embedding job via the API, THE Embedding_Engine SHALL process all files whose content_hash has changed since their last successful embedding generation or that have no prior embedding record
2. THE Backend_API SHALL expose an endpoint to trigger a full re-embedding of all indexed files, ignoring content_hash comparison and regenerating embeddings for every file in the index
3. THE Backend_API SHALL expose an endpoint to trigger embedding for a specific file by its database ID
4. IF the specified file ID does not exist in the index, THEN THE Backend_API SHALL return an error response indicating the file was not found
5. WHEN an embedding job completes, THE Backend_API SHALL return a summary indicating the count of files processed, the count of chunks generated, and a list of per-file errors for any files that failed during processing
6. IF one or more files fail during an embedding job, THEN THE Embedding_Engine SHALL continue processing the remaining files and THE Backend_API SHALL record the job status as "partial_success"
7. THE Backend_API SHALL log each embedding job in an embedding_log table with timestamp, files processed count, chunks generated count, and status where status is one of "success", "partial_success", or "error"
8. THE Embedding_Engine SHALL skip files whose content_hash has not changed since the last successful embedding, unless the job was triggered via the full re-embedding endpoint

### Requirement 4: Entity Extraction

**User Story:** As a developer, I want entities automatically extracted from document chunks, so that the knowledge graph captures the semantic concepts within the knowledge base.

#### Acceptance Criteria

1. WHEN chunks are embedded for a file, THE GraphRAG_Engine SHALL extract up to 50 entities per chunk using a configured extraction method
2. THE GraphRAG_Engine SHALL categorize each extracted entity with exactly one type label from the set: person, organization, concept, location, event, document
3. THE GraphRAG_Engine SHALL deduplicate entities by normalizing names using case-folding and whitespace trimming, and merging entities that share the same normalized name and type into a single entity record
4. THE GraphRAG_Engine SHALL store extracted entities in an entities table with name (maximum 256 characters), type, description (maximum 1024 characters), and source chunk references linking each entity to all chunks from which it was extracted
5. IF no entities are extracted from a chunk, THEN THE GraphRAG_Engine SHALL proceed without error and continue processing subsequent chunks
6. IF entity extraction fails for a chunk due to a processing error, THEN THE GraphRAG_Engine SHALL log the failure with the chunk identifier and continue processing remaining chunks without halting the overall extraction

### Requirement 5: Semantic Relationship Extraction

**User Story:** As a developer, I want relationships between entities extracted automatically, so that the knowledge graph captures how concepts relate to each other.

#### Acceptance Criteria

1. WHEN entities are extracted from a chunk, THE GraphRAG_Engine SHALL identify and extract relationships between all entity pairs present within the same chunk
2. THE GraphRAG_Engine SHALL store each extracted relationship with source entity, target entity, a relationship description of no more than 256 characters, and a strength score ranging from 0.0 to 1.0 inclusive
3. WHEN entity-relationship extraction is complete for a file, THE GraphRAG_Engine SHALL merge the extracted entity-relationship graph into the existing file-level relationship graph by adding entity nodes and semantic edges without removing or overwriting manually created relationships from the Relationship Engine
4. WHEN a file is re-processed, THE GraphRAG_Engine SHALL remove all previously extracted entities and relationships associated with that file before performing re-extraction
5. IF entity or relationship extraction fails for a chunk, THEN THE GraphRAG_Engine SHALL skip that chunk, continue processing remaining chunks in the file, and log the failure with the chunk identifier and error reason

### Requirement 6: Community Detection

**User Story:** As a developer, I want entities grouped into communities, so that global search can reason over thematic clusters rather than individual documents.

#### Acceptance Criteria

1. WHEN the entity graph is updated after entity and relationship extraction completes for a file, THE GraphRAG_Engine SHALL run a community detection algorithm to identify clusters of connected entities
2. THE GraphRAG_Engine SHALL support hierarchical community detection producing at least 2 and at most 5 levels of granularity, where level 1 represents the coarsest grouping and higher levels represent progressively finer sub-communities
3. THE GraphRAG_Engine SHALL store community assignments in a communities table with community ID, level, member entity IDs, and a generated summary
4. WHEN communities are detected, THE GraphRAG_Engine SHALL generate a natural language Community_Summary of no more than 500 tokens for each community describing its theme and the top 5 relationships by strength score among its member entities
5. IF the entity graph contains fewer than three entities, THEN THE GraphRAG_Engine SHALL skip community detection and log an informational message
6. WHEN community detection is re-run after a graph update, THE GraphRAG_Engine SHALL remove all previously stored communities and regenerate them from the current entity graph
7. IF Community_Summary generation fails for a community, THEN THE GraphRAG_Engine SHALL store the community with an empty summary, log the error, and continue processing remaining communities

### Requirement 7: Local Search Retrieval

**User Story:** As a chatbot backend, I want to retrieve focused context for specific queries, so that answers are grounded in relevant document passages and their graph neighborhood.

#### Acceptance Criteria

1. WHEN a local search query is received with a query text between 1 and 1000 characters, THE Retrieval_Endpoint SHALL generate an embedding for the query text using the same Embedding_Model that was used during chunk indexing
2. WHEN a local search query is received, THE Retrieval_Endpoint SHALL perform a similarity search against the Vector_Store and return the top-k most similar chunks, where k is a configurable parameter between 1 and 50 defaulting to 5, including only chunks with a similarity score at or above a configurable minimum threshold defaulting to 0.5 on a 0-to-1 scale
3. WHEN chunks are retrieved from the Vector_Store, THE Retrieval_Endpoint SHALL enrich each retrieved chunk with its graph neighborhood up to 1 hop, including related entities, connected files, and relationship types
4. THE Retrieval_Endpoint SHALL return results ranked by a combined score computed as a weighted sum of vector similarity and graph relevance, with a configurable similarity weight defaulting to 0.7 and graph relevance weight defaulting to 0.3, where graph relevance is defined as the count of graph connections for the chunk normalized to a 0-to-1 scale
5. THE Retrieval_Endpoint SHALL include source file metadata (name, department, path) with each result for attribution
6. IF the query text is empty or exceeds 1000 characters, THEN THE Retrieval_Endpoint SHALL reject the request with an error message indicating the query length constraint
7. IF no chunks meet the minimum similarity threshold, THEN THE Retrieval_Endpoint SHALL return an empty result set with a count of zero

### Requirement 8: Global Search Retrieval

**User Story:** As a chatbot backend, I want to answer broad thematic queries using community summaries, so that responses capture knowledge base-wide patterns and themes.

#### Acceptance Criteria

1. WHEN a global search query is received, THE Retrieval_Endpoint SHALL generate an embedding for the query text using the configured Embedding_Model and perform a similarity comparison against all stored Community_Summary embeddings to identify relevant communities
2. WHEN global search results are returned, THE Retrieval_Endpoint SHALL return ranked community summaries with their member entities and up to 3 document references per community selected by highest entity co-occurrence count within that community
3. THE Retrieval_Endpoint SHALL support a configurable number of communities to return with a default of 3 and a maximum of 20
4. WHEN global search results are returned, THE Retrieval_Endpoint SHALL include a relevance score between 0.0 and 1.0 for each returned community based on cosine similarity between the query embedding and the community summary embedding
5. IF no communities exist in the knowledge graph when a global search query is received, THEN THE Retrieval_Endpoint SHALL return an empty results list with a metadata field indicating that community detection has not been performed
6. IF no community scores meet or exceed a configurable minimum relevance threshold defaulting to 0.1, THEN THE Retrieval_Endpoint SHALL return an empty results list

### Requirement 9: Graph-Enhanced Context Assembly

**User Story:** As a chatbot backend, I want retrieved context assembled into a structured format, so that the downstream LLM receives well-organized grounding information.

#### Acceptance Criteria

1. THE Retrieval_Endpoint SHALL return context in a structured JSON format containing the following top-level fields: chunks (list of text segments with relevance scores), entities (list of extracted entities with types), relationships (list of entity pairs with relationship labels), community_summaries (list of topic cluster summaries), and source_attributions (list of source document references with file identifiers)
2. WHEN both local and global search results are available, THE Retrieval_Endpoint SHALL support a combined search mode that merges results by interleaving local chunk results and global community context in descending order of relevance score, with local results taking precedence when scores are equal
3. THE Retrieval_Endpoint SHALL enforce a configurable maximum context token limit between 1000 and 16000 tokens with a default of 4000 tokens, truncating results with the lowest relevance scores first when the assembled context exceeds the limit
4. THE Retrieval_Endpoint SHALL include a metadata section with query processing time in milliseconds, total chunks searched, and retrieval mode used (local, global, or combined)
5. IF the retrieval operation returns no matching chunks or entities, THEN THE Retrieval_Endpoint SHALL return the standard JSON structure with empty lists for chunks, entities, relationships, and community_summaries, and include a metadata field indicating zero results found

### Requirement 10: Embedding Sync Integration

**User Story:** As a user, I want embeddings to stay current with the knowledge base, so that retrieval results reflect the latest document state.

#### Acceptance Criteria

1. WHEN a file sync operation detects new or modified files, THE Backend_API SHALL mark those files as requiring re-embedding by setting an embedding status of "pending" in the file metadata
2. WHEN a file sync operation detects deleted files, THE Embedding_Engine SHALL remove the corresponding embeddings, chunks, entities, and relationships from the Vector_Store and graph
3. THE Backend_API SHALL expose an endpoint to retrieve embedding status for the knowledge base including total files embedded, files pending embedding, and last embedding job timestamp
4. WHEN a file is re-embedded, THE Embedding_Engine SHALL replace the existing document-level embedding used in graph operations with the newly generated embedding
5. WHEN a file is successfully re-embedded, THE Backend_API SHALL update the file's embedding status from "pending" to "embedded" in the file metadata
6. IF the Embedding_Engine fails to remove embeddings for a deleted file, THEN THE Backend_API SHALL retain the file's deletion record with an embedding status of "removal_failed" and include it in the pending count returned by the embedding status endpoint

### Requirement 11: Database Schema Extensions

**User Story:** As a developer, I want well-defined database tables for embeddings and graph entities, so that the GraphRAG data is stored consistently alongside existing metadata.

#### Acceptance Criteria

1. THE Backend_API SHALL create a chunks table storing chunk ID (integer primary key), file ID (foreign key referencing files.id), chunk index (integer starting at 0), text content (string up to 10,000 characters), start position (integer character offset from beginning of file), end position (integer character offset from beginning of file), and embedding vector stored as a JSON-serialized array of floats
2. THE Backend_API SHALL create an entities table storing entity ID (integer primary key), name (string up to 512 characters), normalized name (lowercase trimmed string up to 512 characters), type (string up to 128 characters), description (string up to 2,000 characters), and source chunk IDs stored as a JSON array of chunk ID integers
3. THE Backend_API SHALL create an entity_relationships table storing relationship ID (integer primary key), source entity ID (foreign key referencing entities.id), target entity ID (foreign key referencing entities.id), description (string up to 2,000 characters), strength score (float between 0.0 and 1.0 inclusive), and source chunk ID (foreign key referencing chunks.id)
4. THE Backend_API SHALL create a communities table storing community ID (integer primary key), level (integer representing hierarchy depth starting at 0), member entity IDs stored as a JSON array of entity ID integers, and summary text (string up to 5,000 characters)
5. THE Backend_API SHALL create an embedding_log table storing job ID (integer primary key), timestamp (datetime), files processed (integer), chunks generated (integer), errors count (integer), and status (string with allowed values "pending", "running", "completed", or "failed")
6. WHEN the application starts, THE Backend_API SHALL create all GraphRAG schema tables using an additive approach that preserves existing tables and their data, and SHALL NOT alter or drop the existing files, relationships, or sync_log tables

### Requirement 12: Configuration and Model Management

**User Story:** As a developer, I want embedding and GraphRAG parameters configurable via environment variables, so that the system can be tuned without code changes.

#### Acceptance Criteria

1. THE Backend_API SHALL support configuration of the following parameters via environment variables with the KB_ prefix, applying the specified defaults when no environment variable is set: embedding model name (default: "all-MiniLM-L6-v2"), chunk size in tokens (default: 512, valid range: 64 to 4096), chunk overlap in tokens (default: 50, valid range: 0 to half of chunk size), top-k retrieval count (default: 5, valid range: 1 to 100), and maximum context tokens (default: 2048, valid range: 256 to 16384)
2. THE Backend_API SHALL support configuration of entity extraction method via an environment variable with the KB_ prefix, accepting only the values "rule-based" or "llm-based", defaulting to "rule-based" when not set
3. THE Backend_API SHALL support configuration of community detection resolution (default: 1.0, valid range: 0.1 to 10.0) and maximum community size (default: 100, valid range: 2 to 10000) via environment variables with the KB_ prefix
4. IF a configured embedding model is not available locally, THEN THE Backend_API SHALL log an error message identifying the missing model on startup and return an error response with a message indicating the model is unavailable for all embedding endpoint requests until the application is restarted with a valid model name
5. IF any KB_-prefixed configuration environment variable contains a value outside its valid range or of an invalid type, THEN THE Backend_API SHALL reject the value, log a warning identifying the variable and the invalid value, and apply the default value for that parameter
6. THE Backend_API SHALL read and apply all KB_-prefixed configuration values at application startup, requiring a restart for configuration changes to take effect
