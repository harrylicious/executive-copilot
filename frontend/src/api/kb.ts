// ─── Knowledge Base Manager API (Extended) ───────────────────────────────────
// Extends the existing frontend_new API to cover all eaip-layer1/backend features.

import type {
  FileNode,
  TreeNode,
  GraphData,
  Relationship,
  SyncResult,
  IndexStatus,
  SyncLog,
  EmbeddingStatus,
  EmbeddingLog,
  EmbeddingJobResult,
  SearchResponse,
  LocalSearchRequest,
  GlobalSearchRequest,
  CombinedSearchRequest,
  ChatResponse,
  ChatRequest,
  SSEEvent,
  ChatSessionSummary,
  ChatSessionDetail,
  SaveSessionRequest,
  PaginatedSessionsResponse,
} from "../types";

const API_BASE = "/api";

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = "ApiError";
  }
}

async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  let url = `${API_BASE}${path}`;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `GET ${path} failed (${res.status})`);
  }
  return res.json();
}

async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `POST ${path} failed (${res.status})`);
  }
  return res.json();
}

async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `PATCH ${path} failed (${res.status})`);
  }
  return res.json();
}

async function apiDelete(path: string): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `DELETE ${path} failed (${res.status})`);
  }
}

// ─── Files ───────────────────────────────────────────────────────────────────

export async function getFiles(params?: {
  department?: string;
  subfolder?: string;
  fileType?: string;
  syncStatus?: string;
}): Promise<FileNode[]> {
  return apiGet<FileNode[]>("/files", params as Record<string, string> | undefined);
}

export async function getFile(id: number): Promise<FileNode> {
  return apiGet<FileNode>(`/files/${id}`);
}

export function getFileContentUrl(id: number): string {
  return `/api/files/${id}/content`;
}

export async function revealFileInExplorer(id: number): Promise<void> {
  await apiPost(`/files/${id}/reveal`);
}

export async function updateFileTags(id: number, tags: string[]): Promise<FileNode> {
  return apiPatch<FileNode>(`/files/${id}/tags`, { tags });
}

export async function suggestTags(fileId: number): Promise<string[]> {
  return apiPost<string[]>(`/files/${fileId}/suggest-tags`);
}

export async function suggestRename(fileId: number): Promise<string[]> {
  return apiPost<string[]>(`/files/${fileId}/suggest-rename`);
}

export async function renameFile(fileId: number, newName: string): Promise<FileNode> {
  return apiPatch<FileNode>(`/files/${fileId}`, { name: newName });
}

export async function deleteFile(id: number): Promise<void> {
  await apiDelete(`/files/${id}`);
}

export async function removeFileFromIndex(id: number): Promise<void> {
  await apiDelete(`/files/${id}/index`);
}

export async function uploadFile(
  file: File,
  department: string,
  subfolder: string
): Promise<FileNode> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", department);
  formData.append("subfolder", subfolder);
  const res = await fetch(`${API_BASE}/files/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new ApiError(res.status, "Upload failed");
  return res.json();
}

// ─── Departments ─────────────────────────────────────────────────────────────

export async function getDepartments(): Promise<TreeNode[]> {
  return apiGet<TreeNode[]>("/departments");
}

export async function createFolder(department: string, name: string): Promise<void> {
  await apiPost("/departments/folders", { department, name });
}

export async function deleteFolder(department: string, name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/departments/folders`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ department, name }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, text || `DELETE /departments/folders failed (${res.status})`);
  }
}

// ─── Sync ────────────────────────────────────────────────────────────────────

export async function triggerSync(): Promise<SyncResult> {
  return apiPost<SyncResult>("/sync");
}

export async function triggerSyncSingle(fileId: number): Promise<SyncResult> {
  return apiPost<SyncResult>(`/sync/${fileId}`);
}

export async function getIndexStatus(): Promise<IndexStatus> {
  return apiGet<IndexStatus>("/sync/status");
}

export async function toggleAutoSync(): Promise<{ autoSync: boolean }> {
  return apiPost("/sync/toggle");
}

export async function getSyncLogs(): Promise<SyncLog[]> {
  return apiGet<SyncLog[]>("/sync/logs");
}

// ─── Embeddings ──────────────────────────────────────────────────────────────

