# Implementation Plan: Real-Time Embedding Versioning

## Overview

This plan implements the real-time file monitoring, automatic re-embedding, and version management system for the Executive Copilot knowledge base. The implementation is broken into incremental steps that build on the existing FastAPI backend and React frontend, starting with data models and core services, then wiring them together with the WebSocket layer and monitoring dashboard.

## Tasks

- [x] 1. Set up data models and schemas
  - [x] 1.1 Create FileVersion model and AuditLog model
    - Create `backend/app/models/file_version.py` with the `FileVersion` SQLAlchemy model (id, file_id, version_number, content_hash, file_size, timestamp, archive_path, is_restore, restored_from_version) with unique constraint on (file_id, version_number)
    - Create `backend/app/models/audit_log.py` with the `AuditLog` SQLAlchemy model (id, timestamp, event_type, file_id, actor, details)
    - Add `current_version` column to existing `File` model
    - Register new models in `backend/app/models/__init__.py`
    - Add migration logic in `main.py` lifespan for new columns on `files` table
    - _Requirements: 3.1, 3.7, 7.1, 7.4_

  - [x] 1.2 Create Pydantic schemas for monitoring endpoints
    - Create `backend/app/schemas/monitoring.py` with FileStatusResponse, FileVersionResponse, DiffRequest, DiffOperationResponse, DiffResponse, EmbeddingStatusResponse, ActivityEventResponse, RestoreRequest, and WSMessage schemas
    - _Requirements: 6.1, 6.4, 4.1, 4.4_

- [x] 2. Implement Audit Logger service
  - [x] 2.1 Create the AuditLogger service
    - Create `backend/app/services/audit_logger.py` with `AuditLogger` class
    - Implement `AuditEventType` enum (FILE_CREATED, FILE_MODIFIED, FILE_DELETED, EMBEDDING_STARTED, EMBEDDING_COMPLETED, EMBEDDING_FAILED, VERSION_CREATED, VERSION_RESTORED, SYSTEM_ERROR)
    - Implement `log()` method that creates AuditLog records with ISO 8601 UTC timestamps (millisecond precision), event_type, file_id, actor, and details
    - Implement `get_recent_events(limit=50)` method returning most recent records ordered by timestamp descending
    - Fire-and-forget design: catch and log any database write errors to stderr without blocking the caller
    - _Requirements: 7.1, 7.4, 7.5_

  - [ ]* 2.2 Write property test for audit logging comprehensiveness (Property 21)
    - **Property 21: Comprehensive audit logging**
    - Verify that for any system action type, the audit logger creates a record with correct UTC ISO 8601 timestamp (ms precision), correct event_type, and actor identifier
    - **Validates: Requirements 7.1**

- [x] 3. Implement Version Store service
  - [x] 3.1 Create the VersionStoreService
    - Create `backend/app/services/version_store.py` with `VersionStoreService` class
    - Implement `create_version(file_id, file_path, content)` that computes MD5 content hash, compares against latest version, creates FileVersion record only if hash differs, stores content snapshot in archive directory (`{kb_path}/.versions/{file_id}/{version_number}`), assigns monotonically increasing version numbers, and enforces 500 MB file size limit
    - Implement integrity verification: after writing content, re-hash and compare; delete on mismatch
    - Implement `create_restore_version(file_id, file_path, content, restored_from)` for restore records
    - Implement `get_versions(file_id, page, page_size)` returning paginated version history descending
    - Implement `get_version_content(file_id, version_number)` to retrieve archived content
    - Implement `get_latest_version(file_id)` to get current version info
    - Handle disk space errors by rejecting version creation and preserving existing state
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 7.6_

  - [ ]* 3.2 Write property test for version creation conditional on hash difference (Property 10)
    - **Property 10: Version creation IFF content hash differs**
    - Generate random content bytes, verify new version created only when content hash differs from latest
    - **Validates: Requirements 3.2, 3.3, 3.4**

  - [ ]* 3.3 Write property test for content archive round-trip (Property 11)
    - **Property 11: Version content archive round-trip**
    - Generate random binary content, store as version, retrieve and verify byte-for-byte equality
    - **Validates: Requirements 3.6**

  - [ ]* 3.4 Write property test for monotonic version numbering (Property 12)
    - **Property 12: Monotonic version numbering**
    - Generate random sequences of version creations for a file, verify version numbers form strictly increasing sequence starting from 1 with no duplicates
    - **Validates: Requirements 3.7**

  - [ ]* 3.5 Write property test for file size limit enforcement (Property 13)
    - **Property 13: File size limit enforcement**
    - Generate random file sizes around the 500 MB boundary, verify rejection above and acceptance at/below the limit
    - **Validates: Requirements 3.10**

  - [ ]* 3.6 Write property test for content hash integrity verification (Property 23)
    - **Property 23: Content hash integrity verification**
    - Verify that after writing, the version store checks hash and deletes corrupted files when hashes don't match
    - **Validates: Requirements 7.6**

