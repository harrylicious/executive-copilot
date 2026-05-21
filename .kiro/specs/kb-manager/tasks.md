# Implementation Plan: Knowledge Base Manager

## Overview

Full-stack POC implementation following priority order: backend scaffolding → API endpoints → frontend shell → file viewers → sync toggle → graph view. The backend uses Python FastAPI + SQLAlchemy + SQLite, and the frontend uses React + TypeScript + Vite + Tailwind CSS. Project root is `eaip-layer1/`.

## Tasks

- [x] 1. Backend scaffolding and project setup
  - [x] 1.1 Create backend project structure and dependencies
    - Create `eaip-layer1/backend/` directory with `app/__init__.py`, `app/models/__init__.py`, `app/schemas/__init__.py`, `app/routers/__init__.py`, `app/services/__init__.py`, `app/utils/__init__.py`
    - Create `requirements.txt` with fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, python-multipart
    - Create `pyproject.toml` with project metadata
    - _Requirements: 1.1, 1.2, 12.1, 12.4_

  - [x] 1.2 Implement configuration and database setup
    - Create `app/config.py` with `Settings` class (port, database_url, knowledge_base_path, cors_origins) using pydantic-settings
    - Create `app/database.py` with SQLAlchemy engine, session factory, and Base declarative class
    - _Requirements: 1.2, 1.4, 9.4_

  - [x] 1.3 Implement SQLAlchemy models
    - Create `app/models/file.py` with File model (id, name, path, department, size, tags as JSON, created_at, modified_at, content_hash)
    - Create `app/models/relationship.py` with Relationship model (id, source_file_id, target_file_id, relationship_type, is_manual)
    - Create `app/models/sync_log.py` with SyncLog model (id, timestamp, files_added, files_updated, files_removed, status, summary)
    - _Requirements: 9.1, 9.2, 9.3_

  - [x] 1.4 Implement department configuration and folder initialization
    - Create `app/utils/department_config.py` with DEPARTMENTS dict defining six departments and their subfolders
    - Implement folder creation logic that builds the full directory tree under `knowledge_base/`
    - _Requirements: 2.1, 2.2_

  - [x] 1.5 Implement seed data service
    - Create `app/services/seed_service.py` that generates 2-3 sample files per department in varied formats (txt, md, json)
    - Implement idempotency check: skip seeding if department folders already contain files
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 1.6 Create FastAPI application entry point
    - Create `app/main.py` with FastAPI app instance, CORS middleware, startup event that creates tables, initializes folders, seeds data, and runs initial sync
    - Register all routers with `/api` prefix
    - _Requirements: 1.1, 1.4, 9.4, 10.2_

  - [ ]* 1.7 Write unit tests for seed idempotency
    - **Property 8: Seed idempotency**
    - **Validates: Requirements 10.3**

- [x] 2. Implement Sync Engine and API
  - [x] 2.1 Implement sync engine service
    - Create `app/services/sync_engine.py` with `SyncEngine` class
    - Implement `_scan_filesystem` to walk `knowledge_base/` and collect file metadata with MD5 hashes
    - Implement `execute_sync` with diff logic: detect new files, modified files (hash changed), and deleted files
    - Apply INSERT/UPDATE/DELETE to the files table and log result to sync_log
    - _Requirements: 5.1, 5.2, 5.3, 8.1, 8.2, 8.3_

  - [ ]* 2.2 Write property test for sync database-filesystem consistency
    - **Property 1: Sync database-filesystem consistency**
    - **Validates: Requirements 5.1, 8.1, 8.2, 8.3**

  - [ ]* 2.3 Write property test for sync summary accuracy
    - **Property 2: Sync summary accuracy**
    - **Validates: Requirements 5.4**

  - [ ]* 2.4 Write property test for sync operation logging
    - **Property 3: Sync operation logging**
    - **Validates: Requirements 5.5**

  - [x] 2.5 Implement sync router endpoints
    - Create `app/routers/sync.py` with POST `/api/sync` (trigger sync), GET `/api/sync/status` (index status), GET `/api/sync/logs` (sync history)
    - Create `app/schemas/sync.py` with SyncResultResponse and IndexStatusResponse Pydantic models
    - _Requirements: 5.1, 5.4, 5.5, 8.4_

  - [ ]* 2.6 Write property test for index status accuracy
    - **Property 7: Index status accuracy**
    - **Validates: Requirements 8.4**