export async function getEmbeddingLogs(): Promise<EmbeddingLog[]> {
  return apiGet<EmbeddingLog[]>("/embeddings/logs");
}

export async function getGraphData(): Promise<GraphData> {
  return apiGet<GraphData>("/graph");
}

export async function createRelationship(
  sourceFileId: number,
  targetFileId: number,
  type: string
): Promise<Relationship> {
  return apiPost<Relationship>("/graph/relationships", {
    sourceFileId,
    targetFileId,
    relationshipType: type,
  });
}

export async function updateRelationship(id: number, type: string): Promise<Relationship> {
  return apiPatch<Relationship>(`/graph/relationships/${id}`, { relationshipType: type });
}

export async function deleteRelationship(id: number): Promise<void> {
  await apiDelete(`/graph/relationships/${id}`);
}

export interface AutoReferenceSuggestion {
  id: string;
  source: string;
  target: string;
  label: string;
  type: string;
}

export interface AutoReferenceResponse {
  suggestions: AutoReferenceSuggestion[];
  total_found: number;
}

export async function autoReference(): Promise<AutoReferenceResponse> {
  return apiPost<AutoReferenceResponse>("/graph/auto-reference");
}

export async function acceptSuggestion(
  sourceId: number,
  targetId: number,
  relationshipType: string
): Promise<Relationship> {
  return apiPost<Relationship>("/graph/relationships", {
    source_id: sourceId,
    target_id: targetId,
    relationship_type: relationshipType,
  });
}

// ─── Embedding Jobs ──────────────────────────────────────────────────────────

export async function runIncrementalEmbedding(): Promise<EmbeddingJobResult> {
  return apiPost<EmbeddingJobResult>("/embeddings/run");
}

export async function runFullEmbedding(): Promise<EmbeddingJobResult> {
  return apiPost<EmbeddingJobResult>("/embeddings/run/full");
}

export async function runFileEmbedding(fileId: number): Promise<EmbeddingJobResult> {
  return apiPost<EmbeddingJobResult>(`/embeddings/run/${fileId}`);
}

export async function getEmbeddingStatus(): Promise<EmbeddingStatus> {
  return apiGet<EmbeddingStatus>("/embeddings/status");
}

// ─── Search ──────────────────────────────────────────────────────────────────

/**
 * Maps a raw snake_case chunk from the backend to the camelCase ChunkResult type.
 */
function mapChunkResult(raw: Record<string, unknown>): import("../types").ChunkResult {
  return {
    text: raw.text as string,
    score: raw.score as number,
    fileId: (raw.file_id ?? raw.fileId) as number,
    fileName: (raw.file_name ?? raw.fileName) as string,
    department: raw.department as string,
    filePath: (raw.file_path ?? raw.filePath) as string,
    chunkIndex: (raw.chunk_index ?? raw.chunkIndex) as number,
    entities: (raw.entities ?? []) as Record<string, unknown>[],
    relationships: (raw.relationships ?? []) as Record<string, unknown>[],
  };
}

/**
 * Maps a raw snake_case community result from the backend to CommunityResult.
 */
function mapCommunityResult(raw: Record<string, unknown>): import("../types").CommunityResult {
  return {
    communityId: (raw.community_id ?? raw.communityId) as number,
    level: raw.level as number,
    summary: raw.summary as string,
    relevanceScore: (raw.relevance_score ?? raw.relevanceScore) as number,
    memberEntities: (raw.member_entities ?? raw.memberEntities ?? []) as Record<string, unknown>[],
    documentReferences: (raw.document_references ?? raw.documentReferences ?? []) as Record<string, unknown>[],
  };
}

/**
 * Maps a raw snake_case source attribution from the backend.
 */
function mapSourceAttribution(raw: Record<string, unknown>): Record<string, unknown> {
  return {
    fileId: (raw.file_id ?? raw.fileId) as number,
    fileName: (raw.file_name ?? raw.fileName) as string,
    department: raw.department as string,
    chunkIndex: (raw.chunk_index ?? raw.chunkIndex) as number,
    ...raw,
  };
}

/**
 * Maps a raw snake_case search response from the backend to the camelCase SearchResponse type.
 */
