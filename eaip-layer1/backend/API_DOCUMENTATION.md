# Executive Copilot — API Documentation

Base URL: `http://localhost:8000`

---

## Table of Contents

- [Chat (LLM Generation)](#chat-llm-generation)
- [Search (Retrieval)](#search-retrieval)
- [Files](#files)
- [Departments](#departments)
- [Sync](#sync)
- [Embeddings](#embeddings)
- [Graph](#graph)

---

## Chat (LLM Generation)

These endpoints require a configured LLM provider (`KB_LLM_PROVIDER` and `KB_LLM_API_KEY` set in `.env`). If the LLM is not configured, they return `503 Service Unavailable`.

---

### POST /api/chat

Generate a natural language answer grounded in knowledge base content. The query is routed through an agentic workflow that classifies it (simple retrieval, multi-step reasoning, or clarification) and produces a structured response with source attributions.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | The question to ask (1–2000 characters) |
| `session_id` | string | No | null | Session ID for multi-turn conversations (max 128 chars) |
| `retrieval_mode` | string | No | `"combined"` | One of: `"local"`, `"global"`, `"combined"` |
| `top_k` | integer | No | null | Number of documents to retrieve (1–50) |
| `max_tokens` | integer | No | null | Max context token budget (1000–16000) |

**Response (200):**

```json
{
  "answer": "Based on the Q3 report [Source 1], revenue increased by 15%...",
  "source_attributions": [
    {
      "file_id": 12,
      "file_name": "q3_report.pdf",
      "department": "Finance",
      "chunk_index": 3
    }
  ],
  "retrieval_metadata": {
    "retrieval_mode": "combined",
    "documents_retrieved": 5,
    "query_time_ms": 1230
  },
  "token_usage": {
    "prompt_tokens": 850,
    "completion_tokens": 120,
    "total_tokens": 970
  },
  "response_type": "answer",
  "step_limit_reached": false
}
```

**Error Responses:**

| Status | Condition |
|--------|-----------|
| 422 | Invalid query (empty, too long, invalid retrieval_mode) |
| 503 | LLM not configured or packages missing |
| 504 | Request timed out (>60 seconds) |
| 500 | Unrecoverable internal error |

**curl Examples:**

```bash
# Basic question
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "What was our Q3 revenue?"}'

# With session for multi-turn conversation
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Compare that to Q2",
    "session_id": "user-session-abc123",
    "retrieval_mode": "combined",
    "top_k": 10
  }'

# Local search only (vector similarity)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Who is the CFO?", "retrieval_mode": "local", "top_k": 3}'

# Global search (community-based)
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Summarize the organizational structure", "retrieval_mode": "global"}'
```

---

### POST /api/chat/stream

Stream a response as Server-Sent Events (SSE). Tokens are emitted as they are generated, followed by source attributions, metadata, and a done signal.

**Request Body:** Same as `POST /api/chat`.

**SSE Event Sequence:**

1. **`token`** (0 or more) — Partial answer text as it's generated
2. **`sources`** — Source attributions after generation completes
3. **`metadata`** — Retrieval mode, documents retrieved, token usage
4. **`done`** — End-of-stream signal
5. **`error`** (on failure) — Error message, then stream closes

**Event Format:**

```
event: token
data: {"content": "Based on"}

event: token
data: {"content": " the Q3 report"}

event: sources
data: {"source_attributions": [{"file_id": 12, "file_name": "q3_report.pdf", "department": "Finance", "chunk_index": 3}]}

event: metadata
data: {"retrieval_mode": "combined", "documents_retrieved": 5, "token_usage": {"prompt_tokens": 0, "completion_tokens": 42, "total_tokens": 42}}

event: done
data: {}
```

**Error Responses:**

| Status | Condition |
|--------|-----------|
| 422 | Invalid request body |
| 503 | LLM not configured or packages missing |

**curl Examples:**

```bash
# Stream a response (tokens appear in real-time)
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"query": "What are our key strategic priorities?"}' \
  --no-buffer

# Stream with session and retrieval mode
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "query": "Explain the budget allocation for next quarter",
    "session_id": "session-xyz",
    "retrieval_mode": "combined",
    "max_tokens": 8000
  }' \
  --no-buffer
```

---

## Search (Retrieval)

These endpoints perform document retrieval without LLM generation. They work regardless of LLM configuration.

---

### POST /api/search/local

Perform a local vector similarity search enriched with graph neighborhood context. Generates a query embedding, searches the vector store, enriches results with 1-hop graph neighbors, and ranks by combined score.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query text |
| `top_k` | integer | No | 5 | Max results to return (1–50) |
| `min_score` | float | No | 0.5 | Minimum similarity score (0.0–1.0) |
| `similarity_weight` | float | No | 0.7 | Weight for similarity vs graph score (0.0–1.0) |

**curl Example:**

```bash
curl -X POST http://localhost:8000/api/search/local \
  -H "Content-Type: application/json" \
  -d '{
    "query": "employee onboarding process",
    "top_k": 10,
    "min_score": 0.3
  }'
```

---

### POST /api/search/global

Perform a global community-based search. Compares the query embedding against community summary embeddings and returns ranked community summaries with member entities.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query text |
| `num_communities` | integer | No | 3 | Number of communities to return (1–20) |
| `min_relevance` | float | No | 0.1 | Minimum relevance score (0.0–1.0) |

**curl Example:**

```bash
curl -X POST http://localhost:8000/api/search/global \
  -H "Content-Type: application/json" \
  -d '{
    "query": "organizational leadership structure",
    "num_communities": 5,
    "min_relevance": 0.2
  }'
```

---

### POST /api/search/combined

Perform a combined local + global search within a token budget. Merges local and global results interleaved by descending relevance score, then truncates to fit within the maximum token limit.

**Request Body:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | Yes | — | Search query text |
| `max_tokens` | integer | No | 4000 | Token budget for results (1000–16000) |
| `top_k` | integer | No | 5 | Max local results (1–50) |
| `num_communities` | integer | No | 3 | Number of communities (1–20) |

**curl Example:**

```bash
curl -X POST http://localhost:8000/api/search/combined \
  -H "Content-Type: application/json" \
  -d '{
    "query": "quarterly financial performance",
    "max_tokens": 8000,
    "top_k": 10,
    "num_communities": 5
  }'
```

---

## Files

CRUD operations for indexed knowledge base files.

---

### GET /api/files

List all indexed files with optional filters.

**Query Parameters:**

| Param | Type | Description |
|-------|------|-------------|
| `department` | string | Filter by department name |
| `subfolder` | string | Filter by subfolder |
| `file_type` | string | Filter by file type (e.g., "pdf", "docx") |
| `sync_status` | string | Filter by sync status |

**curl Examples:**

```bash
# List all files
curl http://localhost:8000/api/files

# Filter by department
curl "http://localhost:8000/api/files?department=Finance"

# Filter by file type
curl "http://localhost:8000/api/files?file_type=pdf"
```

---

### POST /api/files/upload

Upload a new file to the knowledge base.

**Form Data:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | file | Yes | The file to upload |
| `department` | string | Yes | Target department |
| `subfolder` | string | Yes | Target subfolder within department |

**curl Example:**

```bash
curl -X POST http://localhost:8000/api/files/upload \
  -F "file=@/path/to/document.pdf" \
  -F "department=Finance" \
  -F "subfolder=reports"
```

---

### GET /api/files/{file_id}

Get metadata for a specific file by ID.

```bash
curl http://localhost:8000/api/files/12
```

---

### GET /api/files/{file_id}/content

Download the raw file content.

```bash
curl http://localhost:8000/api/files/12/content --output document.pdf
```

---

### PATCH /api/files/{file_id}/tags

Update tags on a file.

**Request Body:**

```json
{"tags": ["quarterly", "finance", "2024"]}
```

**curl Example:**

```bash
curl -X PATCH http://localhost:8000/api/files/12/tags \
  -H "Content-Type: application/json" \
  -d '{"tags": ["quarterly", "finance", "2024"]}'
```

---

### DELETE /api/files/{file_id}

Delete a file from the knowledge base.

```bash
curl -X DELETE http://localhost:8000/api/files/12
```

---

### DELETE /api/files/{file_id}/index

Remove a file from the search index without deleting the file itself.

```bash
curl -X DELETE http://localhost:8000/api/files/12/index
```

---

## Departments

---

### GET /api/departments

Get the department tree structure with folders and files.

Returns a hierarchical tree of departments → subfolders → files, including metadata like colors, descriptions, and sensitivity levels.

```bash
curl http://localhost:8000/api/departments
```

**Response (200):**

```json
[
  {
    "id": "dept-finance",
    "name": "Finance",
    "type": "department",
    "color": "#4CAF50",
    "description": "Financial reports and budgets",
    "outputs": ["quarterly_reports", "budgets"],
    "children": [
      {
        "id": "folder-finance-reports",
        "name": "Reports",
        "type": "folder",
        "sensitivity": "Internal",
        "children": [
          {
            "id": "file-12",
            "name": "q3_report.pdf",
            "type": "file",
            "fileId": 12
          }
        ]
      }
    ]
  }
]
```

---

## Sync

Manage file synchronization between the filesystem and the database index.

---

### POST /api/sync

Trigger a full sync of the knowledge base. Detects new, modified, and deleted files.

```bash
curl -X POST http://localhost:8000/api/sync
```

**Response (200):**

```json
{
  "files_added": 3,
  "files_updated": 1,
  "files_removed": 0,
  "status": "completed",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

### POST /api/sync/{file_id}

Trigger sync for a specific file.

```bash
curl -X POST http://localhost:8000/api/sync/12
```

---

### GET /api/sync/status

Get the current index status (total files, last sync time, pending count).

```bash
curl http://localhost:8000/api/sync/status
```

**Response (200):**

```json
{
  "total_files": 45,
  "last_sync_timestamp": "2024-01-15T10:30:00Z",
  "pending_count": 2
}
```

---

### POST /api/sync/toggle

Toggle automatic sync on/off.

```bash
curl -X POST http://localhost:8000/api/sync/toggle
```

**Response (200):**

```json
{"auto_sync": false}
```

---

### GET /api/sync/logs

Get sync history logs (most recent first).

```bash
curl http://localhost:8000/api/sync/logs
```

---

## Embeddings

Manage document embedding jobs for the vector store.

---

### POST /api/embeddings/run

Trigger an incremental embedding job. Processes only files with changed content or no prior embedding.

```bash
curl -X POST http://localhost:8000/api/embeddings/run
```

**Response (200):**

```json
{
  "job_id": "emb-20240115-001",
  "files_processed": 5,
  "chunks_generated": 42,
  "errors": [],
  "status": "completed"
}
```

---

### POST /api/embeddings/run/full

Trigger a full re-embedding of all indexed files (regardless of content hash).

```bash
curl -X POST http://localhost:8000/api/embeddings/run/full
```

---

### POST /api/embeddings/run/{file_id}

Trigger embedding for a single file.

```bash
curl -X POST http://localhost:8000/api/embeddings/run/12
```

**Error:** Returns `404` if the file doesn't exist.

---

### GET /api/embeddings/status

Get the current embedding status of the knowledge base.

```bash
curl http://localhost:8000/api/embeddings/status
```

**Response (200):**

```json
{
  "total_files_embedded": 40,
  "files_pending": 5,
  "last_job_timestamp": "2024-01-15T09:00:00Z"
}
```

---

## Graph

Knowledge graph visualization data and relationship management.

---

### GET /api/graph

Get the full knowledge graph (nodes and edges) with computed radial layout positions.

```bash
curl http://localhost:8000/api/graph
```

**Response (200):**

```json
{
  "nodes": [
    {
      "id": "12",
      "data": {
        "label": "q3_report.pdf",
        "department": "Finance",
        "fileId": 12
      },
      "position": {"x": 350.5, "y": 200.3}
    }
  ],
  "edges": [
    {
      "id": "1",
      "source": "12",
      "target": "15",
      "label": "references"
    }
  ]
}
```

---

### POST /api/graph/relationships

Create a manual relationship between two files.

**Request Body:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source_file_id` | integer | Yes | Source file ID |
| `target_file_id` | integer | Yes | Target file ID |
| `relationship_type` | string | Yes | Type of relationship (e.g., "references", "supersedes") |

**curl Example:**

```bash
curl -X POST http://localhost:8000/api/graph/relationships \
  -H "Content-Type: application/json" \
  -d '{
    "source_file_id": 12,
    "target_file_id": 15,
    "relationship_type": "references"
  }'
```

**Error:** Returns `404` if source or target file doesn't exist.

---

### PUT /api/graph/relationships/{relationship_id}

Update the type of an existing relationship.

**Request Body:**

```json
{"relationship_type": "supersedes"}
```

**curl Example:**

```bash
curl -X PUT http://localhost:8000/api/graph/relationships/1 \
  -H "Content-Type: application/json" \
  -d '{"relationship_type": "supersedes"}'
```

---

### DELETE /api/graph/relationships/{relationship_id}

Delete a relationship.

```bash
curl -X DELETE http://localhost:8000/api/graph/relationships/1
```

**Error:** Returns `404` if the relationship doesn't exist.

---

## Running the Server

```bash
cd eaip-layer1/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The interactive API docs are also available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