- [x] 3. Implement File CRUD and Department API
  - [x] 3.1 Implement file service
    - Create `app/services/file_service.py` with methods: list_files, get_file, get_file_content (stream binary), update_tags, delete_file
    - _Requirements: 1.1, 7.1, 7.2, 7.3_

  - [x] 3.2 Implement file router endpoints
    - Create `app/routers/files.py` with GET `/api/files`, GET `/api/files/{id}`, GET `/api/files/{id}/content`, PUT `/api/files/{id}/tags`, DELETE `/api/files/{id}`
    - Create `app/schemas/file.py` with FileResponse and TagUpdateRequest Pydantic models
    - _Requirements: 1.1, 7.3_

  - [x] 3.3 Implement department router
    - Create `app/routers/departments.py` with GET `/api/departments` returning tree structure with departments, subfolders, and files
    - _Requirements: 2.3_

  - [ ]* 3.4 Write unit tests for file service and department endpoints
    - Test file listing, content serving, tag updates, and department hierarchy
    - _Requirements: 1.1, 2.3, 7.3_

- [x] 4. Implement Relationship Engine and Graph API
  - [x] 4.1 Implement relationship engine service
    - Create `app/services/relationship_engine.py` with auto-generation logic for department and tag relationships
    - Implement manual relationship CRUD with override precedence over auto-generated
    - Implement recalculation triggered on tag updates and sync completion
    - _Requirements: 6.3, 6.4, 7.4_

  - [x] 4.2 Implement graph router endpoints
    - Create `app/routers/graph.py` with GET `/api/graph`, POST `/api/graph/relationships`, PUT `/api/graph/relationships/{id}`, DELETE `/api/graph/relationships/{id}`
    - Create `app/schemas/graph.py` and `app/schemas/relationship.py` with request/response models
    - Implement graph layout algorithm (radial by department)
    - _Requirements: 6.3, 6.4_

  - [ ]* 4.3 Write property test for auto-relationship generation correctness
    - **Property 4: Auto-relationship generation correctness**
    - **Validates: Requirements 6.3, 7.4**

  - [ ]* 4.4 Write property test for manual relationship override precedence
    - **Property 5: Manual relationship override precedence**
    - **Validates: Requirements 6.4**

- [x] 5. Checkpoint - Backend complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Frontend project setup and layout shell
  - [x] 6.1 Initialize frontend project
    - Create `eaip-layer1/frontend/` with Vite + React + TypeScript template
    - Install dependencies: tailwindcss, postcss, autoprefixer, react-router-dom, axios, reactflow, pdfjs-dist, xlsx, mammoth, marked
    - Configure `tailwind.config.ts` with dark theme colors, `vite.config.ts` with API proxy to backend
    - _Requirements: 11.3, 11.4, 12.5_

  - [x] 6.2 Create TypeScript types and API client
    - Create `src/types/index.ts` with all shared interfaces (FileNode, TreeNode, Relationship, GraphData, SyncResult, IndexStatus, ViewMode, SupportedFormat)
    - Create `src/api/client.ts` with axios instance and typed API functions for all endpoints
    - _Requirements: 11.4_

  - [x] 6.3 Implement layout components
    - Create `src/components/Layout/TopNav.tsx` with app branding, sync button, and view toggle (Viewer/Graph)
    - Create `src/components/Layout/ThreePanel.tsx` with three-panel flex layout (~280px left, fluid center, ~300px right)
    - Create `src/App.tsx` wiring layout with state management for selected file and view mode
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 6.4 Implement File Explorer component
    - Create `src/components/FileExplorer/TreeNode.tsx` for recursive tree rendering with expand/collapse
    - Create `src/components/FileExplorer/FileExplorer.tsx` that fetches department tree from API and renders TreeNode hierarchy
    - Create `src/hooks/useFiles.ts` for file data fetching
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 6.5 Implement Metadata Sidebar component
    - Create `src/components/MetadataSidebar/MetadataSidebar.tsx` displaying file info (name, path, department, size, dates)
    - Create `src/components/MetadataSidebar/TagEditor.tsx` with add/remove tag functionality and API persistence
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 7. Implement File Viewers
  - [x] 7.1 Implement format detection and viewer shell
    - Create `src/utils/fileFormat.ts` with `detectFormat` and `isSupported` functions
    - Create `src/components/FileViewer/FileViewer.tsx` with format routing and unsupported format message
    - _Requirements: 4.7, 4.8_

  - [ ]* 7.2 Write property test for unsupported format detection
    - **Property 6: Unsupported format detection**
    - **Validates: Requirements 4.8**

  - [x] 7.3 Implement PDF viewer
    - Create `src/components/FileViewer/PdfViewer.tsx` using pdfjs-dist with page navigation controls
    - _Requirements: 4.1_

  - [x] 7.4 Implement Excel viewer
    - Create `src/components/FileViewer/ExcelViewer.tsx` using SheetJS (xlsx) with sheet tab selection and table rendering
    - _Requirements: 4.2_

  - [x] 7.5 Implement JSON viewer
    - Create `src/components/FileViewer/JsonViewer.tsx` with syntax highlighting and collapsible nodes
    - _Requirements: 4.3_

  - [x] 7.6 Implement DOCX viewer
    - Create `src/components/FileViewer/DocxViewer.tsx` using Mammoth.js to render formatted HTML
    - _Requirements: 4.4_

  - [x] 7.7 Implement Markdown and Plain Text viewers
    - Create `src/components/FileViewer/MarkdownViewer.tsx` using Marked.js for HTML rendering
    - Create `src/components/FileViewer/PlainTextViewer.tsx` with monospace formatting
    - _Requirements: 4.5, 4.6_

