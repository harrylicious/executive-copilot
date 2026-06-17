# Requirements Document

## Introduction

This feature introduces a real-time file ingestion, embedding, and versioning system for the Executive Copilot knowledge base. The system continuously monitors file changes (uploads, modifications, deletions), automatically triggers re-embedding pipelines, maintains a complete version history of files with diff detection, and provides version restore capabilities. A frontend monitoring UI gives operators visibility into file status, version history, embedding progress, and system health. Enterprise-grade safety mechanisms include rollback, error recovery, and audit logging.

## Glossary

- **File_Watcher_Service**: A backend service that monitors the knowledge base filesystem for file creation, modification, and deletion events in real time.
- **Embedding_Pipeline**: The automated process that extracts text from files, chunks the text, generates vector embeddings, and stores them in the database.
- **Version_Store**: A backend service responsible for storing, retrieving, and managing file version history including content snapshots and metadata.
- **Diff_Engine**: A component that computes and presents differences between two versions of a file at the content level.
- **Version_Restore_Service**: A backend service that restores a specific historical version of a file and triggers re-embedding of the restored content.
- **Monitoring_Dashboard**: A frontend UI component that displays real-time file status, version history, embedding progress, and system health metrics.
- **Audit_Logger**: A service that records all system actions (file changes, embedding runs, version restores, errors) with timestamps, actors, and outcomes for compliance and traceability.
- **Embedding_Status**: The current embedding state of a file, one of: "pending", "embedding", "embedded", "failed", "stale".
- **File_Version**: A record representing a specific point-in-time snapshot of a file's content, including content hash, size, timestamp, and stored content reference.
- **Content_Hash**: An MD5 hash of a file's binary content used to detect modifications.

## Requirements

### Requirement 1: Real-Time File Change Detection

**User Story:** As a knowledge base administrator, I want the system to automatically detect when files are added, modified, or deleted, so that the knowledge base stays current without manual intervention.

#### Acceptance Criteria

1. WHEN a new file is created in the knowledge base directory, THE File_Watcher_Service SHALL detect the creation event within 5 seconds and emit a file-created notification containing the file path, file size, Content_Hash, and detection timestamp.
2. WHEN an existing file's content is modified, THE File_Watcher_Service SHALL detect the modification event within 5 seconds and emit a file-modified notification containing the file path, new file size, new Content_Hash, and detection timestamp.
3. WHEN a file is deleted from the knowledge base directory, THE File_Watcher_Service SHALL detect the deletion event within 5 seconds and emit a file-deleted notification containing the file path and detection timestamp.
4. WHILE the File_Watcher_Service is running, THE File_Watcher_Service SHALL monitor all subdirectories of the knowledge base recursively up to a maximum depth of 10 levels.
5. IF the File_Watcher_Service loses connectivity to the filesystem, THEN THE File_Watcher_Service SHALL log an error and attempt reconnection with exponential backoff starting at 1 second, doubling each attempt up to a maximum interval of 60 seconds, and continuing retries indefinitely until connectivity is restored.
6. WHEN the File_Watcher_Service starts, THE File_Watcher_Service SHALL perform a full filesystem reconciliation against the database and emit file-created, file-modified, or file-deleted notifications for each discrepancy detected, completing reconciliation within 60 seconds for up to 10,000 tracked files.
7. WHEN multiple modification events occur on the same file within a 2-second window, THE File_Watcher_Service SHALL coalesce them into a single file-modified notification emitted after the 2-second debounce period elapses.

### Requirement 2: Automatic Embedding Trigger on File Change

**User Story:** As a knowledge base administrator, I want file changes to automatically trigger re-embedding, so that the vector store always reflects the latest file content.

#### Acceptance Criteria

1. WHEN the File_Watcher_Service emits a file-created notification, THE Embedding_Pipeline SHALL update the file's Embedding_Status to "pending" and queue the new file for embedding within 2 seconds.
2. WHEN the File_Watcher_Service emits a file-modified notification, THE Embedding_Pipeline SHALL update the file's Embedding_Status to "stale", retain existing embeddings available for queries, and queue the file for re-embedding within 2 seconds.
3. WHEN the File_Watcher_Service emits a file-deleted notification, THE Embedding_Pipeline SHALL remove all embedding chunks associated with the deleted file from the vector store within 5 seconds.
4. WHILE the Embedding_Pipeline is processing a file, THE Embedding_Pipeline SHALL update the file's Embedding_Status to "embedding".
5. WHEN the Embedding_Pipeline completes processing a file successfully, THE Embedding_Pipeline SHALL update the file's Embedding_Status to "embedded" and remove any previously retained stale embeddings for that file.
6. IF the Embedding_Pipeline encounters an error during processing, THEN THE Embedding_Pipeline SHALL update the file's Embedding_Status to "failed", log the error with file identifier and error details, and retain the previous valid embeddings until a successful re-embedding occurs.
7. THE Embedding_Pipeline SHALL process queued files in FIFO order with a configurable concurrency limit between 1 and 10, defaulting to 3 parallel embedding jobs.
8. IF a file-modified or file-created notification is received for a file that is already queued or currently being embedded, THEN THE Embedding_Pipeline SHALL cancel or discard the in-progress or queued job for that file and enqueue a new embedding job using the latest file content.

