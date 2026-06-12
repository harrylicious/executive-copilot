import { apiGet, apiDelete, apiUpload } from "./client";

export interface BackendFile {
  id: number;
  name: string;
  path: string;
  department: string;
  subfolder: string | null;
  file_type: string | null;
  size: number;
  tags: string[];
  created_at: string;
  modified_at: string;
  indexed_at: string | null;
  sync_status: string | null;
  sensitivity_level: string | null;
  is_deleted: boolean;
}

export async function fetchFiles(params?: {
  department?: string;
  subfolder?: string;
  file_type?: string;
  sync_status?: string;
}): Promise<BackendFile[]> {
  return apiGet<BackendFile[]>("/files", params as Record<string, string> | undefined);
}

export async function uploadFile(
  file: File,
  department: string,
  subfolder: string
): Promise<BackendFile> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("department", department);
  formData.append("subfolder", subfolder);
  return apiUpload<BackendFile>("/files/upload", formData);
}

export async function deleteFile(fileId: number): Promise<void> {
  return apiDelete(`/files/${fileId}`);
}

export function getFileContentUrl(fileId: number): string {
  return `/api/files/${fileId}/content`;
}
