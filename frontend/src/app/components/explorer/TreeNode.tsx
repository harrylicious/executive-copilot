import { useState } from "react";
import { ChevronRight, Building2, Folder, FileText, Trash2, Loader2 } from "lucide-react";
import { cn } from "../../../utils/cn";
import type { TreeNode as TreeNodeType } from "../../../types";

interface TreeNodeProps {
  node: TreeNodeType;
  depth: number;
  selectedId?: string;
  onSelect: (node: TreeNodeType) => void;
  onDelete?: (node: TreeNodeType) => void;
  deletingId?: string | null;
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

export function TreeNode({ node, depth, selectedId, onSelect, onDelete, deletingId }: TreeNodeProps) {
  const [expanded, setExpanded] = useState(depth < 1);
  const hasChildren = node.children && node.children.length > 0;
  const isSelected = selectedId === node.id;
  const Icon = getIcon(node.type);
  const deptColor = node.color || DEPT_COLORS[node.name];
  const isDeleting = deletingId === node.id;
  const canDelete = node.type === "file" || node.type === "folder";

  return (
    <div className="relative group">
      <button
        onClick={() => {
          onSelect(node);
          if (hasChildren) setExpanded(!expanded);
        }}
        className={cn(
          "w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-left transition-all text-xs",
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
      </button>

      {/* Delete button — accessible span with role="button" to avoid nested <button> */}
      {canDelete && (
        <span
          onClick={(e) => {
            e.stopPropagation();
            onDelete?.(node);
          }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.stopPropagation();
              onDelete?.(node);
            }
          }}
          role="button"
          tabIndex={isDeleting ? -1 : 0}
          aria-disabled={isDeleting}
          aria-label={`Hapus ${node.type === "file" ? "file" : "folder"}`}
          className="absolute right-2 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 p-0.5 rounded text-muted-foreground hover:text-red-500 aria-disabled:opacity-40 transition-all shrink-0 cursor-pointer select-none"
        >
          {isDeleting ? <Loader2 size={11} className="animate-spin" /> : <Trash2 size={11} />}
        </span>
      )}

      {hasChildren && expanded && (
        <div>
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              onSelect={onSelect}
              onDelete={onDelete}
              deletingId={deletingId}
            />
          ))}
        </div>
      )}
    </div>
  );
}

export default TreeNode;