- [x] 8. Implement Sync UI
  - [x] 8.1 Implement sync hook and UI integration
    - Create `src/hooks/useSync.ts` with sync trigger, status polling, and result state
    - Wire sync button in TopNav to trigger POST `/api/sync` and display result summary (files added/updated/removed)
    - Show sync status indicator in TopNav (last sync time, loading state)
    - _Requirements: 5.1, 5.4, 11.2_

- [x] 9. Checkpoint - File viewing and sync complete
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement Knowledge Graph UI
  - [x] 10.1 Implement graph data hook
    - Create `src/hooks/useGraph.ts` with graph data fetching and relationship CRUD operations
    - _Requirements: 6.1, 6.2_

  - [x] 10.2 Implement Knowledge Graph component
    - Create `src/components/KnowledgeGraph/GraphNode.tsx` with custom node styling by department
    - Create `src/components/KnowledgeGraph/KnowledgeGraph.tsx` using React Flow with nodes, edges, background, controls, and node click handler
    - Wire view toggle in TopNav to switch between FileViewer and KnowledgeGraph in center panel
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 10.3 Implement manual relationship management
    - Add UI for creating manual relationships (select source/target nodes, choose type)
    - Add delete relationship option on edge click
    - _Requirements: 6.4_

- [x] 11. Final integration and README
  - [x] 11.1 Wire all components together and verify end-to-end flow
    - Ensure file selection in explorer loads viewer and metadata
    - Ensure tag edits trigger relationship recalculation and graph updates
    - Ensure sync refreshes file tree and graph
    - _Requirements: 3.3, 7.3, 7.4_

  - [x] 11.2 Create project README
    - Create `eaip-layer1/README.md` with installation prerequisites, setup commands for backend and frontend, and startup instructions
    - Document the single-repo clone workflow
    - _Requirements: 12.1, 12.2, 12.3_

- [x] 12. Final checkpoint - All features complete
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend is fully functional before frontend work begins (priority order)
- No authentication, cloud services, or vector embeddings required (Requirement 12.3)

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2", "1.4"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["1.5", "1.6"] },
    { "id": 4, "tasks": ["1.7", "2.1"] },
    { "id": 5, "tasks": ["2.2", "2.3", "2.4", "2.5"] },
    { "id": 6, "tasks": ["2.6", "3.1", "3.3"] },
    { "id": 7, "tasks": ["3.2", "3.4"] },
    { "id": 8, "tasks": ["4.1"] },
    { "id": 9, "tasks": ["4.2", "4.3", "4.4"] },
    { "id": 10, "tasks": ["6.1"] },
    { "id": 11, "tasks": ["6.2", "6.3"] },
    { "id": 12, "tasks": ["6.4", "6.5"] },
    { "id": 13, "tasks": ["7.1"] },
    { "id": 14, "tasks": ["7.2", "7.3", "7.4", "7.5", "7.6", "7.7"] },
    { "id": 15, "tasks": ["8.1"] },
    { "id": 16, "tasks": ["10.1"] },
    { "id": 17, "tasks": ["10.2", "10.3"] },
    { "id": 18, "tasks": ["11.1", "11.2"] }
  ]
}
```
