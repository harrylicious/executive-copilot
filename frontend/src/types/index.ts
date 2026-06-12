// ─── File Types ──────────────────────────────────────────────────────────────

export interface FileNode {
  id: number;
  name: string;
  path: string;
  department: string;
  subfolder?: string;
  fileType?: string;
  size: number;
  tags: string[];
  createdAt: string;
  modifiedAt: string;
  indexedAt?: string;
  syncStatus?: string;
  sensitivityLevel?: string;
  isDeleted?: boolean;
}

export interface TreeNode {
  id: string;
  name: string;
  type: "department" | "folder" | "file";
  children?: TreeNode[];
  fileId?: number;
  color?: string;
  description?: string;
  outputs?: string[];
  sensitivity?: string;
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
  pendingCount?: number;
}

export type ViewMode = "viewer" | "graph" | "search";

export type SearchMode = "local" | "global" | "combined";

export interface EmbeddingJobResult {
  jobId: number;
  filesProcessed: number;
  chunksGenerated: number;
  errors: { fileId: number; filePath: string; error: string }[];
  status: string;
}

export interface EmbeddingStatus {
  totalFilesEmbedded: number;
  filesPending: number;
  lastJobTimestamp: string | null;
}

export interface LocalSearchRequest {
  query: string;
  topK?: number;
  minScore?: number;
  similarityWeight?: number;
}

export interface GlobalSearchRequest {
  query: string;
  numCommunities?: number;
  minRelevance?: number;
}

export interface CombinedSearchRequest {
  query: string;
  maxTokens?: number;
  topK?: number;
  numCommunities?: number;
}

export interface ChunkResult {
  text: string;
  score: number;
  fileId: number;
  fileName: string;
  department: string;
  filePath: string;
  chunkIndex: number;
  entities: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
}

export interface CommunityResult {
  communityId: number;
  level: number;
  summary: string;
  relevanceScore: number;
  memberEntities: Record<string, unknown>[];
  documentReferences: Record<string, unknown>[];
}

export interface SearchResponse {
  chunks: ChunkResult[];
  entities: Record<string, unknown>[];
  relationships: Record<string, unknown>[];
  communitySummaries: CommunityResult[];
  sourceAttributions: Record<string, unknown>[];
  metadata: {
    queryTimeMs: number;
    totalChunksSearched: number;
    retrievalMode: string;
  };
}

export interface SyncLog {
  id: number;
  timestamp: string;
  filesAdded: number;
  filesUpdated: number;
  filesRemoved: number;
  status: string;
  summary: string | null;
}

export interface EmbeddingLog {
  id: number;
  timestamp: string;
  filesProcessed: number;
  chunksGenerated: number;
  errorsCount: number;
  status: string;
}

export type SupportedFormat = "pdf" | "xlsx" | "json" | "docx" | "md" | "txt" | "csv";

// ─── Chat Types ──────────────────────────────────────────────────────────────

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming: boolean;
  isComplete: boolean;
  sources?: SourceAttribution[];
  metadata?: RetrievalMetadata;
  suggestions?: string[];
  error?: string;
  timestamp: number;
}

export interface SourceAttribution {
  fileId: number;
  fileName: string;
  department: string;
  chunkIndex: number;
}

export interface RetrievalMetadata {
  retrievalMode: string;
  documentsRetrieved: number;
  queryTimeMs?: number;
  tokenUsage?: TokenUsage;
}

export interface TokenUsage {
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
}

export interface ChatRequest {
  query: string;
  sessionId?: string;
  retrievalMode?: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
  language?: "id" | "en";
}

export interface ChatResponse {
  answer: string;
  sourceAttributions: SourceAttribution[];
  retrievalMetadata: RetrievalMetadata;
  tokenUsage: TokenUsage;
  responseType: string;
  stepLimitReached: boolean;
}

export type SSEEvent =
  | { type: "token"; data: { content: string } }
  | { type: "sources"; data: { sourceAttributions: SourceAttribution[] } }
  | { type: "metadata"; data: RetrievalMetadata & { tokenUsage: TokenUsage } }
  | { type: "suggestions"; data: { suggestions: string[] } }
  | { type: "done"; data: Record<string, never> }
  | { type: "error"; data: { message: string } };

export interface ChatConfig {
  retrievalMode: "local" | "global" | "combined";
  topK?: number;
  maxTokens?: number;
  language: "id" | "en";
}

// ─── Session Types ───────────────────────────────────────────────────────────

export interface ChatSessionSummary {
  id: string;
  title: string | null;
  retrievalMode: string | null;
  topK: number | null;
  maxTokens: number | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface PaginatedSessionsResponse {
  items: ChatSessionSummary[];
  total: number;
  has_more: boolean;
}

export interface ChatSessionDetail extends ChatSessionSummary {
  messages: ChatMessageRecord[];
}

export interface ChatMessageRecord {
  id: string;
  sessionId: string;
  role: "user" | "assistant";
  content: string;
  sources?: SourceAttribution[] | null;
  metadataJson?: RetrievalMetadata | null;
  error?: string | null;
  timestamp: number;
}

export interface SaveSessionRequest {
  id: string;
  title?: string | null;
  retrievalMode?: string | null;
  topK?: number | null;
  maxTokens?: number | null;
  messages: ChatMessageRecord[];
}
