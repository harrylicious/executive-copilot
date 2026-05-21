import { useCallback } from "react";
import { useNavigate } from "react-router-dom";
import KnowledgeGraph from "../components/KnowledgeGraph/KnowledgeGraph";
import useGraph from "../hooks/useGraph";
import { Loader2 } from "lucide-react";

export function GraphPage() {
  const navigate = useNavigate();
  const {
    graphData,
    loading: graphLoading,
    error: graphError,
    addRelationship,
    removeRelationship,
    fetchGraph,
  } = useGraph();

  const handleGraphNodeSelect = useCallback(
    (fileId: number) => {
      navigate(`/?fileId=${fileId}`);
    },
    [navigate]
  );

  if (graphLoading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground gap-2">
        <Loader2 className="size-4 animate-spin" />
        <span className="text-sm">Loading graph...</span>
      </div>
    );
  }

  if (graphError) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-sm">
        <span className="text-destructive">Failed to load graph</span>
        <span className="text-muted-foreground text-xs">{graphError}</span>
        <button
          onClick={fetchGraph}
          className="text-primary text-xs hover:underline mt-1"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!graphData || (graphData.nodes.length === 0)) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
        No graph data available. Sync some files first.
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <KnowledgeGraph
        data={graphData}
        onNodeSelect={handleGraphNodeSelect}
        onCreateRelationship={addRelationship}
        onDeleteRelationship={removeRelationship}
      />
    </div>
  );
}

export default GraphPage;
