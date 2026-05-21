# Design Document: Knowledge Base Manager

## Overview

The Knowledge Base Manager (KB Manager) is a full-stack POC application for organizing, viewing, and exploring departmental documents. It uses a three-panel dark-themed UI backed by a Python FastAPI server with SQLite metadata storage and local filesystem document storage.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Frontend (React + Vite)                       │
│  ┌──────────────┐  ┌──────────────────────┐  ┌──────────────────┐  │
│  │ File Explorer │  │  File Viewer /       │  │ Metadata Sidebar │  │
│  │  (Tree View)  │  │  Knowledge Graph     │  │  (Tags + Info)   │  │
│  │   ~280px      │  │  (Center Panel)      │  │   ~300px         │  │
│  └──────────────┘  └──────────────────────┘  └──────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Top Navigation Bar                            ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                              │ HTTP (REST)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI + SQLAlchemy)                   │
│  ┌────────────┐  ┌────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  File API   │  │  Sync API  │  │ Graph API│  │ Department API│  │
│  └────────────┘  └────────────┘  └──────────┘  └───────────────┘  │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     Service Layer                               │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌────────────────────────┐   │ │
│  │  │File Svc  │  │ Sync Engine  │  │ Relationship Engine    │   │ │
│  │  └──────────┘  └──────────────┘  └────────────────────────┘   │ │
│  └────────────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────┐  ┌──────────────────────────────────────┐│
│  │  SQLite (metadata)   │  │  Local Filesystem (knowledge_base/) ││
│  └──────────────────────┘  └──────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
eaip-layer1/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── config.py            # Configuration (port, DB path, KB path)
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── file.py          # File SQLAlchemy model
│   │   │   ├── relationship.py  # Relationship model
│   │   │   └── sync_log.py      # SyncLog model
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── file.py          # Pydantic request/response schemas
│   │   │   ├── relationship.py
│   │   │   ├── sync.py
│   │   │   └── graph.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── files.py         # File CRUD endpoints
│   │   │   ├── departments.py   # Department listing
│   │   │   ├── sync.py          # Sync trigger endpoint
│   │   │   └── graph.py         # Graph data endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── file_service.py
│   │   │   ├── sync_engine.py
│   │   │   ├── relationship_engine.py
│   │   │   └── seed_service.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── department_config.py  # Department/subfolder definitions
│   ├── knowledge_base/           # Local file storage root
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── tests/
│       ├── __init__.py
│       ├── test_sync_engine.py
│       ├── test_relationship_engine.py
│       └── test_file_service.py
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   └── client.ts         # Axios/fetch wrapper
│   │   ├── components/
│   │   │   ├── Layout/
│   │   │   │   ├── TopNav.tsx
│   │   │   │   └── ThreePanel.tsx
│   │   │   ├── FileExplorer/
│   │   │   │   ├── FileExplorer.tsx
│   │   │   │   └── TreeNode.tsx
│   │   │   ├── FileViewer/
│   │   │   │   ├── FileViewer.tsx
│   │   │   │   ├── PdfViewer.tsx
│   │   │   │   ├── ExcelViewer.tsx
│   │   │   │   ├── JsonViewer.tsx
│   │   │   │   ├── DocxViewer.tsx
│   │   │   │   ├── MarkdownViewer.tsx
│   │   │   │   └── PlainTextViewer.tsx
│   │   │   ├── KnowledgeGraph/
│   │   │   │   ├── KnowledgeGraph.tsx
│   │   │   │   └── GraphNode.tsx
│   │   │   └── MetadataSidebar/
│   │   │       ├── MetadataSidebar.tsx
│   │   │       └── TagEditor.tsx
│   │   ├── hooks/
│   │   │   ├── useFiles.ts
│   │   │   ├── useSync.ts
│   │   │   └── useGraph.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   └── utils/
│   │       └── fileFormat.ts     # Format detection utility
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.ts
└── README.md
```

## Data Models

### SQLAlchemy Models (Backend)

```python
# models/file.py
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base