- [x] 4. Implement Diff Engine service
  - [x] 4.1 Create the DiffEngine service
    - Create `backend/app/services/diff_engine.py` with `DiffEngine` class
    - Implement `compute_diff(file_id, version_a, version_b)` using `difflib.unified_diff` to compute line-level differences
    - Parse diff output into structured `DiffOperation` objects (addition, deletion, modification) with line numbers and content
    - Compute `DiffSummary` with counts of additions, deletions, and modifications
    - Handle non-text files by extracting text via existing `TextExtractor` before diffing
    - Return error if either version doesn't exist or text extraction fails
    - Return empty operations list and zero-count summary when versions are identical
    - Enforce 30-second timeout for large file diffs
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 4.2 Write property test for diff round-trip correctness (Property 14)
    - **Property 14: Diff round-trip correctness**
    - Generate pairs of random multiline text strings, compute diff, apply operations to source, verify result equals target
    - **Validates: Requirements 4.1, 4.2, 4.7**

  - [ ]* 4.3 Write property test for diff summary matches operations (Property 15)
    - **Property 15: Diff summary matches operations**
    - Generate pairs of random multiline text strings, compute diff, verify summary counts match operation type counts
    - **Validates: Requirements 4.4**

- [x] 5. Checkpoint - Core services verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement File Watcher service
  - [x] 6.1 Create the FileWatcherService
    - Create `backend/app/services/file_watcher.py` with `FileWatcherService` class
    - Implement `FileEventType` enum and `FileNotification` dataclass
    - Use `watchdog.observers.Observer` with a custom `FileSystemEventHandler` subclass to detect file creation, modification, and deletion events
    - Implement per-file debouncing with 2-second window using `asyncio.Task` dictionary keyed by file path; cancel and restart on new events within window
    - Implement depth filtering to ignore events from paths deeper than 10 levels from KB root
    - Implement subscriber pattern with `subscribe(handler)` for registering async event handlers
    - Implement `start()` method that begins watching and performs initial reconciliation
    - Implement `stop()` method for graceful shutdown
    - Implement `reconcile()` method that compares filesystem state against database and emits notifications for discrepancies
    - Implement exponential backoff reconnection on filesystem errors (1s → 60s max, indefinite retries)
    - Compute MD5 content hash and file size for creation/modification notifications
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ]* 6.2 Write property test for depth filtering correctness (Property 1)
    - **Property 1: Depth filtering correctness**
    - Generate random file paths with 1-15 depth levels, verify inclusion iff depth ≤ 10
    - **Validates: Requirements 1.4**

  - [ ]* 6.3 Write property test for reconciliation correctness (Property 2)
    - **Property 2: Reconciliation correctness**
    - Generate random sets of (path, hash) for filesystem and database states, verify exactly correct notifications emitted for each discrepancy type
    - **Validates: Requirements 1.6**

  - [ ]* 6.4 Write property test for debounce coalescing (Property 3)
    - **Property 3: Debounce coalescing**
    - Generate random sequences of modification events within 2-second windows, verify exactly one notification emitted with latest event's data
    - **Validates: Requirements 1.7**