function mapSearchResponse(raw: Record<string, unknown>): SearchResponse {
  const chunks = ((raw.chunks ?? []) as Record<string, unknown>[]).map(mapChunkResult);
  const communitySummaries = ((raw.community_summaries ?? raw.communitySummaries ?? []) as Record<string, unknown>[]).map(mapCommunityResult);
  const sourceAttributions = ((raw.source_attributions ?? raw.sourceAttributions ?? []) as Record<string, unknown>[]).map(mapSourceAttribution);
  const rawMeta = (raw.metadata ?? {}) as Record<string, unknown>;
  const metadata = {
    queryTimeMs: (rawMeta.query_time_ms ?? rawMeta.queryTimeMs ?? 0) as number,
    totalChunksSearched: (rawMeta.total_chunks_searched ?? rawMeta.totalChunksSearched ?? 0) as number,
    retrievalMode: (rawMeta.retrieval_mode ?? rawMeta.retrievalMode ?? "combined") as string,
  };

  return {
    chunks,
    entities: (raw.entities ?? []) as Record<string, unknown>[],
    relationships: (raw.relationships ?? []) as Record<string, unknown>[],
    communitySummaries,
    sourceAttributions,
    metadata,
  };
}

export async function localSearch(body: LocalSearchRequest): Promise<SearchResponse> {
  const raw = await apiPost<Record<string, unknown>>("/search/local", {
    query: body.query,
    top_k: body.topK,
    min_score: body.minScore,
    similarity_weight: body.similarityWeight,
  });
  return mapSearchResponse(raw);
}

export async function globalSearch(body: GlobalSearchRequest): Promise<SearchResponse> {
  const raw = await apiPost<Record<string, unknown>>("/search/global", {
    query: body.query,
    num_communities: body.numCommunities,
    min_relevance: body.minRelevance,
  });
  return mapSearchResponse(raw);
}

export async function combinedSearch(body: CombinedSearchRequest): Promise<SearchResponse> {
  const raw = await apiPost<Record<string, unknown>>("/search/combined", {
    query: body.query,
    max_tokens: body.maxTokens,
    top_k: body.topK,
    num_communities: body.numCommunities,
  });
  return mapSearchResponse(raw);
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export async function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>("/chat", body);
}

export async function* streamChatMessage(
  body: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Stream request failed: ${response.status}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        const data = JSON.parse(line.slice(6));
        yield { type: currentEvent, data } as SSEEvent;
        currentEvent = "";
      }
    }
  }
}

// ─── Session API ─────────────────────────────────────────────────────────────

export async function getSessions(params?: {
  page?: number;
  page_size?: number;
}): Promise<PaginatedSessionsResponse> {
  const queryParams: Record<string, string> = {};
  if (params?.page) queryParams.page = String(params.page);
  if (params?.page_size) queryParams.page_size = String(params.page_size);
  const raw = await apiGet<{ items: Array<Record<string, unknown>>; total: number; has_more: boolean }>("/sessions", Object.keys(queryParams).length > 0 ? queryParams : undefined);
  // Map snake_case fields from backend to camelCase
  const items: ChatSessionSummary[] = raw.items.map((item) => ({
    id: item.id as string,
    title: (item.title as string | null) ?? null,
    retrievalMode: (item.retrieval_mode as string | null) ?? null,
    topK: (item.top_k as number | null) ?? null,
    maxTokens: (item.max_tokens as number | null) ?? null,
    createdAt: (item.created_at as string | null) ?? null,
    updatedAt: (item.updated_at as string | null) ?? null,
  }));
  return { items, total: raw.total, has_more: raw.has_more };
}

export async function getSession(sessionId: string): Promise<ChatSessionDetail> {
  return apiGet<ChatSessionDetail>(`/sessions/${sessionId}`);
}

export async function saveSession(body: SaveSessionRequest): Promise<ChatSessionSummary> {
  return apiPost<ChatSessionSummary>("/sessions", body);
}

export async function updateSessionTitle(
  sessionId: string,
  title: string
): Promise<ChatSessionSummary> {
  return apiPatch<ChatSessionSummary>(`/sessions/${sessionId}/title`, { title });
}

export async function deleteSession(sessionId: string): Promise<void> {
  await apiDelete(`/sessions/${sessionId}`);
}
