import { useState, useEffect, useCallback, useRef } from "react";
import {
  getDashboardAnalytics,
  type DashboardAnalytics,
} from "../api/dashboard";

interface UseDashboardReturn {
  data: DashboardAnalytics | null;
  loading: boolean;
  error: string | null;
  isStale: boolean;
  refetch: () => void;
}

export function useDashboard(): UseDashboardReturn {
  const [data, setData] = useState<DashboardAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isStale, setIsStale] = useState(false);
  const cachedData = useRef<DashboardAnalytics | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const timeout = new Promise<never>((_, reject) =>
        setTimeout(() => reject(new Error("Request timed out")), 10000)
      );
      const result = await Promise.race([getDashboardAnalytics(), timeout]);
      cachedData.current = result;
      setData(result);
      setIsStale(false);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load dashboard analytics";

      if (cachedData.current) {
        setData(cachedData.current);
        setIsStale(true);
      }

      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  return { data, loading, error, isStale, refetch: fetchAnalytics };
}

export default useDashboard;
