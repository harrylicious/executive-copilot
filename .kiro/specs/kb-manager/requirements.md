# Requirements Document

## Introduction

The Knowledge Base Manager (KB Manager) is a full-stack proof-of-concept application for organizing, viewing, and exploring departmental documents. It provides a file system explorer with tree navigation, multi-format file viewing, on-demand synchronization, metadata tagging, and a knowledge graph visualization. The system uses a Python FastAPI backend with SQLite for metadata storage and local filesystem for file storage, paired with a React/TypeScript/Vite frontend styled with Tailwind CSS in a dark enterprise theme.

## Glossary

- **KB_Manager**: The full-stack application comprising the Backend API and the Frontend UI
- **Backend_API**: The Python FastAPI server responsible for file management, metadata storage, sync operations, and graph data
- **Frontend_UI**: The React/TypeScript/Vite single-page application providing the user interface
- **File_Explorer**: The left-panel tree view component displaying the departmental folder hierarchy
- **File_Viewer**: The center panel component rendering file content in supported formats (PDF, Excel, JSON, DOCX, Markdown, plain text)
- **Metadata_Sidebar**: The right-panel component displaying and editing file metadata and tags
- **Knowledge_Graph**: The React Flow-based visualization showing relationships between files across departments
- **Sync_Engine**: The backend module that scans the local filesystem and updates the SQLite database on demand
- **Department**: A top-level organizational unit (Finance, Retail/Operations, HR, Supply Chain, Executive, IT/Audit)
- **Subfolder_Structure**: The predefined directory hierarchy within each department
- **Relationship**: A connection between two files in the knowledge graph, either auto-generated or manually created
- **Tag**: A user-defined label attached to a file for categorization and graph relationship generation
- **Seed_Data**: The initial set of 2-3 sample files per department loaded on first startup

## Requirements

### Requirement 1: Backend API Server

**User Story:** As a developer, I want a FastAPI backend server that exposes RESTful endpoints, so that the frontend can manage files, metadata, sync, and graph data.

#### Acceptance Criteria

1. THE Backend_API SHALL expose RESTful endpoints for file CRUD operations, sync triggers, department listing, graph data retrieval, and content serving
2. THE Backend_API SHALL use SQLAlchemy with SQLite as the metadata storage engine
3. THE Backend_API SHALL use the local filesystem for document file storage
4. THE Backend_API SHALL serve content on a configurable port with CORS enabled for local frontend development

### Requirement 2: Department Structure

**User Story:** As a user, I want predefined departmental folders with subfolder structures, so that documents are organized by business unit.

#### Acceptance Criteria

1. THE Backend_API SHALL provide six top-level departments: Finance, Retail/Operations, HR, Supply Chain, Executive, and IT/Audit
2. THE Backend_API SHALL create predefined subfolder structures within each department on initialization
3. WHEN the department listing endpoint is called, THE Backend_API SHALL return all departments with their subfolder hierarchies

### Requirement 3: File System Explorer

**User Story:** As a user, I want a tree view of the departmental file structure, so that I can navigate and select documents.

#### Acceptance Criteria

1. THE Frontend_UI SHALL render the File_Explorer as a collapsible tree view in the left panel with an approximate width of 280 pixels
2. THE File_Explorer SHALL display departments as root nodes with subfolders and files as nested children
3. WHEN a user selects a file in the File_Explorer, THE Frontend_UI SHALL load the file content in the File_Viewer and display metadata in the Metadata_Sidebar
4. WHEN a user expands or collapses a folder node, THE File_Explorer SHALL toggle visibility of child nodes

### Requirement 4: Multi-Format File Viewer

**User Story:** As a user, I want to view documents in multiple formats without leaving the application, so that I can review content in context.

#### Acceptance Criteria

1. THE File_Viewer SHALL render PDF files with page navigation controls
2. THE File_Viewer SHALL render Excel files as tabular data with sheet selection
3. THE File_Viewer SHALL render JSON files with syntax highlighting and collapsible nodes
4. THE File_Viewer SHALL render DOCX files as formatted text content
5. THE File_Viewer SHALL render Markdown files as formatted HTML
6. THE File_Viewer SHALL render plain text files with monospace formatting
7. THE File_Viewer SHALL occupy the center panel of the layout between the File_Explorer and the Metadata_Sidebar
8. IF a file format is not supported, THEN THE File_Viewer SHALL display a message indicating the format is unsupported

### Requirement 5: On-Demand Sync

**User Story:** As a user, I want to trigger a filesystem scan manually, so that the database reflects the current state of files on disk without background processes.

#### Acceptance Criteria