- [x] 7. Implement Embedding Queue service
  - [x] 7.1 Create the EmbeddingQueueService
    - Create `backend/app/services/embedding_queue.py` with `EmbeddingQueueService` class
    - Implement FIFO queue using `asyncio.Queue` with `asyncio.Semaphore` for configurable concurrency (1-10, default 3)
    - Implement `enqueue(file_id, file_path, content_hash)` that cancels existing jobs for same file before adding new job
    - Implement `cancel_file(file_id)` to cancel queued/processing jobs
    - Implement retry logic with exponential backoff (5s, 15s, 45s) before marking permanently failed
    - Integrate with existing `EmbeddingEngine.run_single()` for actual embedding processing
    - Update file `embedding_status` at each stage: "pending" → "stale" (modified) → "embedding" → "embedded"/"failed"
    - On deletion events, remove all chunks for the file from database
    - Implement `get_queue_status()` returning counts by status
    - Implement `start()` and `stop()` for lifecycle management
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 7.2, 7.5_

  - [ ]* 7.2 Write property test for embedding status state machine (Property 4)
    - **Property 4: Embedding status state machine**
    - Verify that status transitions follow: created → "pending" → "embedding" → "embedded" for successful jobs
    - **Validates: Requirements 2.1, 2.4, 2.5**

  - [ ]* 7.3 Write property test for stale status retains embeddings (Property 5)
    - **Property 5: Stale status retains existing embeddings**
    - Verify that on file-modified, status becomes "stale" and existing chunks remain in database
    - **Validates: Requirements 2.2**

  - [ ]* 7.4 Write property test for deletion removes all chunks (Property 6)
    - **Property 6: Deletion removes all chunks**
    - Verify that processing a file-deleted notification removes all chunk records for that file
    - **Validates: Requirements 2.3**

  - [ ]* 7.5 Write property test for failed embedding retains previous embeddings (Property 7)
    - **Property 7: Failed embedding retains previous embeddings**
    - Verify that on embedding failure, status is "failed" and existing chunks remain unchanged
    - **Validates: Requirements 2.6**

  - [ ]* 7.6 Write property test for FIFO queue ordering (Property 8)
    - **Property 8: FIFO queue ordering**
    - Enqueue random sequences of jobs, verify processing begins in FIFO order (subject to concurrency)
    - **Validates: Requirements 2.7**

  - [ ]* 7.7 Write property test for superseded job cancellation (Property 9)
    - **Property 9: Superseded job cancellation**
    - Verify that enqueueing a new job for an already-queued file cancels the existing job
    - **Validates: Requirements 2.8**

  - [ ]* 7.8 Write property test for error skip and continue (Property 22)
    - **Property 22: Error skip and continue**
    - Verify that when one file fails after all retries, remaining files in batch still complete
    - **Validates: Requirements 7.5**

- [x] 8. Implement Version Restore service
  - [x] 8.1 Create the VersionRestoreService
    - Create `backend/app/services/version_restore.py` with `VersionRestoreService` class
    - Implement `restore_version(file_id, version_number, actor)` that retrieves version content, writes atomically to filesystem (temp file + `os.replace`), creates a new FileVersion record with `is_restore=True` and `restored_from_version`, triggers re-embedding via embedding queue, and logs to audit logger
    - Validate: file exists and is not deleted, version exists
    - On filesystem write failure: clean up temp file, preserve current content, log error
    - Return 404 error if version not found, error if file deleted
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

  - [ ]* 8.2 Write property test for restore content correctness (Property 16)
    - **Property 16: Restore content correctness**
    - Verify that after restore, file content on filesystem equals archived version content byte-for-byte
    - **Validates: Requirements 5.1**

  - [ ]* 8.3 Write property test for restore creates versioned record with indicator (Property 17)
    - **Property 17: Restore creates versioned record with indicator**
    - Verify that restore creates a new FileVersion with is_restore=True and correct restored_from_version
    - **Validates: Requirements 5.3**

