import { useState, useCallback } from "react";
import axios from "axios";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface DiffOperation {
  operation: string;
  line_number: number;
  content: string;
  old_content: string | null;
}

export interface DiffSummary {
  lines_added: number;
  lines_deleted: number;
  lines_modified: number;
}

export interface DiffResult {
  operations: DiffOperation[];
  summary: DiffSummary;
}

export interface UseVersionDiffResult {
  diff: DiffResult | null;
  loading: boolean;
  error: string | null;
  loadDiff: (fileId: number, versionA: number, versionB: number) => Promise<void>;
  clearDiff: () => void;
}

// ─── Constants ───────────────────────────────────────────────────────────────

const API_BASE = "/api";

// ─── Hook ────────────────────────────────────────────────────────────────────

export function useVersionDiff(): UseVersionDiffResult {
  const [diff, setDiff] = useState<DiffResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDiff = useCallback(
    async (fileId: number, versionA: number, versionB: number) => {
      setLoading(true);
      setError(null);
      setDiff(null);
      try {
        const res = await axios.post<DiffResult>(
          `${API_BASE}/monitoring/files/${fileId}/versions/diff`,
          { version_a: versionA, version_b: versionB }
        );
        setDiff(res.data);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to compute diff";
        setError(message);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const clearDiff = useCallback(() => {
    setDiff(null);
    setError(null);
  }, []);

  return {
    diff,
    loading,
    error,
    loadDiff,
    clearDiff,
  };
}