### Requirement 3: File Version Detection and Storage

**User Story:** As a knowledge base administrator, I want the system to detect when the same file is re-uploaded with different content and store each version, so that I can track changes over time.

#### Acceptance Criteria

1. WHEN a file creation is detected and no previous File_Version record exists for that file, THE Version_Store SHALL compute the Content_Hash of the file content and create the initial File_Version record with version number 1.
2. WHEN a file modification is detected and a previous File_Version record exists, THE Version_Store SHALL compute the Content_Hash of the new content and compare it against the current version's Content_Hash.
3. WHEN the Content_Hash of a modified file differs from the stored Content_Hash, THE Version_Store SHALL create a new File_Version record containing the version number, Content_Hash, file size in bytes, timestamp in UTC, and a reference to the stored content snapshot.
4. IF the Content_Hash of a modified file is identical to the stored Content_Hash, THEN THE Version_Store SHALL not create a new File_Version record and SHALL discard the duplicate content.
5. THE Version_Store SHALL retain all previous File_Version records for a file indefinitely unless explicitly purged by an administrator.
6. WHEN a new File_Version is created, THE Version_Store SHALL store a complete copy of the file content in the version archive directory.
7. THE Version_Store SHALL assign monotonically increasing version numbers starting from 1 for each file's version history, guaranteeing uniqueness per file even under concurrent modification events.
8. WHEN a file's version history is requested, THE Version_Store SHALL return all File_Version records ordered by version number descending.
9. IF storage of a new version fails due to insufficient disk space, THEN THE Version_Store SHALL log an error with the file identifier, reject the version creation, preserve the existing version as current, and emit an alert notification.
10. IF a file exceeds 500 MB in size, THEN THE Version_Store SHALL reject the version creation and return an error indicating the file size limit has been exceeded.

### Requirement 4: Version Diff Computation

**User Story:** As a knowledge base administrator, I want to view differences between file versions, so that I can understand what changed between uploads.

#### Acceptance Criteria

1. WHEN a diff between two File_Version records of the same file is requested, THE Diff_Engine SHALL compute a line-level difference between the extracted text content of both versions and return the result within 30 seconds.
2. THE Diff_Engine SHALL represent differences as a list of change operations (additions, deletions, modifications) with line numbers and content for each affected line.
3. WHEN a diff is requested for non-plain-text file formats (including Excel, PDF, and Word), THE Diff_Engine SHALL compute the diff on the extracted text representation of each version.
4. THE Diff_Engine SHALL return a summary containing total lines added, total lines deleted, and total lines modified.
5. IF text extraction fails for either version during diff computation, THEN THE Diff_Engine SHALL return an error indicating which version's extraction failed and the reason.
6. IF either of the two requested File_Version records does not exist, THEN THE Diff_Engine SHALL return an error identifying the missing version.
7. WHEN a diff is computed and both versions have identical extracted text content, THE Diff_Engine SHALL return an empty list of change operations and a summary with zero additions, zero deletions, and zero modifications.

### Requirement 5: Version Restore and Re-Embedding

**User Story:** As a knowledge base administrator, I want to restore a specific file version and have it automatically re-embedded, so that I can revert accidental changes.

#### Acceptance Criteria

1. WHEN a version restore is requested for a specific File_Version, THE Version_Restore_Service SHALL replace the current file content with the content from the specified File_Version within 10 seconds.
2. WHEN a version restore completes successfully, THE Version_Restore_Service SHALL trigger the Embedding_Pipeline to re-embed the restored file within 2 seconds of restore completion.
3. WHEN a version restore completes successfully, THE Version_Restore_Service SHALL create a new File_Version record that includes a restore indicator referencing the source version number, to maintain a complete audit trail.
4. IF the specified File_Version does not exist, THEN THE Version_Restore_Service SHALL return an error with status code 404 and a message indicating the requested version identifier and that it was not found.
5. IF the restore operation fails due to filesystem write error, THEN THE Version_Restore_Service SHALL rollback any partial changes, retain the current file content unchanged, and log the error.
6. WHEN a version restore is requested, THE Audit_Logger SHALL record the restore event with the file identifier, source version number, target version number, actor identity, and timestamp.
7. IF the file associated with the requested File_Version has been deleted from the knowledge base, THEN THE Version_Restore_Service SHALL return an error indicating that the target file no longer exists and the restore cannot be completed.

### Requirement 6: Frontend Monitoring Dashboard

