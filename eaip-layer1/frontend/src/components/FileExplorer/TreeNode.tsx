import { useState, useEffect, useCallback, useRef } from "react";
import type { FC } from "react";
import type { TreeNode as TreeNodeType } from "../../types";
import { cn } from "@/lib/utils";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { ChevronRight, Folder, FolderOpen, MoreHorizontal, Eye, FolderOpenDot } from "lucide-react";
import type { IconType } from "react-icons";
import { FaFilePdf, FaFileWord, FaFileExcel, FaFileCsv, FaFileCode, FaFileAlt } from "react-icons/fa";
import { detectFormat } from "../../utils/fileFormat";

function getFileIcon(name: string): IconType {
  const format = detectFormat(name);
  switch (format) {
    case "pdf":
      return FaFilePdf;
    case "docx":
      return FaFileWord;
    case "xlsx":
      return FaFileExcel;
    case "csv":
      return FaFileCsv;
    case "json":
      return FaFileCode;
    default:
      return FaFileAlt;
  }
}

function getFileColor(name: string): string {
  const format = detectFormat(name);
  switch (format) {
    case "pdf":
      return "text-red-500";
    case "docx":
      return "text-blue-500";
    case "xlsx":
      return "text-emerald-500";
    case "csv":
      return "text-green-500";
    case "json":
      return "text-amber-500";
    default:
      return "text-foreground";
  }
}

const STORAGE_KEY = "eaip-tree-expanded";

function getExpandedState(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return new Set(JSON.parse(raw));
  } catch {
    // ignore
  }
  return new Set();
}

function saveExpandedState(ids: Set<string>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    // ignore
  }
}

interface TreeNodeProps {
  node: TreeNodeType;
  depth: number;
  onFileSelect: (fileId: number) => void;
  onOpenInFolder?: (node: TreeNodeType) => void;
}

export const TreeNode: FC<TreeNodeProps> = ({ node, depth, onFileSelect, onOpenInFolder }) => {
  const [expanded, setExpanded] = useState(() => {
    const stored = getExpandedState();
    return stored.has(node.id) || depth === 0;
  });
  const [contextOpen, setContextOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const isExpandable = node.type === "department" || node.type === "folder";
  const hasChildren = node.children && node.children.length > 0;

  // Persist expanded state
  useEffect(() => {
    const stored = getExpandedState();
    if (expanded) {
      stored.add(node.id);
    } else {
      stored.delete(node.id);
    }
    saveExpandedState(stored);
  }, [expanded, node.id]);

  const handleClick = () => {
    if (isExpandable) {
      setExpanded((prev) => !prev);
    } else if (node.type === "file" && node.fileId != null) {
      onFileSelect(node.fileId);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setContextOpen(true);
  }, []);

  const handleOpenFile = () => {
    if (node.type === "file" && node.fileId != null) {
      onFileSelect(node.fileId);
    }
  };

  const handleExpandAll = () => {
    if (isExpandable) {
      setExpanded(true);
      // Expand all children recursively via localStorage
      const stored = getExpandedState();
      const expandRecursive = (n: TreeNodeType) => {
        if (n.type === "department" || n.type === "folder") {
          stored.add(n.id);
          n.children?.forEach(expandRecursive);
        }
      };
      expandRecursive(node);
      saveExpandedState(stored);
      // Force re-render by toggling
      setExpanded(false);
      setTimeout(() => setExpanded(true), 0);
    }
  };

  const handleCollapseAll = () => {
    if (isExpandable) {
      const stored = getExpandedState();
      const collapseRecursive = (n: TreeNodeType) => {
        stored.delete(n.id);
        n.children?.forEach(collapseRecursive);
      };
      collapseRecursive(node);
      saveExpandedState(stored);
      setExpanded(false);
    }
  };

  return (
    <div>
      <div
        role="treeitem"
        tabIndex={0}
        aria-expanded={isExpandable ? expanded : undefined}
        className={cn(
          "group flex items-center gap-1.5 px-2 py-1 cursor-pointer rounded text-xs transition-colors",
          "text-foreground hover:bg-muted"
        )}
        style={{ paddingLeft: `${depth * 14 + 8}px` }}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onContextMenu={handleContextMenu}
      >
        {/* Chevron */}
        {isExpandable ? (
          <ChevronRight
            className={cn(
              "size-3 text-muted-foreground shrink-0 transition-transform",
              expanded && "rotate-90"
            )}
          />
        ) : (
          <span className="w-3 shrink-0" />
        )}

        {/* Icon */}
        {isExpandable ? (
          expanded ? (
            <FolderOpen className="size-3.5 text-primary shrink-0" />
          ) : (
            <Folder className="size-3.5 text-primary/70 shrink-0" />
          )
        ) : (() => {
          const Icon = getFileIcon(node.name);
          const color = getFileColor(node.name);
          return <Icon className={`size-3.5 shrink-0 ${color}`} />;
        })()}

        {/* Label */}
        <span className="truncate flex-1">{node.name}</span>

        {/* Context menu trigger (visible on hover) */}
        <DropdownMenu open={contextOpen} onOpenChange={setContextOpen}>
          <DropdownMenuTrigger asChild>
            <button
              ref={triggerRef}
              className="opacity-0 group-hover:opacity-100 shrink-0 p-0.5 rounded hover:bg-muted-foreground/10 transition-opacity"
              onClick={(e) => { e.stopPropagation(); setContextOpen(true); }}
              aria-label="More actions"
            >
              <MoreHorizontal className="size-3" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="w-44">
            {node.type === "file" && node.fileId != null && (
              <DropdownMenuItem onClick={handleOpenFile}>
                <Eye className="size-3.5 mr-2" />
                Open File
              </DropdownMenuItem>
            )}
            {isExpandable && (
              <>
                <DropdownMenuItem onClick={handleExpandAll}>
                  <FolderOpenDot className="size-3.5 mr-2" />
                  Expand All
                </DropdownMenuItem>
                <DropdownMenuItem onClick={handleCollapseAll}>
                  <Folder className="size-3.5 mr-2" />
                  Collapse All
                </DropdownMenuItem>
              </>
            )}
            {onOpenInFolder && (
              <>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => onOpenInFolder(node)}>
                  <FolderOpen className="size-3.5 mr-2" />
                  Reveal in Folder
                </DropdownMenuItem>
              </>
            )}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Children */}
      {isExpandable && expanded && hasChildren && (
        <div role="group">
          {node.children!.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              onFileSelect={onFileSelect}
              onOpenInFolder={onOpenInFolder}
            />
          ))}
        </div>
      )}
    </div>
  );
};

export default TreeNode;
