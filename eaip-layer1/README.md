# Knowledge Base Manager

A full-stack proof-of-concept application for organizing, viewing, and exploring departmental documents. Features a three-panel dark-themed UI with file tree navigation, multi-format document viewing, on-demand sync, metadata tagging, and knowledge graph visualization.

## Prerequisites

- Python 3.11+
- Node.js 18+
- npm

No authentication, cloud services, or vector embedding dependencies are required.

## Quick Start

```bash
git clone <repository-url>
cd eaip-layer1
```

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API server starts at `http://localhost:8000`. On first startup it will:
- Create the SQLite database and tables
- Initialize the department folder structure under `knowledge_base/`
- Seed 2–3 sample files per department
- Run an initial sync to index all files

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server starts at `http://localhost:5173` and proxies API requests to the backend.

## Architecture

```
Frontend (React + TypeScript + Vite + Tailwind CSS)
        │
        │  HTTP REST
        ▼
Backend (FastAPI + SQLAlchemy + SQLite)
        │
        ├── SQLite   → file metadata, relationships, sync logs
        └── Filesystem → knowledge_base/ document storage
```

**Frontend** — Three-panel layout: file explorer tree (left), file viewer or knowledge graph (center), metadata sidebar (right).

**Backend** — FastAPI app with service layer for sync, relationships, and file management. SQLite stores metadata; actual documents live on the local filesystem.

## API Endpoints

| Group | Endpoint | Description |
|-------|----------|-------------|
| Files | `GET /api/files` | List all indexed files |
| Files | `GET /api/files/{id}` | Get file metadata |
| Files | `GET /api/files/{id}/content` | Serve file content |
| Files | `PUT /api/files/{id}/tags` | Update file tags |
| Departments | `GET /api/departments` | List departments with hierarchy |
| Sync | `POST /api/sync` | Trigger filesystem sync |
| Sync | `GET /api/sync/status` | Index status (file count, last sync) |
| Sync | `GET /api/sync/logs` | Sync history |
| Graph | `GET /api/graph` | Full graph data (nodes + edges) |
| Graph | `POST /api/graph/relationships` | Create manual relationship |
| Graph | `PUT /api/graph/relationships/{id}` | Update relationship |
| Graph | `DELETE /api/graph/relationships/{id}` | Delete relationship |

## Supported File Formats

PDF, Excel (.xlsx/.xls), JSON, DOCX, Markdown, and plain text.

## Project Structure

```
eaip-layer1/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entry point
│   │   ├── config.py        # Settings (port, DB, CORS)
│   │   ├── database.py      # SQLAlchemy setup
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── routers/         # API route handlers
│   │   ├── services/        # Business logic
│   │   └── utils/           # Department config
│   ├── knowledge_base/      # Document storage
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/             # HTTP client
│   │   ├── components/      # UI components
│   │   ├── hooks/           # React hooks
│   │   ├── types/           # TypeScript types
│   │   └── utils/           # Helpers
│   ├── package.json
│   └── index.html
└── README.md
```