**User Story:** As a knowledge base administrator, I want a real-time monitoring dashboard, so that I can observe file processing status, version history, and embedding progress at a glance.

#### Acceptance Criteria

1. THE Monitoring_Dashboard SHALL display a paginated list of all tracked files with their current Embedding_Status, latest version number, and last modified timestamp, showing 25 files per page sorted by last modified timestamp descending.
2. WHEN a file's Embedding_Status changes, THE Monitoring_Dashboard SHALL reflect the updated status within 3 seconds without requiring a page refresh.
3. THE Monitoring_Dashboard SHALL display an embedding progress indicator showing the number of files currently in "pending" status, currently in "embedding" status, and currently in "failed" status, as well as total files in "embedded" status.
4. WHEN a file is selected, THE Monitoring_Dashboard SHALL display the version history for that file including version number, timestamp, Content_Hash, and file size for each version, showing up to 50 versions per page ordered by version number descending.
5. THE Monitoring_Dashboard SHALL allow the user to select exactly two versions from the version history via checkboxes, and provide a button to trigger a diff view between the two selected versions. The diff button SHALL remain disabled until exactly two versions are selected.
6. THE Monitoring_Dashboard SHALL provide a restore button for each historical version that initiates the version restore workflow by displaying a confirmation dialog containing the file name, the version number to be restored, and the current version number, with explicit confirm and cancel actions.
7. THE Monitoring_Dashboard SHALL display a real-time activity feed showing the last 50 system events (file changes, embedding completions, errors, restores) ordered by recency, with each event displaying event type, file name, timestamp, and outcome.
8. IF the Monitoring_Dashboard fails to load file data from the backend, THEN THE Monitoring_Dashboard SHALL display an error message indicating the data could not be retrieved and provide a retry button.
9. IF no tracked files exist, THEN THE Monitoring_Dashboard SHALL display an empty state message indicating that no files are being tracked.

### Requirement 7: Enterprise Safety Mechanisms

**User Story:** As a system administrator, I want robust error recovery and audit logging, so that the system operates reliably and all actions are traceable for compliance.

#### Acceptance Criteria

1. THE Audit_Logger SHALL record every file creation, modification, deletion, embedding job start, embedding job completion, embedding job failure, version creation, and version restore event with a UTC timestamp (ISO 8601 with millisecond precision), event type, and actor identifier (user ID or "system" for automated actions).
2. WHEN an embedding job fails, THE Embedding_Pipeline SHALL retry the job up to 3 times with exponential backoff intervals of 5 seconds, 15 seconds, and 45 seconds before marking the job as permanently failed.
3. IF a permanently failed embedding job exists, THEN THE Monitoring_Dashboard SHALL display the failure with the error message and provide a manual retry button that resets the job's retry count to zero and re-queues the job for processing through the standard retry cycle.
4. THE Audit_Logger SHALL store audit records in a dedicated audit_log database table with retention of at least 90 days.
5. WHEN the File_Watcher_Service, Embedding_Pipeline, or Version_Store encounters an error that cannot be resolved after all configured retry attempts are exhausted, THE Audit_Logger SHALL record the error with the affected file identifier and error details, and the system SHALL skip the affected file and continue processing remaining files without halting.
6. WHEN the Version_Store completes a file write operation, THE Version_Store SHALL compute the Content_Hash of the written file and compare it against the expected hash, and IF the hashes do not match, THEN THE Version_Store SHALL delete the corrupted write, log a corruption warning with the file identifier, and emit an alert notification.
7. WHEN a file restore is requested, THE Version_Restore_Service SHALL require explicit user confirmation through the Monitoring_Dashboard before executing the restore.

### Requirement 8: Real-Time Communication

**User Story:** As a frontend developer, I want a WebSocket-based real-time communication channel, so that the dashboard receives live updates without polling.

#### Acceptance Criteria

1. THE backend SHALL expose a WebSocket endpoint at /ws/embedding-status that streams file status changes, embedding progress updates, and system events to connected clients.
2. WHEN a file's Embedding_Status changes, THE backend SHALL broadcast the status change to all connected WebSocket clients within 1 second.
3. WHEN a new File_Version is created, THE backend SHALL broadcast the version creation event to all connected WebSocket clients within 1 second.
4. WHEN a WebSocket client connects, THE backend SHALL send an initial state snapshot containing current embedding status counts and the last 50 activity events.
5. IF a WebSocket connection drops, THEN THE Monitoring_Dashboard SHALL attempt automatic reconnection with exponential backoff starting at 1 second, doubling on each attempt, up to a maximum interval of 30 seconds and a maximum of 10 retry attempts, and display a connection status indicator to the user.
6. IF a WebSocket client reconnects after a connection drop, THEN THE backend SHALL send any events that occurred during the disconnection period up to a maximum of 100 missed events, ordered chronologically.
