import type { FC } from "react";
import { Handle, Position } from "reactflow";
import type { NodeProps } from "reactflow";
import { cn } from "@/lib/utils";

const DEPARTMENT_NODE_COLORS: Record<
  string,
  { accent: string; badge: string }
> = {
  demand_supply: {
    accent: "#7c3aed",
    badge: "bg-purple-500/15 text-purple-600 dark:text-purple-400",
  },
  accounting_tax: {
    accent: "#0d9488",
    badge: "bg-teal-500/15 text-teal-600 dark:text-teal-400",
  },
  logistic: {
    accent: "#d97706",
    badge: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  },
  finance: {
    accent: "#ea580c",
    badge: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
  },
};

const DEFAULT_COLORS = {
  accent: "#6b7280",
  badge: "bg-gray-500/15 text-gray-600 dark:text-gray-400",
};

function getNodeColors(department: string) {
  return DEPARTMENT_NODE_COLORS[department] ?? DEFAULT_COLORS;
}

interface GraphNodeData {
  label: string;
  department: string;
  fileId: number;
}

export const GraphNode: FC<NodeProps<GraphNodeData>> = ({ data }) => {
  const colors = getNodeColors(data.department);

  return (
    <div
      className="group relative px-3 py-2.5 rounded-lg border bg-card shadow-sm cursor-pointer transition-all duration-150 hover:shadow-md hover:scale-[1.03]"
      style={{
        borderColor: colors.accent + "60",
        minWidth: 130,
      }}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2.5 !h-2.5 !border-2 !bg-card !border-muted-foreground/40 transition-all group-hover:!scale-110"
      />

      <div className="flex items-center gap-2 relative z-10">
        <svg
          className="w-4 h-4 shrink-0"
          style={{ color: colors.accent }}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
          />
        </svg>
        <div className="min-w-0">
          <div className="text-xs font-medium text-foreground truncate max-w-[140px] leading-tight">
            {data.label}
          </div>
          <div
            className={cn(
              "text-[10px] font-medium mt-0.5 inline-block px-1.5 py-0.5 rounded",
              colors.badge
            )}
          >
            {data.department.replace(/_/g, " ")}
          </div>
        </div>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2.5 !h-2.5 !border-2 !bg-card !border-muted-foreground/40 transition-all group-hover:!scale-110"
      />
    </div>
  );
};

export default GraphNode;