- [~] 9. Checkpoint - All backend services verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement WebSocket Manager and real-time endpoint
  - [x] 10.1 Create the WebSocketManager service
    - Create `backend/app/services/websocket_manager.py` with `WebSocketManager` class
    - Implement connection tracking with `connect()` and `disconnect()` methods
    - Implement `broadcast(event)` that sends events to all connected clients and buffers in ring buffer (max 100 events)
    - Assign monotonically increasing event IDs to each event
    - Implement `send_missed_events(websocket, last_event_id)` for reconnection replay (up to 100 events chronologically)
    - Implement initial state snapshot on connect: embedding status counts + last 50 activity events
    - Use ping/pong with 30s timeout for connection health detection
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 10.2 Write property test for WebSocket initial state snapshot (Property 24)
    - **Property 24: WebSocket initial state snapshot**
    - Verify initial state contains correct embedding status counts and at most 50 most recent activity events
    - **Validates: Requirements 8.4**

  - [ ]* 10.3 Write property test for missed events replay on reconnect (Property 25)
    - **Property 25: Missed events replay on reconnect**
    - Verify that on reconnect with last_event_id, all buffered events with greater IDs are sent (up to 100, chronological)
    - **Validates: Requirements 8.6**

- [x] 11. Implement REST API monitoring router
  - [x] 11.1 Create the monitoring router with all endpoints
    - Create `backend/app/routers/monitoring.py` with router prefix `/monitoring`
    - Implement `GET /api/monitoring/files` — paginated file list (25 per page, sorted by modified_at desc) with embedding_status, current_version, file_size
    - Implement `GET /api/monitoring/files/{file_id}/versions` — paginated version history (50 per page, version_number desc)
    - Implement `POST /api/monitoring/files/{file_id}/versions/diff` — compute diff between two versions (DiffRequest body)
    - Implement `POST /api/monitoring/files/{file_id}/versions/{version}/restore` — restore version (RestoreRequest with confirmed=True required)
    - Implement `GET /api/monitoring/embedding-status` — current embedding status counts
    - Implement `GET /api/monitoring/activity` — last 50 activity events
    - Implement WebSocket endpoint at `/ws/embedding-status`
    - Register router in `main.py`
    - _Requirements: 6.1, 6.4, 4.1, 5.1, 6.3, 6.7, 8.1, 7.7_

  - [ ]* 11.2 Write property test for paginated file list correctness (Property 18)
    - **Property 18: Paginated file list correctness**
    - Generate random sets of file records, verify pagination returns at most 25 per page, sorted by modified_at desc, and union of all pages equals full set
    - **Validates: Requirements 6.1**

  - [ ]* 11.3 Write property test for embedding status counts accuracy (Property 19)
    - **Property 19: Embedding status counts accuracy**
    - Generate random distributions of embedding_status values, verify endpoint returns exact counts
    - **Validates: Requirements 6.3**

  - [ ]* 11.4 Write property test for activity feed ordering and limit (Property 20)
    - **Property 20: Activity feed ordering and limit**
    - Generate random audit log records, verify endpoint returns at most 50 records ordered by timestamp desc
    - **Validates: Requirements 6.7**

- [x] 12. Wire backend services together in application lifecycle
  - [x] 12.1 Integrate services into FastAPI lifespan and event flow
    - Update `main.py` lifespan to initialize and start FileWatcherService, EmbeddingQueueService, WebSocketManager, and AuditLogger
    - Wire FileWatcher notifications to: VersionStore (create versions), EmbeddingQueue (trigger embedding), AuditLogger (log events), WebSocketManager (broadcast updates)
    - Wire EmbeddingQueue status changes to: WebSocketManager (broadcast), AuditLogger (log)
    - Wire VersionStore events to: WebSocketManager (broadcast version_created)
    - Ensure graceful shutdown of FileWatcher and EmbeddingQueue on app stop
    - Add `watchdog` to project dependencies in `pyproject.toml`
    - _Requirements: 1.1, 2.1, 2.2, 3.1, 7.1, 8.2, 8.3_

- [x] 13. Checkpoint - Backend integration verification
  - Ensure all tests pass, ask the user if questions arise.

