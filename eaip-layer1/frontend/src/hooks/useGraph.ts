import { useState, useEffect, useCallback } from "react";
import type { GraphData } from "../types";
import {
  getGraphData,
  createRelationship,
  deleteRelationship,
} from "../api/client";

interface UseGraphReturn {
  graphData: GraphData | null;
  loading: boolean;
  error: string | null;
  fetchGraph: () => Promise<void>;
  addRelationship: (
    sourceFileId: number,
    targetFileId: number,
    type: string
  ) => Promise<void>;
  removeRelationship: (id: number) => Promise<void>;
}

export function useGraph(): UseGraphReturn {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getGraphData();
      setGraphData(data);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load graph data";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const addRelationship = useCallback(
    async (sourceFileId: number, targetFileId: number, type: string) => {
      setError(null);
      try {
        await createRelationship(sourceFileId, targetFileId, type);
        await fetchGraph();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to create relationship";
        setError(message);
      }
    },
    [fetchGraph]
  );

  const removeRelationship = useCallback(
    async (id: number) => {
      setError(null);
      try {
        await deleteRelationship(id);
        await fetchGraph();
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to delete relationship";
        setError(message);
      }
    },
    [fetchGraph]
  );

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  return {
    graphData,
    loading,
    error,
    fetchGraph,
    addRelationship,
    removeRelationship,
  };
}

export default useGraph;
