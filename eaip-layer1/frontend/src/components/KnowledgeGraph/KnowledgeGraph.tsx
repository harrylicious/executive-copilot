import { useCallback, useEffect, useState } from "react";
import type { FC } from "react";
import type { Node, Edge, Connection } from "reactflow";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  MarkerType,
  ConnectionLineType,
} from "reactflow";
import "reactflow/dist/style.css";
import type { GraphData } from "../../types";
import GraphNode from "./GraphNode";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const nodeTypes = { custom: GraphNode };

interface KnowledgeGraphProps {
  data: GraphData;
  onNodeSelect: (fileId: number) => void;
  onCreateRelationship: (
    sourceFileId: number,
    targetFileId: number,
    type: string
  ) => Promise<void>;
  onDeleteRelationship: (id: number) => Promise<void>;
}

const defaultEdgeOptions = {
  animated: true,
  style: { stroke: "#4f46e5", strokeWidth: 2.5 },
  markerEnd: { type: MarkerType.ArrowClosed, color: "#4f46e5" },
  labelStyle: {
    fill: "#c7d2fe",
    fontSize: 11,
    fontWeight: 600,
    fontFamily: "Inter, system-ui, sans-serif",
  },
  labelBgStyle: {
    fill: "#1e1b4b",
    fillOpacity: 0.9,
  },
  labelBgPadding: [6, 3] as [number, number],
  labelBgBorderRadius: 4,
};

export const KnowledgeGraph: FC<KnowledgeGraphProps> = ({
  data,
  onNodeSelect,
  onCreateRelationship,
  onDeleteRelationship,
}) => {
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedEdge, setSelectedEdge] = useState<Edge | null>(null);
  const [deleting, setDeleting] = useState(false);

  // State for the "create relationship" dialog (replaces window.prompt)
  const [connectDialogOpen, setConnectDialogOpen] = useState(false);
  const [connectRelType, setConnectRelType] = useState("references");
  const [pendingConnection, setPendingConnection] = useState<{
    sourceFileId: number;
    targetFileId: number;
  } | null>(null);

  useEffect(() => {
    setNodes(data.nodes.map((n) => ({ ...n, type: "custom" })));
    setEdges(
      data.edges.map((e) => ({
        ...e,
        animated: true,
        style: { stroke: "#4f46e5", strokeWidth: 2.5 },
        markerEnd: { type: MarkerType.ArrowClosed, color: "#4f46e5" },
      }))
    );
  }, [data, setNodes, setEdges]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onNodeSelect(node.data.fileId);
    },
    [onNodeSelect]
  );

  const handleConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;

      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      if (!sourceNode || !targetNode) return;

      setPendingConnection({
        sourceFileId: sourceNode.data.fileId,
        targetFileId: targetNode.data.fileId,
      });
      setConnectRelType("references");
      setConnectDialogOpen(true);
    },
    [nodes]
  );

  const handleConnectConfirm = useCallback(async () => {
    if (!pendingConnection || !connectRelType.trim()) return;

    await onCreateRelationship(
      pendingConnection.sourceFileId,
      pendingConnection.targetFileId,
      connectRelType.trim()
    );

    setConnectDialogOpen(false);
    setPendingConnection(null);
    setConnectRelType("references");
  }, [pendingConnection, connectRelType, onCreateRelationship]);

  const handleConnectCancel = useCallback(() => {
    setConnectDialogOpen(false);
    setPendingConnection(null);
    setConnectRelType("references");
  }, []);

  const handleEdgeClick = useCallback(
    (_: React.MouseEvent, edge: Edge) => {
      setSelectedEdge((prev) => (prev?.id === edge.id ? null : edge));
    },
    []
  );

  const handlePaneClick = useCallback(() => {
    setSelectedEdge(null);
  }, []);

  const handleDeleteSelectedEdge = useCallback(async () => {
    if (!selectedEdge) return;
    setDeleting(true);
    const edgeId = parseInt(selectedEdge.id, 10);
    if (!isNaN(edgeId)) {
      await onDeleteRelationship(edgeId);
    }
    setSelectedEdge(null);
    setDeleting(false);
  }, [selectedEdge, onDeleteRelationship]);

  return (
    <div className="h-full w-full relative" style={{ minHeight: "400px" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onConnect={handleConnect}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        attributionPosition="bottom-left"
        defaultEdgeOptions={defaultEdgeOptions}
        connectionLineStyle={{
          stroke: "#818cf8",
          strokeWidth: 3,
          strokeDasharray: "6 4",
        }}
        connectionLineType={ConnectionLineType.SmoothStep}
        deleteKeyCode={null}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="hsl(var(--border))" gap={24} size={1} />
        <Controls
          className="!bg-card !border-border !rounded-lg !shadow-lg [&_button]:!bg-card [&_button]:!border-border [&_button]:!text-muted-foreground [&_button:hover]:!text-foreground [&_button:hover]:!bg-muted"
          showInteractive={false}
        />
        <MiniMap
          nodeColor="#6366f1"
          maskColor="hsl(var(--background) / 0.7)"
          className="!bg-card !border-border !rounded-lg !shadow-lg"
          style={{ width: 140, height: 90 }}
        />
      </ReactFlow>

      {selectedEdge && (
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 z-20">
          <div className="bg-card/95 backdrop-blur-sm border border-border rounded-xl shadow-2xl px-4 py-3 flex items-center gap-4">
            <div className="text-sm text-muted-foreground">
              Relationship:{" "}
              <span className="text-foreground font-medium">
                {selectedEdge.label || "untitled"}
              </span>
            </div>
            <div className="w-px h-5 bg-border" />
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteSelectedEdge}
              disabled={deleting}
            >
              {deleting ? "Deleting..." : "Delete"}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setSelectedEdge(null)}
            >
              Dismiss
            </Button>
          </div>
        </div>
      )}

      {nodes.length > 0 && edges.length === 0 && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10">
          <div className="bg-card/80 backdrop-blur-sm border border-border rounded-lg px-4 py-2 text-xs text-muted-foreground shadow-lg">
            Drag from the bottom handle of a node to create a relationship
          </div>
        </div>
      )}

      {/* Create Relationship Dialog (replaces window.prompt) */}
      <Dialog open={connectDialogOpen} onOpenChange={(open) => {
        if (!open) handleConnectCancel();
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Relationship</DialogTitle>
            <DialogDescription>
              Enter the type of relationship between the connected nodes.
            </DialogDescription>
          </DialogHeader>
          <div className="py-2">
            <label
              htmlFor="connect-rel-type"
              className="block text-sm text-muted-foreground mb-1.5"
            >
              Relationship Type
            </label>
            <Input
              id="connect-rel-type"
              value={connectRelType}
              onChange={(e) => setConnectRelType(e.target.value)}
              placeholder="e.g. references, depends-on"
              onKeyDown={(e) => {
                if (e.key === "Enter" && connectRelType.trim()) {
                  handleConnectConfirm();
                }
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={handleConnectCancel}>
              Cancel
            </Button>
            <Button
              onClick={handleConnectConfirm}
              disabled={!connectRelType.trim()}
            >
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default KnowledgeGraph;