class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    path = Column(String, nullable=False, unique=True)  # Relative to knowledge_base/
    department = Column(String, nullable=False)
    size = Column(Integer, nullable=False)
    tags = Column(JSON, default=list)  # List of tag strings
    created_at = Column(DateTime, nullable=False)
    modified_at = Column(DateTime, nullable=False)
    content_hash = Column(String, nullable=True)  # For detecting modifications


# models/relationship.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.database import Base

class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    target_file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    relationship_type = Column(String, nullable=False)  # "department", "tag", "manual"
    is_manual = Column(Boolean, default=False)


# models/sync_log.py
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base

class SyncLog(Base):
    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False)
    files_added = Column(Integer, default=0)
    files_updated = Column(Integer, default=0)
    files_removed = Column(Integer, default=0)
    status = Column(String, nullable=False)  # "success", "error"
    summary = Column(String, nullable=True)
```

### TypeScript Types (Frontend)

```typescript
// types/index.ts

export interface FileNode {
  id: number;
  name: string;
  path: string;
  department: string;
  size: number;
  tags: string[];
  createdAt: string;
  modifiedAt: string;
}

export interface TreeNode {
  id: string;
  name: string;
  type: "department" | "folder" | "file";
  children?: TreeNode[];
  fileId?: number;
}

