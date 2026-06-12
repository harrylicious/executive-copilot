// ─── Ingestion Pipeline API ──────────────────────────────────────────────────

import type {
  IngestionJob,
  IngestionJobListParams,
  IngestionJobListResponse,
  UploadResponse,
  BatchUploadResponse,
  BatchLoaderConfig,
  BatchLoaderConfigCreate,
} from "../types/ingestion";

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

// ─── Upload API ──────────────────────────────────────────────────────────────

export async function uploadFile(
  file: File,
  department: string,
  subfolder?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", department);
  if (subfolder) {
    formData.append("subfolder", subfolder);
  }
  const res = await fetch(`${API_BASE}/ingestion/upload`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    if (res.status === 413) {
      throw new ApiError(res.status, "File is too large. Maximum allowed size is 50MB.");
    }
    if (res.status === 422) {
      throw new ApiError(res.status, "Missing required metadata. Please select a department.");
    }
    const detail = await res.text().catch(() => "");
    throw new ApiError(res.status, detail || "Upload failed");
  }
  return res.json();
}

export async function uploadBatch(
  files: File[],
  department: string,
  subfolder?: string
): Promise<BatchUploadResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }
  formData.append("department", department);
  if (subfolder) {
    formData.append("subfolder", subfolder);
  }
  const res = await fetch(`${API_BASE}/ingestion/upload/batch`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new ApiError(res.status, "Batch upload failed");
  return res.json();
}

// ─── Jobs API ────────────────────────────────────────────────────────────────

export async function getJobs(
  params?: IngestionJobListParams
): Promise<IngestionJobListResponse> {
  return apiGet<IngestionJobListResponse>(
    "/ingestion/jobs",
    params as Record<string, string> | undefined
  );
}

export async function getJobDetail(jobId: string): Promise<IngestionJob> {
  return apiGet<IngestionJob>(`/ingestion/jobs/${jobId}`);
}

// ─── Batch Loader Config API ─────────────────────────────────────────────────

export async function getBatchConfigs(): Promise<BatchLoaderConfig[]> {
  return apiGet<BatchLoaderConfig[]>("/ingestion/batch-configs");
}

export async function createBatchConfig(
  config: BatchLoaderConfigCreate
): Promise<BatchLoaderConfig> {
  return apiPost<BatchLoaderConfig>("/ingestion/batch-configs", config);
}
