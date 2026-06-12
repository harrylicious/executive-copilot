import { useCallback, useMemo, useState } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  type Connection,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";
import { Loader2, AlertCircle, RefreshCw, Sparkles, Check, X } from "lucide-react";
import { useGraph } from "../../../hooks/useGraph";
import {
  autoReference,
  acceptSuggestion,
  type AutoReferenceSuggestion,
} from "../../../api/kb";
import GraphNode from "./GraphNode";

const nodeTypes = { graphNode: GraphNode };

interface SuggestionWithState extends AutoReferenceSuggestion {
  status: "pending" | "accepting" | "accepted" | "dismissed";
}

export function KnowledgeGraph() {
  const { graphData, loading, error, fetchGraph, addRelationship } = useGraph();

  const [suggestions, setSuggestions] = useState<SuggestionWithState[]>([]);
  const [autoRefLoading, setAutoRefLoading] = useState(false);
  const [autoRefError, setAutoRefError] = useState<string | null>(null);

  const initialNodes: Node[] = useMemo(() => {
    if (!graphData) return [];
    return graphData.nodes.map((n) => ({
      id: n.id,
      type: "graphNode",
      position: n.position,
      data: n.data,
    }));
  }, [graphData]);

  const initialEdges: Edge[] = useMemo(() => {
    if (!graphData) return [];
    return graphData.edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.label,
      type: e.type || "smoothstep",
      animated: true,
      style: { stroke: "var(--border)", strokeWidth: 1.5 },
      markerEnd: { type: MarkerType.ArrowClosed, color: "var(--border)" },
    }));
  }, [graphData]);

  // Build suggestion edges (dashed, animated, different color)
  const suggestionEdges: Edge[] = useMemo(() => {
    return suggestions
      .filter((s) => s.status === "pending" || s.status === "accepting")
      .map((s) => ({
        id: `suggestion-${s.id}`,
        source: s.source,
        target: s.target,
        label: s.label,
        type: "smoothstep",
        animated: true,
        style: {
          stroke: "#8b5cf6",
          strokeWidth: 2,
          strokeDasharray: "6 3",
          opacity: s.status === "accepting" ? 0.5 : 1,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#8b5cf6" },
      }));
  }, [suggestions]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync when graphData or suggestions change
  useMemo(() => {
    setNodes(initialNodes);
    setEdges([...initialEdges, ...suggestionEdges]);
  }, [initialNodes, initialEdges, suggestionEdges, setNodes, setEdges]);

  const onConnect = useCallback(
    async (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      try {
        await addRelationship(
          parseInt(connection.source),
          parseInt(connection.target),
          "manual"
        );
      } catch {
        // silently fail
      }
    },
    [addRelationship]
  );

  const handleAutoReference = useCallback(async () => {
    setAutoRefLoading(true);
    setAutoRefError(null);
    try {
      const response = await autoReference();
      const suggestionsWithState: SuggestionWithState[] = response.suggestions.map(
        (s) => ({ ...s, status: "pending" as const })
      );
      setSuggestions(suggestionsWithState);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to find auto-references";
      setAutoRefError(message);
    } finally {
      setAutoRefLoading(false);
    }
  }, []);

  const handleAcceptSuggestion = useCallback(
    async (suggestion: SuggestionWithState) => {
      // Mark as accepting
      setSuggestions((prev) =>
        prev.map((s) =>
          s.id === suggestion.id ? { ...s, status: "accepting" as const } : s
        )
      );

      try {
        await acceptSuggestion(
          parseInt(suggestion.source),
          parseInt(suggestion.target),
          suggestion.type || "auto_reference"
        );

        // Mark as accepted and refresh graph
        setSuggestions((prev) =>
          prev.map((s) =>
            s.id === suggestion.id ? { ...s, status: "accepted" as const } : s
          )
        );
        await fetchGraph();
      } catch {
        // Revert to pending on failure
        setSuggestions((prev) =>
          prev.map((s) =>
            s.id === suggestion.id ? { ...s, status: "pending" as const } : s
          )
        );
      }
    },
    [fetchGraph]
  );

  const handleDismissSuggestion = useCallback((suggestionId: string) => {
    setSuggestions((prev) =>
      prev.map((s) =>
        s.id === suggestionId ? { ...s, status: "dismissed" as const } : s
      )
    );
  }, []);

  const pendingSuggestions = suggestions.filter(
    (s) => s.status === "pending" || s.status === "accepting"
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full bg-card rounded-xl border border-border">
        <div className="flex flex-col items-center gap-2">
          <Loader2 size={20} className="animate-spin text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Loading graph...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full bg-card rounded-xl border border-border">
        <div className="flex flex-col items-center gap-2">
          <AlertCircle size={20} className="text-destructive" />
          <span className="text-xs text-destructive">{error}</span>
          <button
            onClick={fetchGraph}
            className="flex items-center gap-1 text-xs text-primary hover:underline mt-1"
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="flex items-center justify-center h-full bg-card rounded-xl border border-border">
        <div className="flex flex-col items-center gap-2 text-center px-4">
          <div className="w-10 h-10 rounded-xl bg-primary/5 flex items-center justify-center">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="text-muted-foreground/40">
              <circle cx="5" cy="12" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="12" cy="19" r="2"/><circle cx="19" cy="12" r="2"/>
              <line x1="7" y1="11.5" x2="10" y2="6.5"/><line x1="7" y1="12.5" x2="10" y2="17.5"/>
              <line x1="14" y1="6.5" x2="17" y2="11.5"/><line x1="14" y1="17.5" x2="17" y2="12.5"/>
            </svg>
          </div>
          <p className="text-xs text-muted-foreground">No graph data available</p>
          <p className="text-[10px] text-muted-foreground/60">
            Upload and index documents first
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full bg-card rounded-xl border border-border overflow-hidden relative">
      {/* Auto-Reference Button */}
      <div className="absolute top-3 right-3 z-10 flex flex-col items-end gap-2">
        <button
          onClick={handleAutoReference}
          disabled={autoRefLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed shadow-sm transition-colors"
        >
          {autoRefLoading ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <Sparkles size={14} />
          )}
          Auto-Reference
        </button>

        {autoRefError && (
          <div className="bg-destructive/10 text-destructive text-[10px] px-2 py-1 rounded-md max-w-[200px]">
            {autoRefError}
          </div>
        )}

        {/* Suggestion Controls Panel */}
        {pendingSuggestions.length > 0 && (
          <div className="bg-card border border-border rounded-lg shadow-lg p-2 max-w-[260px] max-h-[300px] overflow-y-auto">
            <p className="text-[10px] font-medium text-muted-foreground mb-1.5">
              Suggestions ({pendingSuggestions.length})
            </p>
            <div className="flex flex-col gap-1.5">
              {pendingSuggestions.map((suggestion) => (
                <div
                  key={suggestion.id}
                  className="flex items-center gap-1.5 p-1.5 rounded-md bg-secondary/50 border border-purple-200 dark:border-purple-800"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-[10px] font-medium text-foreground truncate">
                      {suggestion.label || suggestion.type}
                    </p>
                    <p className="text-[9px] text-muted-foreground truncate">
                      {suggestion.source} → {suggestion.target}
                    </p>
                  </div>
                  <div className="flex items-center gap-0.5 shrink-0">
                    <button
                      onClick={() => handleAcceptSuggestion(suggestion)}
                      disabled={suggestion.status === "accepting"}
                      className="p-1 rounded hover:bg-green-100 dark:hover:bg-green-900/30 text-green-600 dark:text-green-400 disabled:opacity-50"
                      title="Accept suggestion"
                    >
                      {suggestion.status === "accepting" ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Check size={12} />
                      )}
                    </button>
                    <button
                      onClick={() => handleDismissSuggestion(suggestion.id)}
                      disabled={suggestion.status === "accepting"}
                      className="p-1 rounded hover:bg-red-100 dark:hover:bg-red-900/30 text-red-600 dark:text-red-400 disabled:opacity-50"
                      title="Dismiss suggestion"
                    >
                      <X size={12} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.1}
        maxZoom={4}
        attributionPosition="bottom-left"
        className="bg-background/50"
      >
        <Background
          variant="dots"
          gap={20}
          size={1}
          color="var(--border)"
        />
        <Controls
          className="!bg-card !border !border-border !rounded-lg !shadow-sm [&>button]:!text-muted-foreground [&>button]:!border-border [&>button]:!bg-card [&>button:hover]:!bg-secondary"
        />
        <MiniMap
          nodeStrokeColor="var(--border)"
          nodeColor="var(--card)"
          nodeBorderRadius={8}
          maskColor="rgba(0,0,0,0.1)"
          className="!border !border-border !rounded-lg"
        />
      </ReactFlow>
    </div>
  );
}

export default KnowledgeGraph;
