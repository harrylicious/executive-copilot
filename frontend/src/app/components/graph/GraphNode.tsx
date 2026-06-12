import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { FileText } from "lucide-react";

interface GraphNodeData {
  label: string;
  department: string;
  fileId: number;
}

const DEPT_COLORS: Record<string, string> = {
  "Accounting Tax": "#10b981",
  "Demand Supply": "#f59e0b",
  "Finance": "#8b5cf6",
  "Logistic": "#3b82f6",
};

function GraphNode({ data }: NodeProps<GraphNodeData>) {
  const color = DEPT_COLORS[data.department] || "#10b981";

  return (
    <div className="bg-card border border-border rounded-xl shadow-sm hover:border-primary/40 transition-colors px-3 py-2.5 min-w-[160px]">
      <Handle
        type="target"
        position={Position.Top}
        className="!bg-border !w-2 !h-2 !border-2 !border-background"
      />
      <div className="flex items-center gap-2">
        <div
          className="w-6 h-6 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${color}18` }}
        >
          <FileText size={12} style={{ color }} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-foreground truncate">
            {data.label}
          </div>
          <div className="text-[10px] text-muted-foreground truncate">
            {data.department}
          </div>
        </div>
      </div>
      <Handle
        type="source"
        position={Position.Bottom}
        className="!bg-border !w-2 !h-2 !border-2 !border-background"
      />
    </div>
  );
}

export default memo(GraphNode);