- [x] 14. Implement frontend WebSocket hook and data fetching
  - [x] 14.1 Create WebSocket hook and monitoring data hooks
    - Create `frontend/src/app/components/MonitoringDashboard/hooks/useWebSocket.ts` with auto-reconnect logic (exponential backoff 1s → 30s, max 10 retries), connection state tracking, and message parsing
    - Create `frontend/src/app/components/MonitoringDashboard/hooks/useMonitoringData.ts` for REST API data fetching (file list, versions, embedding status, activity) using axios
    - Create `frontend/src/app/components/MonitoringDashboard/hooks/useVersionDiff.ts` for diff request handling
    - _Requirements: 8.5, 6.1, 6.2, 6.3, 6.4_

- [x] 15. Implement frontend Monitoring Dashboard components
  - [x] 15.1 Create the main MonitoringDashboard page and file status table
    - Create `frontend/src/app/components/MonitoringDashboard/index.tsx` — main page layout with sections for file list, progress bar, activity feed
    - Create `frontend/src/app/components/MonitoringDashboard/FileStatusTable.tsx` — paginated table (25 per page) with columns: file name, department, embedding status (colored badges), version number, last modified; sorted by modified_at desc
    - Create `frontend/src/app/components/MonitoringDashboard/EmbeddingProgressBar.tsx` — summary counts showing pending, embedding, failed, and embedded file counts
    - Create `frontend/src/app/components/MonitoringDashboard/ConnectionIndicator.tsx` — WebSocket connection status indicator
    - Handle loading, error, and empty states per requirements
    - _Requirements: 6.1, 6.2, 6.3, 6.8, 6.9_

  - [x] 15.2 Create version history panel, diff viewer, and restore dialog
    - Create `frontend/src/app/components/MonitoringDashboard/VersionHistoryPanel.tsx` — version list for selected file (50 per page, version_number desc) with checkboxes for diff selection and restore buttons
    - Create `frontend/src/app/components/MonitoringDashboard/DiffViewer.tsx` — unified/side-by-side diff display with additions (green), deletions (red), and modifications (yellow) highlighting
    - Create `frontend/src/app/components/MonitoringDashboard/RestoreDialog.tsx` — confirmation dialog showing file name, version to restore, current version, with confirm and cancel buttons
    - Diff button disabled until exactly two versions selected
    - _Requirements: 6.4, 6.5, 6.6, 7.7_

  - [x] 15.3 Create activity feed component
    - Create `frontend/src/app/components/MonitoringDashboard/ActivityFeed.tsx` — real-time event stream showing last 50 events (event type, file name, timestamp, outcome) ordered by recency
    - Integrate with WebSocket hook for live updates
    - Display manual retry button for permanently failed embedding jobs
    - _Requirements: 6.7, 7.3_

- [x] 16. Integrate monitoring dashboard into frontend routing
  - [x] 16.1 Add route and navigation for monitoring dashboard
    - Add monitoring page route to the React Router configuration
    - Add navigation link/menu item to the application shell for the Monitoring Dashboard
    - Ensure the monitoring page is accessible and renders correctly within the existing app layout
    - _Requirements: 6.1_

- [x] 17. Final checkpoint - Full system verification
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties defined in the design document
- Unit tests validate specific examples and edge cases
- The backend uses Python (FastAPI, SQLAlchemy, pytest + hypothesis)
- The frontend uses React + TypeScript + MUI + Radix UI + TailwindCSS 4
- All 25 correctness properties from the design are covered by property test sub-tasks
- The `watchdog` library must be added to `pyproject.toml` dependencies

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["2.2", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3", "3.4", "3.5", "3.6", "4.1"] },
    { "id": 4, "tasks": ["4.2", "4.3", "6.1"] },
    { "id": 5, "tasks": ["6.2", "6.3", "6.4", "7.1"] },
    { "id": 6, "tasks": ["7.2", "7.3", "7.4", "7.5", "7.6", "7.7", "7.8", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3", "10.1"] },
    { "id": 8, "tasks": ["10.2", "10.3", "11.1"] },
    { "id": 9, "tasks": ["11.2", "11.3", "11.4", "12.1"] },
    { "id": 10, "tasks": ["14.1"] },
    { "id": 11, "tasks": ["15.1", "15.2", "15.3"] },
    { "id": 12, "tasks": ["16.1"] }
  ]
}
```
