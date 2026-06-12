// ─── Ingestion Pipeline Types ────────────────────────────────────────────────

export type IngestionJobStatus =
  | "queued"
  | "validating"
  | "preprocessing"
  | "chunking"
  | "embedding"
  | "completed"
  | "failed"
  | "validation_failed"
  | "duplicate_exact"
  | "duplicate_near"
  | "access_denied";

export type StageStatus = "started" | "completed" | "failed";

export interface StageLog {
  stage: string;
  status: StageStatus;
  startedAt: string;
  completedAt: string | null;
  details: Record<string, unknown> | null;
}

export interface IngestionJob {
  id: string;
  fileName: string;
  fileSize: number;
  department: string;
  subfolder: string | null;
  status: IngestionJobStatus;
  currentStage: string | null;
  errorCode: string | null;
  errorMessage: string | null;
  failureStage: string | null;
  contentHash: string | null;
  sensitivityLevel: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  stages: StageLog[];
}

export interface IngestionJobListResponse {
  jobs: IngestionJob[];
  total: number;
  page: number;
  pageSize: number;
}

export interface IngestionJobListParams {
  status?: IngestionJobStatus;
  department?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface UploadResponse {
  jobId: string;
  fileName: string;
  status: string;
  createdAt: string;
}

export interface BatchUploadResponse {
  jobs: UploadResponse[];
}

// ─── Batch Loader Types ──────────────────────────────────────────────────────

export type BatchSourceType = "local" | "s3";

export type BatchExecutionStatus = "running" | "completed" | "failed";

export interface BatchLoaderConfig {
  id: string;
  name: string;
  sourcePath: string;
  sourceType: BatchSourceType;
  cronExpression: string;
  department: string;
  subfolder: string | null;
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
  lastExecutionAt: string | null;
  lastExecutionStatus: string | null;
  nextExecutionAt: string | null;
}

export interface BatchLoaderConfigCreate {
  name: string;
  sourcePath: string;
  sourceType: BatchSourceType;
  cronExpression: string;
  department: string;
  subfolder?: string | null;
}

export interface BatchExecutionLog {
  id: number;
  configId: string;
  startedAt: string;
  completedAt: string | null;
  filesFound: number;
  filesSubmitted: number;
  filesSkipped: number;
  errors: Record<string, unknown>[] | null;
  status: BatchExecutionStatus;
}
