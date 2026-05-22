import axios from "axios";
import type {
  BatchLoaderConfig,
  BatchLoaderConfigCreate,
  BatchUploadResponse,
  IngestionJob,
  IngestionJobListParams,
  IngestionJobListResponse,
  UploadResponse,
} from "../types/ingestion";

// ─── Shared Axios Instance ───────────────────────────────────────────────────

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
  if (config.params) {
    config.params = transformKeys(config.params, camelToSnake);
  }
  return config;
});

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
  const { data } = await api.post<UploadResponse>(
    "/api/ingestion/upload",
    formData
  );
  return data;
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
  const { data } = await api.post<BatchUploadResponse>(
    "/api/ingestion/upload/batch",
    formData
  );
  return data;
}

// ─── Jobs API ────────────────────────────────────────────────────────────────

export async function getJobs(
  params?: IngestionJobListParams
): Promise<IngestionJobListResponse> {
  const { data } = await api.get<IngestionJobListResponse>(
    "/api/ingestion/jobs",
    { params }
  );
  return data;
}

export async function getJobDetail(jobId: string): Promise<IngestionJob> {
  const { data } = await api.get<IngestionJob>(
    `/api/ingestion/jobs/${jobId}`
  );
  return data;
}

// ─── Batch Loader Config API ─────────────────────────────────────────────────

export async function getBatchConfigs(): Promise<BatchLoaderConfig[]> {
  const { data } = await api.get<BatchLoaderConfig[]>(
    "/api/ingestion/batch-configs"
  );
  return data;
}

export async function createBatchConfig(
  config: BatchLoaderConfigCreate
): Promise<BatchLoaderConfig> {
  const { data } = await api.post<BatchLoaderConfig>(
    "/api/ingestion/batch-configs",
    config
  );
  return data;
}