1. WHEN a user triggers the sync action, THE Sync_Engine SHALL scan the local filesystem and update the SQLite database with new, modified, or deleted files
2. THE Sync_Engine SHALL operate only on-demand via user-initiated API calls
3. THE Sync_Engine SHALL NOT run any background file-watching process
4. WHEN the sync operation completes, THE Backend_API SHALL return a summary indicating the number of files added, updated, and removed
5. THE Backend_API SHALL log each sync operation in the sync_log table with a timestamp and result summary

### Requirement 6: Knowledge Graph Visualization

**User Story:** As a user, I want to see a visual graph of relationships between documents, so that I can understand cross-departmental connections.

#### Acceptance Criteria

1. THE Frontend_UI SHALL render the Knowledge_Graph using React Flow in the center panel as an alternative view to the File_Viewer
2. THE Knowledge_Graph SHALL display files as nodes and relationships as edges
3. THE Backend_API SHALL auto-generate relationships between files that share the same department or tags
4. WHEN a user manually creates, updates, or deletes a relationship, THE Backend_API SHALL persist the change and override any conflicting auto-generated relationship
5. WHEN a user selects a node in the Knowledge_Graph, THE Frontend_UI SHALL display the corresponding file metadata in the Metadata_Sidebar

### Requirement 7: File Metadata and Tagging

**User Story:** As a user, I want to view and edit metadata and tags for each file, so that I can categorize and find documents efficiently.

#### Acceptance Criteria

1. THE Metadata_Sidebar SHALL display file metadata including name, path, department, size, creation date, and modification date in the right panel with an approximate width of 300 pixels
2. THE Metadata_Sidebar SHALL allow users to add, edit, and remove tags on a selected file
3. WHEN a user modifies tags on a file, THE Frontend_UI SHALL send the updated tags to the Backend_API for persistence
4. WHEN tags are updated on a file, THE Backend_API SHALL recalculate auto-generated relationships for that file

### Requirement 8: KB Index Management

**User Story:** As a user, I want to manage the knowledge base index, so that I can control which files are indexed and searchable.

#### Acceptance Criteria

1. THE Backend_API SHALL maintain an index of all tracked files in the SQLite database
2. WHEN a file is added to the filesystem and a sync is triggered, THE Sync_Engine SHALL add the file to the index
3. WHEN a file is removed from the filesystem and a sync is triggered, THE Sync_Engine SHALL remove the file from the index
4. THE Backend_API SHALL provide an endpoint to retrieve the current index status including total file count and last sync timestamp

### Requirement 9: SQLite Database Schema

**User Story:** As a developer, I want a well-defined database schema, so that file metadata, relationships, and sync history are stored consistently.

#### Acceptance Criteria

1. THE Backend_API SHALL create a files table storing file metadata including name, path, department, size, tags, creation date, and modification date
2. THE Backend_API SHALL create a relationships table storing source file ID, target file ID, relationship type, and whether the relationship is auto-generated or manual
3. THE Backend_API SHALL create a sync_log table storing sync operation timestamp, files added count, files updated count, files removed count, and status
4. THE Backend_API SHALL apply the database schema automatically on application startup using SQLAlchemy migrations or table creation

### Requirement 10: Seed Data and Auto-Index

**User Story:** As a developer, I want sample files pre-loaded on first startup, so that the application is immediately usable for demonstration.

#### Acceptance Criteria

1. WHEN the KB_Manager starts for the first time, THE Backend_API SHALL populate the filesystem with 2-3 seed files per department
2. WHEN seed data is created, THE Sync_Engine SHALL automatically index all seed files into the SQLite database
3. THE Backend_API SHALL skip seed data creation if files already exist in the department folders

### Requirement 11: Frontend Layout and Styling

**User Story:** As a user, I want a professional dark-themed interface with a clear panel layout, so that the application feels enterprise-grade.

#### Acceptance Criteria

1. THE Frontend_UI SHALL use a three-panel layout: left File_Explorer (~280px), center File_Viewer or Knowledge_Graph, and right Metadata_Sidebar (~300px)
2. THE Frontend_UI SHALL include a top navigation bar with application branding and primary actions including the sync trigger and view toggle
3. THE Frontend_UI SHALL apply a dark color theme using Tailwind CSS
4. THE Frontend_UI SHALL be built with React, TypeScript, and Vite as the build toolchain

### Requirement 12: Project Setup and Deployment

**User Story:** As a developer, I want a single git clone workflow with clear setup instructions, so that the project is easy to run locally.

#### Acceptance Criteria

1. THE KB_Manager SHALL be runnable from a single repository clone with documented setup steps
2. THE KB_Manager SHALL include a README file with installation prerequisites, setup commands, and startup instructions for both backend and frontend
3. THE KB_Manager SHALL NOT require authentication, cloud services, or vector embedding dependencies
4. THE Backend_API SHALL be startable with a single command after dependency installation
5. THE Frontend_UI SHALL be startable with a single command after dependency installation
