import axios from "axios";
import type {
  ChatRequest,
  ChatResponse,
  ChatSessionDetail,
  ChatSessionSummary,
  CombinedSearchRequest,
  EmbeddingJobResult,
  EmbeddingLog,
  EmbeddingStatus,
  FileNode,
  GlobalSearchRequest,
  GraphData,
  IndexStatus,
  LocalSearchRequest,
  Relationship,
  SaveSessionRequest,
  SearchResponse,
  SSEEvent,
  SyncLog,
  SyncResult,
  TreeNode,
} from "../types";

function snakeToCamel(str: string): string {
  return str.replace(/_([a-z])/g, (_, char) => char.toUpperCase());
}

function camelToSnake(str: string): string {
  return str.replace(/[A-Z]/g, (char) => `_${char.toLowerCase()}`);
}

function transformKeys(
  obj: unknown,
  transformer: (key: string) => string
): unknown {
  if (Array.isArray(obj)) {
    return obj.map((item) => transformKeys(item, transformer));
  }
  if (obj !== null && typeof obj === "object") {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([key, value]) => [
        transformer(key),
        transformKeys(value, transformer),
      ])
    );
  }
  return obj;
}

const api = axios.create({
  baseURL: "",
  headers: { "Content-Type": "application/json" },
});

api.interceptors.response.use((response) => {
  if (response.data) {
    response.data = transformKeys(response.data, snakeToCamel);
  }
  return response;
});

api.interceptors.request.use((config) => {
  if (config.data && !(config.data instanceof FormData)) {
    config.data = transformKeys(config.data, camelToSnake);
  }
  return config;
});

export async function getFiles(params?: {
  department?: string;
  subfolder?: string;
  fileType?: string;
  syncStatus?: string;
}): Promise<FileNode[]> {
  const { data } = await api.get<FileNode[]>("/api/files", { params });
  return data;
}

export async function getFile(id: number): Promise<FileNode> {
  const { data } = await api.get<FileNode>(`/api/files/${id}`);
  return data;
}

export function getFileContentUrl(id: number): string {
  return `/api/files/${id}/content`;
}

export async function revealFileInExplorer(id: number): Promise<void> {
  await api.post(`/api/files/${id}/reveal`);
}

export async function updateFileTags(
  id: number,
  tags: string[]
): Promise<FileNode> {
  const { data } = await api.patch<FileNode>(`/api/files/${id}/tags`, { tags });
  return data;
}

export async function deleteFile(id: number): Promise<void> {
  await api.delete(`/api/files/${id}`);
}

export async function removeFileFromIndex(id: number): Promise<void> {
  await api.delete(`/api/files/${id}/index`);
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
  const { data } = await api.post<FileNode>("/api/files/upload", formData);
  return data;
}

export async function getDepartments(): Promise<TreeNode[]> {
  const { data } = await api.get<TreeNode[]>("/api/departments");
  return data;
}

export async function triggerSync(): Promise<SyncResult> {
  const { data } = await api.post<SyncResult>("/api/sync");
  return data;
}

export async function triggerSyncSingle(fileId: number): Promise<SyncResult> {
  const { data } = await api.post<SyncResult>(`/api/sync/${fileId}`);
  return data;
}

export async function getIndexStatus(): Promise<IndexStatus> {
  const { data } = await api.get<IndexStatus>("/api/sync/status");
  return data;
}

export async function toggleAutoSync(): Promise<{ autoSync: boolean }> {
  const { data } = await api.post("/api/sync/toggle");
  return data;
}

export async function getSyncLogs(): Promise<SyncLog[]> {
  const { data } = await api.get<SyncLog[]>("/api/sync/logs");
  return data;
}

export async function getEmbeddingLogs(): Promise<EmbeddingLog[]> {
  const { data } = await api.get<EmbeddingLog[]>("/api/embeddings/logs");
  return data;
}

export async function getGraphData(): Promise<GraphData> {
  const { data } = await api.get<GraphData>("/api/graph");
  return data;
}

export async function createRelationship(
  sourceFileId: number,
  targetFileId: number,
  type: string
): Promise<Relationship> {
  const { data } = await api.post<Relationship>("/api/graph/relationships", {
    sourceFileId,
    targetFileId,
    relationshipType: type,
  });
  return data;
}

export async function updateRelationship(
  id: number,
  type: string
): Promise<Relationship> {
  const { data } = await api.put<Relationship>(
    `/api/graph/relationships/${id}`,
    { relationshipType: type }
  );
  return data;
}

export async function deleteRelationship(id: number): Promise<void> {
  await api.delete(`/api/graph/relationships/${id}`);
}

export async function runIncrementalEmbedding(): Promise<EmbeddingJobResult> {
  const { data } = await api.post<EmbeddingJobResult>("/api/embeddings/run");
  return data;
}

export async function runFullEmbedding(): Promise<EmbeddingJobResult> {
  const { data } = await api.post<EmbeddingJobResult>("/api/embeddings/run/full");
  return data;
}

export async function runFileEmbedding(fileId: number): Promise<EmbeddingJobResult> {
  const { data } = await api.post<EmbeddingJobResult>(`/api/embeddings/run/${fileId}`);
  return data;
}

export async function getEmbeddingStatus(): Promise<EmbeddingStatus> {
  const { data } = await api.get<EmbeddingStatus>("/api/embeddings/status");
  return data;
}

export async function localSearch(body: LocalSearchRequest): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>("/api/search/local", body);
  return data;
}

export async function globalSearch(body: GlobalSearchRequest): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>("/api/search/global", body);
  return data;
}

export async function combinedSearch(body: CombinedSearchRequest): Promise<SearchResponse> {
  const { data } = await api.post<SearchResponse>("/api/search/combined", body);
  return data;
}

export async function sendChatMessage(body: ChatRequest): Promise<ChatResponse> {
  const { data } = await api.post<ChatResponse>("/api/chat", body);
  return data;
}

export async function* streamChatMessage(
  body: ChatRequest,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const requestBody = transformKeys(body, camelToSnake);

  const response = await fetch("/api/chat/stream", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(requestBody),
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
        const rawData = JSON.parse(line.slice(6));
        const data = transformKeys(rawData, snakeToCamel) as SSEEvent["data"];
        yield { type: currentEvent, data } as SSEEvent;
        currentEvent = "";
      }
    }
  }
}

// ─── Session API ─────────────────────────────────────────────────────────────

export async function getSessions(): Promise<ChatSessionSummary[]> {
  const { data } = await api.get<ChatSessionSummary[]>("/api/sessions");
  return data;
}

export async function getSession(sessionId: string): Promise<ChatSessionDetail> {
  const { data } = await api.get<ChatSessionDetail>(`/api/sessions/${sessionId}`);
  return data;
}

export async function saveSession(body: SaveSessionRequest): Promise<ChatSessionSummary> {
  const { data } = await api.post<ChatSessionSummary>("/api/sessions", body);
  return data;
}

export async function updateSessionTitle(
  sessionId: string,
  title: string
): Promise<ChatSessionSummary> {
  const { data } = await api.patch<ChatSessionSummary>(
    `/api/sessions/${sessionId}/title`,
    { title }
  );
  return data;
}

export async function deleteSession(sessionId: string): Promise<void> {
  await api.delete(`/api/sessions/${sessionId}`);
}
