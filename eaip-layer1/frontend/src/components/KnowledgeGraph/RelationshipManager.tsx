import { useState, useCallback } from "react";
import type { FC } from "react";
import type { GraphNode, GraphEdge } from "../../types";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface RelationshipManagerProps {
  nodes: GraphNode[];
  onCreateRelationship: (
    sourceFileId: number,
    targetFileId: number,
    type: string
  ) => Promise<void>;
  onDeleteRelationship: (id: number) => Promise<void>;
  selectedEdge?: GraphEdge | null;
  onEdgeDismiss?: () => void;
}

const RelationshipManager: FC<RelationshipManagerProps> = ({
  nodes,
  onCreateRelationship,
  onDeleteRelationship,
  selectedEdge,
  onEdgeDismiss,
}) => {
  const [sourceId, setSourceId] = useState<string>("");
  const [targetId, setTargetId] = useState<string>("");
  const [relType, setRelType] = useState<string>("");
  const [isCreating, setIsCreating] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const handleCreate = useCallback(async () => {
    if (!sourceId || !targetId || !relType.trim()) return;

    const sourceNode = nodes.find((n) => n.id === sourceId);
    const targetNode = nodes.find((n) => n.id === targetId);
    if (!sourceNode || !targetNode) return;

    setIsCreating(true);
    try {
      await onCreateRelationship(
        sourceNode.data.fileId,
        targetNode.data.fileId,
        relType.trim()
      );
      setSourceId("");
      setTargetId("");
      setRelType("");
    } finally {
      setIsCreating(false);
    }
  }, [sourceId, targetId, relType, nodes, onCreateRelationship]);

  const handleDeleteEdge = useCallback(async () => {
    if (!selectedEdge) return;
    const edgeId = parseInt(selectedEdge.id, 10);
    if (isNaN(edgeId)) return;
    await onDeleteRelationship(edgeId);
    setShowDeleteConfirm(false);
    onEdgeDismiss?.();
  }, [selectedEdge, onDeleteRelationship, onEdgeDismiss]);

  const isFormValid = sourceId && targetId && relType.trim() && sourceId !== targetId;

  return (
    <Card className="p-0 gap-0">
      <CardHeader className="px-4 py-3">
        <CardTitle className="text-sm">Manage Relationships</CardTitle>
      </CardHeader>

      <CardContent className="px-4 pb-4 space-y-4">
        {/* Create Relationship Form */}
        <div className="space-y-3">
          <div>
            <label
              htmlFor="rel-source"
              className="block text-xs text-muted-foreground mb-1"
            >
              Source File
            </label>
            <Select value={sourceId} onValueChange={setSourceId}>
              <SelectTrigger id="rel-source" className="w-full" aria-label="Source File">
                <SelectValue placeholder="Select source..." />
              </SelectTrigger>
              <SelectContent>
                {nodes.map((node) => (
                  <SelectItem key={node.id} value={node.id}>
                    {node.data.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label
              htmlFor="rel-target"
              className="block text-xs text-muted-foreground mb-1"
            >
              Target File
            </label>
            <Select value={targetId} onValueChange={setTargetId}>
              <SelectTrigger id="rel-target" className="w-full" aria-label="Target File">
                <SelectValue placeholder="Select target..." />
              </SelectTrigger>
              <SelectContent>
                {nodes.map((node) => (
                  <SelectItem key={node.id} value={node.id}>
                    {node.data.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div>
            <label
              htmlFor="rel-type"
              className="block text-xs text-muted-foreground mb-1"
            >
              Relationship Type
            </label>
            <Input
              id="rel-type"
              type="text"
              value={relType}
              onChange={(e) => setRelType(e.target.value)}
              placeholder="e.g. references, depends-on"
            />
          </div>

          <Button
            onClick={handleCreate}
            disabled={!isFormValid || isCreating}
            className="w-full"
          >
            {isCreating ? "Creating..." : "Create Relationship"}
          </Button>
        </div>

        {/* Delete Relationship Section */}
        {selectedEdge && (
          <div className="border-t border-border pt-3 space-y-2">
            <p className="text-xs text-muted-foreground">
              Selected edge:{" "}
              <span className="text-foreground">
                {selectedEdge.label || selectedEdge.id}
              </span>
            </p>
            <Button
              variant="destructive"
              className="w-full"
              onClick={() => setShowDeleteConfirm(true)}
            >
              Delete Relationship
            </Button>
          </div>
        )}

        {/* Delete Confirmation Dialog */}
        <Dialog open={showDeleteConfirm} onOpenChange={setShowDeleteConfirm}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Relationship</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete the relationship &quot;{selectedEdge?.label || selectedEdge?.id}&quot;? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setShowDeleteConfirm(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDeleteEdge}
              >
                Confirm
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </CardContent>
    </Card>
  );
};

export default RelationshipManager;
