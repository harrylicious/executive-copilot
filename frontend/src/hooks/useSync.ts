import { useState, useEffect, useCallback } from "react";
import type { SyncResult, IndexStatus } from "../types";
import { triggerSync as apiTriggerSync, getIndexStatus } from "../api/kb";

interface UseSyncReturn {
  isSyncing: boolean;
  lastResult: SyncResult | null;
  indexStatus: IndexStatus | null;
  error: string | null;
  triggerSync: () => Promise<void>;
  fetchStatus: () => Promise<void>;
}

export function useSync(): UseSyncReturn {
  const [isSyncing, setIsSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<SyncResult | null>(null);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const status = await getIndexStatus();
      setIndexStatus(status);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to fetch index status";
      setError(message);
    }
  }, []);

  const triggerSync = useCallback(async () => {
    setIsSyncing(true);
    setError(null);
    try {
      const result = await apiTriggerSync();
      setLastResult(result);
      await fetchStatus();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Sync failed";
      setError(message);
    } finally {
      setIsSyncing(false);
    }
  }, [fetchStatus]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return { isSyncing, lastResult, indexStatus, error, triggerSync, fetchStatus };
}

export default useSync;