export interface Relationship {
  id: number;
  sourceFileId: number;
  targetFileId: number;
  relationshipType: "department" | "tag" | "manual";
  isManual: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface GraphNode {
  id: string;
  data: { label: string; department: string; fileId: number };
  position: { x: number; y: number };
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  type?: string;
}

export interface SyncResult {
  filesAdded: number;
  filesUpdated: number;
  filesRemoved: number;
  status: string;
  timestamp: string;
}

export interface IndexStatus {
  totalFiles: number;
  lastSyncTimestamp: string | null;
}

export type ViewMode = "viewer" | "graph";

export type SupportedFormat = "pdf" | "xlsx" | "json" | "docx" | "md" | "txt";
```

## Component Design

### Backend Components

#### 1. Configuration (`config.py`)

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_port: int = 8000
    database_url: str = "sqlite:///./kb_manager.db"
    knowledge_base_path: str = "./knowledge_base"
    cors_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_prefix = "KB_"
```

#### 2. Sync Engine (`services/sync_engine.py`)

The sync engine is the core backend service. It scans the filesystem and reconciles with the database.

```python
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import hashlib

@dataclass
class SyncResult:
    files_added: int
    files_updated: int
    files_removed: int
    status: str
    timestamp: datetime

class SyncEngine:
    def __init__(self, db_session, kb_path: str):
        self.db = db_session
        self.kb_path = Path(kb_path)

    def execute_sync(self) -> SyncResult:
        """Scan filesystem and reconcile with database."""
        timestamp = datetime.utcnow()
        fs_files = self._scan_filesystem()
        db_files = self._get_indexed_files()

        added = self._add_new_files(fs_files, db_files)
        updated = self._update_modified_files(fs_files, db_files)
        removed = self._remove_deleted_files(fs_files, db_files)

        result = SyncResult(
            files_added=added,
            files_updated=updated,
            files_removed=removed,
            status="success",
            timestamp=timestamp,
        )
        self._log_sync(result)
        return result

    def _scan_filesystem(self) -> dict[str, dict]:
        """Walk the knowledge_base directory and collect file metadata."""
        files = {}
        for file_path in self.kb_path.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(self.kb_path))
                stat = file_path.stat()
                files[rel_path] = {
                    "name": file_path.name,
                    "path": rel_path,
                    "department": self._extract_department(rel_path),
                    "size": stat.st_size,
                    "modified_at": datetime.fromtimestamp(stat.st_mtime),
                    "created_at": datetime.fromtimestamp(stat.st_ctime),
                    "content_hash": self._compute_hash(file_path),
                }
        return files

    def _extract_department(self, rel_path: str) -> str:
        """Extract department name from the first path segment."""
        return rel_path.split("/")[0]

    def _compute_hash(self, file_path: Path) -> str:
        """Compute MD5 hash for change detection."""
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
```

#### 3. Relationship Engine (`services/relationship_engine.py`)

```python
class RelationshipEngine:
    def __init__(self, db_session):
        self.db = db_session

    def recalculate_for_file(self, file_id: int) -> None:
        """Recalculate auto-generated relationships for a specific file."""
        # Remove existing auto-generated relationships for this file
        self._remove_auto_relationships(file_id)
        # Generate new relationships based on department and tags
        file = self._get_file(file_id)
        self._generate_department_relationships(file)
        self._generate_tag_relationships(file)

    def recalculate_all(self) -> None:
        """Recalculate all auto-generated relationships."""
        self._remove_all_auto_relationships()
        files = self._get_all_files()
        for file in files:
            self._generate_department_relationships(file)
            self._generate_tag_relationships(file)

    def _generate_department_relationships(self, file) -> None:
        """Create edges between files in the same department."""
        same_dept_files = self._get_files_in_department(file.department)
        for other in same_dept_files:
            if other.id != file.id:
                self._create_relationship(
                    file.id, other.id, "department", is_manual=False
                )

    def _generate_tag_relationships(self, file) -> None:
        """Create edges between files sharing at least one tag."""
        if not file.tags:
            return
        files_with_shared_tags = self._get_files_with_any_tag(file.tags)
        for other in files_with_shared_tags:
            if other.id != file.id:
                self._create_relationship(
                    file.id, other.id, "tag", is_manual=False
                )

    def create_manual_relationship(
        self, source_id: int, target_id: int, rel_type: str
    ) -> None:
        """Create or override a relationship with a manual one."""
        # Remove any existing auto relationship between these files
        self._remove_relationship_between(source_id, target_id)
        self._create_relationship(source_id, target_id, rel_type, is_manual=True)
```

#### 4. Department Configuration (`utils/department_config.py`)

```python
DEPARTMENTS = {
    "Finance": [
        "Budgets",
        "Reports",
        "Invoices",
    ],
    "Retail_Operations": [
        "Sales",
        "Inventory",
        "Promotions",
    ],
    "HR": [
        "Policies",
        "Onboarding",
        "Training",
    ],
    "Supply_Chain": [
        "Logistics",
        "Vendors",
        "Procurement",
    ],
    "Executive": [
        "Strategy",
        "Board_Reports",
        "Communications",
    ],
    "IT_Audit": [
        "Security",
        "Compliance",
        "Infrastructure",
    ],
}
```

### Frontend Components

#### 1. File Format Detection (`utils/fileFormat.ts`)

```typescript
const FORMAT_MAP: Record<string, SupportedFormat> = {
  ".pdf": "pdf",
  ".xlsx": "xlsx",
  ".xls": "xlsx",
  ".json": "json",
  ".docx": "docx",
  ".md": "md",
  ".txt": "txt",
};

export function detectFormat(filename: string): SupportedFormat | null {
  const ext = filename.substring(filename.lastIndexOf(".")).toLowerCase();
  return FORMAT_MAP[ext] ?? null;
}

export function isSupported(filename: string): boolean {
  return detectFormat(filename) !== null;
}
```

#### 2. FileViewer Component (`components/FileViewer/FileViewer.tsx`)

```typescript
import { FC } from "react";
import { FileNode, SupportedFormat } from "../../types";
import { detectFormat } from "../../utils/fileFormat";
import PdfViewer from "./PdfViewer";
import ExcelViewer from "./ExcelViewer";
import JsonViewer from "./JsonViewer";
import DocxViewer from "./DocxViewer";
import MarkdownViewer from "./MarkdownViewer";
import PlainTextViewer from "./PlainTextViewer";

interface FileViewerProps {
  file: FileNode | null;
}

const VIEWER_MAP: Record<SupportedFormat, FC<{ fileId: number }>> = {
  pdf: PdfViewer,
  xlsx: ExcelViewer,
  json: JsonViewer,
  docx: DocxViewer,
  md: MarkdownViewer,
  txt: PlainTextViewer,
};

export const FileViewer: FC<FileViewerProps> = ({ file }) => {
  if (!file) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        Select a file to view
      </div>
    );
  }

  const format = detectFormat(file.name);

  if (!format) {
    return (
      <div className="flex items-center justify-center h-full text-yellow-400">
        Unsupported file format: {file.name.split(".").pop()}
      </div>
    );
  }

  const Viewer = VIEWER_MAP[format];
  return <Viewer fileId={file.id} />;
};
```

#### 3. Knowledge Graph Component (`components/KnowledgeGraph/KnowledgeGraph.tsx`)

```typescript
import { FC, useCallback } from "react";
import ReactFlow, {
  Background,
  Controls,
  Node,
  Edge,
  useNodesState,
  useEdgesState,
} from "reactflow";
import { GraphData } from "../../types";

interface KnowledgeGraphProps {
  data: GraphData;
  onNodeSelect: (fileId: number) => void;
}

export const KnowledgeGraph: FC<KnowledgeGraphProps> = ({
  data,
  onNodeSelect,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState(data.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(data.edges);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeSelect(node.data.fileId);
    },
    [onNodeSelect]
  );

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        fitView
      >
        <Background color="#374151" />
        <Controls />
      </ReactFlow>
    </div>
  );
};
```

## API Contracts

### File Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| GET | `/api/files` | List all indexed files | — | `FileNode[]` |
| GET | `/api/files/{id}` | Get file metadata | — | `FileNode` |
| GET | `/api/files/{id}/content` | Serve file content | — | Binary stream |
| PUT | `/api/files/{id}/tags` | Update file tags | `{ tags: string[] }` | `FileNode` |
| DELETE | `/api/files/{id}` | Remove file from index | — | `204` |

### Department Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| GET | `/api/departments` | List departments with hierarchy | `TreeNode[]` |

### Sync Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| POST | `/api/sync` | Trigger filesystem sync | `SyncResult` |
| GET | `/api/sync/status` | Get index status | `IndexStatus` |
| GET | `/api/sync/logs` | Get sync history | `SyncLog[]` |

### Graph Endpoints

| Method | Path | Description | Request Body | Response |
|--------|------|-------------|--------------|----------|
| GET | `/api/graph` | Get full graph data | — | `GraphData` |
| POST | `/api/graph/relationships` | Create manual relationship | `{ sourceFileId, targetFileId, type }` | `Relationship` |
| PUT | `/api/graph/relationships/{id}` | Update relationship | `{ type }` | `Relationship` |
| DELETE | `/api/graph/relationships/{id}` | Delete relationship | — | `204` |

### Response Schemas

```python
# schemas/sync.py
from pydantic import BaseModel
from datetime import datetime

class SyncResultResponse(BaseModel):
    files_added: int
    files_updated: int
    files_removed: int
    status: str
    timestamp: datetime

class IndexStatusResponse(BaseModel):
    total_files: int
    last_sync_timestamp: datetime | None


# schemas/file.py
class FileResponse(BaseModel):
    id: int
    name: str
    path: str
    department: str
    size: int
    tags: list[str]
    created_at: datetime
    modified_at: datetime

class TagUpdateRequest(BaseModel):
    tags: list[str]


# schemas/graph.py
class GraphNodeResponse(BaseModel):
    id: str
    data: dict
    position: dict

class GraphEdgeResponse(BaseModel):
    id: str
    source: str
    target: str
    label: str | None = None

class GraphDataResponse(BaseModel):
    nodes: list[GraphNodeResponse]
    edges: list[GraphEdgeResponse]

class RelationshipCreateRequest(BaseModel):
    source_file_id: int
    target_file_id: int
    relationship_type: str
```

## Key Algorithms

### Sync Algorithm

```
SYNC():
  1. Scan filesystem → collect all files with metadata (path, size, hash, timestamps)
  2. Query database → get all currently indexed files
  3. Compute diff:
     - NEW: files on disk not in DB (by path)
     - MODIFIED: files on disk AND in DB where content_hash differs
     - DELETED: files in DB not on disk (by path)
  4. Apply changes:
     - INSERT new file records
     - UPDATE modified file records (size, hash, modified_at)
     - DELETE removed file records (cascade removes relationships)
  5. Recalculate auto-generated relationships for affected files
  6. Log sync result to sync_log table
  7. Return SyncResult summary
```

### Relationship Auto-Generation Algorithm

```
GENERATE_RELATIONSHIPS(file):
  1. Find all other files in the same department
     → Create "department" edge between file and each
  2. For each tag on the file:
     → Find all other files with that tag
     → Create "tag" edge between file and each
  3. Deduplicate: if both department and tag edges exist between
     same pair, keep only the tag edge (more specific)
  4. Never overwrite edges where is_manual = True
```

### Graph Layout Algorithm

```
LAYOUT_GRAPH(files, relationships):
  1. Group files by department
  2. Assign each department a sector (radial layout)
  3. Within each sector, arrange files in a grid
  4. Position nodes with spacing to minimize edge crossings
  5. Return positioned nodes + edges for React Flow
```

### Seed Data Algorithm

```
SEED_ON_FIRST_START():
  1. For each department in DEPARTMENTS:
     a. Check if department folder exists and contains files
     b. If empty or missing:
        - Create folder structure
        - Copy 2-3 sample files (varied formats) into subfolders
  2. Run sync to index all seed files
```

## Error Handling

| Scenario | Backend Response | Frontend Behavior |
|----------|-----------------|-------------------|
| File not found (DB) | 404 with message | Show "File not found" in viewer |
| File not found (disk) | 404 with message | Show "File missing from disk" |
| Unsupported format | N/A (frontend-only) | Show unsupported format message |
| Sync failure (IO error) | 500 with error detail | Show error toast notification |
| Invalid tag update | 422 with validation errors | Show inline validation message |
| Relationship conflict | 409 with existing relationship | Show conflict resolution prompt |
| Database error | 500 with generic message | Show error toast notification |

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Sync database-filesystem consistency

*For any* filesystem state within the `knowledge_base/` directory, after a sync operation completes successfully, the set of file records in the SQLite database SHALL be exactly equal to the set of files present on disk — every file on disk has a corresponding database record with matching path, and every database record corresponds to an existing file on disk.

**Validates: Requirements 5.1, 8.1, 8.2, 8.3**

### Property 2: Sync summary accuracy

*For any* sync operation, the returned `files_added`, `files_updated`, and `files_removed` counts SHALL exactly equal the number of INSERT, UPDATE, and DELETE operations performed on the files table during that sync.

**Validates: Requirements 5.4**

### Property 3: Sync operation logging

*For any* sync operation (successful or failed), a corresponding entry SHALL exist in the `sync_log` table with a timestamp equal to or later than the sync invocation time, and the logged counts SHALL match the actual sync result.

**Validates: Requirements 5.5**

### Property 4: Auto-relationship generation correctness

*For any* two files in the index, a "department" relationship SHALL exist between them if and only if they share the same department value, and a "tag" relationship SHALL exist between them if and only if they share at least one common tag — excluding pairs where a manual relationship already exists.

**Validates: Requirements 6.3, 7.4**

### Property 5: Manual relationship override precedence

*For any* pair of files where a manual relationship is created, the manual relationship SHALL persist regardless of subsequent auto-generation recalculations, and no auto-generated relationship SHALL exist between that same pair.

**Validates: Requirements 6.4**

### Property 6: Unsupported format detection

*For any* filename whose extension is not in the set {`.pdf`, `.xlsx`, `.xls`, `.json`, `.docx`, `.md`, `.txt`}, the `detectFormat` function SHALL return `null`, and the FileViewer component SHALL render an unsupported format message.

**Validates: Requirements 4.8**

### Property 7: Index status accuracy

*For any* state of the database, the index status endpoint SHALL return a `total_files` count equal to the number of rows in the `files` table, and a `last_sync_timestamp` equal to the most recent `timestamp` in the `sync_log` table (or null if no syncs have occurred).

**Validates: Requirements 8.4**

### Property 8: Seed idempotency

*For any* pre-existing state of the `knowledge_base/` directory where department folders already contain files, running the seed operation SHALL not create, modify, or delete any existing files.

**Validates: Requirements 10.3**
