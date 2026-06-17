import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import type { WSMessage } from "./useWebSocket";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface FileStatus {
  id: number;
  name: string;
  path: string;
  department: string;
  embedding_status: string | null;
  current_version: number | null;
  modified_at: string;
  file_size: number;
}

export interface FileVersion {
  version_number: number;
  content_hash: string;
  file_size: number;
  timestamp: string;
  is_restore: boolean;
  restored_from_version: number | null;
}

export interface EmbeddingStatus {
  pending: number;
  embedding: number;
  embedded: number;
  failed: number;
  stale: number;
}

export interface ActivityEvent {
  id: number;
  timestamp: string;
  event_type: string;
  file_name: string | null;
  actor: string;
  details: Record<string, unknown> | null;
}

export interface PaginatedFiles {
  files: FileStatus[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaginatedVersions {
  versions: FileVersion[];
  total: number;
  page: number;
  page_size: number;
}

export interface UseMonitoringDataResult {
  // File list
  files: FileStatus[];
  filesTotalCount: number;
  filesPage: number;
  filesLoading: boolean;
  filesError: string | null;
  loadFiles: (page?: number) => Promise<void>;

  // Versions
  versions: FileVersion[];
  versionsTotalCount: number;
  versionsPage: number;
  versionsLoading: boolean;
  versionsError: string | null;
  loadVersions: (fileId: number, page?: number) => Promise<void>;

  // Embedding status
  embeddingStatus: EmbeddingStatus | null;
  embeddingStatusLoading: boolean;
  embeddingStatusError: string | null;
  loadEmbeddingStatus: () => Promise<void>;

  // Activity
  activity: ActivityEvent[];
  activityLoading: boolean;
  activityError: string | null;
  loadActivity: () => Promise<void>;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const API_BASE = "/api";
const FILES_PAGE_SIZE = 25;
const VERSIONS_PAGE_SIZE = 50;

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useMonitoringData(
  messages: WSMessage[] = []
): UseMonitoringDataResult {
  // ── File list state ──
  const [files, setFiles] = useState<FileStatus[]>([]);
  const [filesTotalCount, setFilesTotalCount] = useState(0);
  const [filesPage, setFilesPage] = useState(1);
  const [filesLoading, setFilesLoading] = useState(false);
  const [filesError, setFilesError] = useState<string | null>(null);

  // ── Versions state ──
  const [versions, setVersions] = useState<FileVersion[]>([]);
  const [versionsTotalCount, setVersionsTotalCount] = useState(0);
  const [versionsPage, setVersionsPage] = useState(1);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);

  // ── Embedding status state ──
  const [embeddingStatus, setEmbeddingStatus] =
    useState<EmbeddingStatus | null>(null);
  const [embeddingStatusLoading, setEmbeddingStatusLoading] = useState(false);
  const [embeddingStatusError, setEmbeddingStatusError] = useState<
    string | null
  >(null);

  // ── Activity state ──
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [activityLoading, setActivityLoading] = useState(false);
  const [activityError, setActivityError] = useState<string | null>(null);

  // ── Load files ──
  const loadFiles = useCallback(async (page: number = 1) => {
    setFilesLoading(true);
    setFilesError(null);
    try {
      const res = await axios.get<PaginatedFiles>(
        `${API_BASE}/monitoring/files`,
        { params: { page, page_size: FILES_PAGE_SIZE } }
      );
      setFiles(res.data.files ?? []);
      setFilesTotalCount(res.data.total ?? 0);
      setFilesPage(page);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load files";
      setFilesError(message);
    } finally {
      setFilesLoading(false);
    }
  }, []);

  // ── Load versions ──
  const loadVersions = useCallback(
    async (fileId: number, page: number = 1) => {
      setVersionsLoading(true);
      setVersionsError(null);
      try {
        const res = await axios.get<PaginatedVersions>(
          `${API_BASE}/monitoring/files/${fileId}/versions`,
          { params: { page, page_size: VERSIONS_PAGE_SIZE } }
        );
        setVersions(res.data.versions);
        setVersionsTotalCount(res.data.total);
        setVersionsPage(page);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to load versions";
        setVersionsError(message);
      } finally {
        setVersionsLoading(false);
      }
    },
    []
  );

  // ── Load embedding status ──
  const loadEmbeddingStatus = useCallback(async () => {
    setEmbeddingStatusLoading(true);
    setEmbeddingStatusError(null);
    try {
      const res = await axios.get<EmbeddingStatus>(
        `${API_BASE}/monitoring/embedding-status`
      );
      setEmbeddingStatus(res.data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load embedding status";
      setEmbeddingStatusError(message);
    } finally {
      setEmbeddingStatusLoading(false);
    }
  }, []);

  // ── Load activity ──
  const loadActivity = useCallback(async () => {
    setActivityLoading(true);
    setActivityError(null);
    try {
      const res = await axios.get<ActivityEvent[]>(
        `${API_BASE}/monitoring/activity`
      );
      setActivity(res.data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load activity";
      setActivityError(message);
    } finally {
      setActivityLoading(false);
    }
  }, []);

  // ── Auto-refresh on WebSocket status_changed events ──
  useEffect(() => {
    if (messages.length === 0) return;
    const latest = messages[messages.length - 1];
    if (latest.event_type === "status_changed") {
      // Refresh embedding status and file list when a status change occurs
      loadEmbeddingStatus();
      loadFiles(filesPage);
    }
  }, [messages, loadEmbeddingStatus, loadFiles, filesPage]);

  return {
    files,
    filesTotalCount,
    filesPage,
    filesLoading,
    filesError,
    loadFiles,

    versions,
    versionsTotalCount,
    versionsPage,
    versionsLoading,
    versionsError,
    loadVersions,

    embeddingStatus,
    embeddingStatusLoading,
    embeddingStatusError,
    loadEmbeddingStatus,

    activity,
    activityLoading,
    activityError,
    loadActivity,
  };
}
