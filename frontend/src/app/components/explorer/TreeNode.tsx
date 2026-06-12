import { useState } from "react";
import { ChevronRight, Building2, Folder, FileText } from "lucide-react";
import { cn } from "../../../utils/cn";
import type { TreeNode as TreeNodeType } from "../../../types";

interface TreeNodeProps {
  node: TreeNodeType;
  depth: number;
  selectedId?: string;
  onSelect: (node: TreeNodeType) => void;
}

function getIcon(type: string) {
  switch (type) {
    case "department": return Building2;
    case "folder": return Folder;
    default: return FileText;
  }
}

const DEPT_COLORS: Record<string, string> = {
  "Accounting Tax": "#10b981",
  "Demand Supply": "#f59e0b",
  "Finance": "#8b5cf6",
  "Logistic": "#3b82f6",
};

export function TreeNode({ node, depth, selectedId, onSelect }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedId === node.id;
  const Icon = getIcon(node.type);
  const deptColor = node.color || DEPT_COLORS[node.name];

  return (
    <div>
      <button
        onClick={() => {
          onSelect(node);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all text-xs group",
          isSelected
            ? "bg-secondary text-foreground border border-border"
            : "text-muted-foreground hover:text-secondary-foreground hover:bg-card"
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {hasChildren ? (
          <ChevronRight
            size={12}
            className={cn(
              "shrink-0 transition-transform text-muted-foreground",
              expanded && "rotate-90"
            )}
          />
        ) : (
          <span className="w-3 shrink-0" />
        )}

        {node.type === "department" ? (
          <div
            className="w-4 h-4 rounded flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${deptColor}18` }}
          >
            <Icon size={10} style={{ color: deptColor }} />
          </div>
        ) : (
          <Icon size={14} className="shrink-0 text-muted-foreground" />
        )}

        <span className="truncate flex-1">{node.name}</span>

        {node.sensitivity && (
          <span className={cn(
            "text-[10px] px-1.5 py-0.5 rounded-full shrink-0",
            node.sensitivity === "high" ? "bg-red-500/10 text-red-500" :
            node.sensitivity === "medium" ? "bg-amber-500/10 text-amber-500" :
            "bg-emerald-500/10 text-emerald-500"
          )}>
            {node.sensitivity}
          </span>
        )}
      </button>

      {hasChildren && expanded && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default TreeNode;
