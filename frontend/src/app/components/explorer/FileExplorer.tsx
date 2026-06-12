import { useState, useMemo, lazy, Suspense } from "react";
import { Search, RotateCcw, PanelLeft, PanelRight, FileText, Folder, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import { cn } from "../../../utils/cn";
import { useFiles } from "../../../hooks/useFiles";
import { detectFormat } from "../../../utils/fileFormat";
import { TreeNode } from "./TreeNode";
import { MetadataSidebar } from "./MetadataSidebar";
import { deleteFile } from "../../../api/kb";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogCancel,
  AlertDialogAction,
} from "../ui/alert-dialog";
import type { TreeNode as TreeNodeType, FileNode } from "../../../types";

const PdfViewer = lazy(() => import("./PdfViewer"));
const ExcelViewer = lazy(() => import("./ExcelViewer"));
const DocxViewer = lazy(() => import("./DocxViewer"));
const JsonViewer = lazy(() => import("./JsonViewer"));
const MarkdownViewer = lazy(() => import("./MarkdownViewer"));
const PlainTextViewer = lazy(() => import("./PlainTextViewer"));
const CsvViewer = lazy(() => import("./CsvViewer"));

function FileContent({ file }: { file: FileNode }) {
  const format = detectFormat(file.name);

  if (!format) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <p className="text-sm">Unsupported file format</p>
      </div>
    );
  }

  const viewerMap: Record<string, React.ReactNode> = {
    pdf: <PdfViewer fileId={file.id} />,
    xlsx: <ExcelViewer fileId={file.id} />,
    json: <JsonViewer fileId={file.id} />,
    docx: <DocxViewer fileId={file.id} />,
    md: <MarkdownViewer fileId={file.id} />,
    txt: <PlainTextViewer fileId={file.id} />,
    csv: <CsvViewer fileId={file.id} />,
  };

  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full">
        <div className="w-5 h-5 border-2 border-muted border-t-primary rounded-full animate-spin" />
      </div>
    }>
      {viewerMap[format] || (
        <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
          <p className="text-sm">Preview not available for {format.toUpperCase()} files</p>
        </div>
      )}
    </Suspense>
  );
}

/** Shows a folder/department's contents as a clickable file list */
function FolderFileList({
  node,
  files,
  onSelectFile,
}: {
  node: TreeNodeType;
  files: FileNode[];
  onSelectFile: (node: TreeNodeType) => void;
}) {
  const fileChildren = node.children?.filter((c) => c.type === "file") || [];
  const subfolders = node.children?.filter((c) => c.type === "folder") || [];

  return (
    <div className="p-6 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-center gap-2 mb-5 pb-4 border-b border-border">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0"
          style={{ backgroundColor: `${node.color || "#10b981"}18` }}
        >
          <Folder size={15} style={{ color: node.color || "#10b981" }} />
        </div>
        <div>
          <h3 className="text-sm font-medium text-foreground">{node.name}</h3>
          <p className="text-xs text-muted-foreground">
            {node.description || `${fileChildren.length} file`}
          </p>
        </div>
      </div>

      {/* Subfolders */}
      {subfolders.length > 0 && (
        <div className="mb-5">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-medium">
            Subfolder
          </p>
          <div className="space-y-0.5">
            {subfolders.map((sub) => (
              <button
                key={sub.id}
                onClick={() => onSelectFile(sub)}
                className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-muted-foreground hover:text-secondary-foreground hover:bg-card transition-colors"
              >
                <Folder size={14} className="shrink-0 text-muted-foreground" />
                <span className="truncate flex-1">{sub.name}</span>
                <span className="text-[10px] text-muted-foreground">
                  {sub.children?.filter((c) => c.type === "file").length || 0} file
                </span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Files */}
      {fileChildren.length > 0 ? (
        <div>
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-2 font-medium">
            File
          </p>
          <div className="space-y-0.5">
            {fileChildren.map((child) => {
              const fileInfo = child.fileId != null
                ? files.find((f) => f.id === child.fileId)
                : undefined;
              return (
                <button
                  key={child.id}
                  onClick={() => onSelectFile(child)}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left text-xs text-muted-foreground hover:text-secondary-foreground hover:bg-card transition-colors group"
                >
                  <FileText size={14} className="shrink-0 text-primary/60" />
                  <span className="truncate flex-1">{child.name}</span>
                  {fileInfo && (
                    <span className="text-[10px] text-muted-foreground shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                      {formatSize(fileInfo.size)}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ) : subfolders.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <FileText size={32} className="text-muted-foreground/30 mb-2" />
          <p className="text-sm text-muted-foreground">Folder ini kosong</p>
        </div>
      ) : null}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

export function FileExplorer() {
  const { tree, treeLoading, treeError, files, filesLoading, refresh, removeNode } = useFiles();
  const [selectedNode, setSelectedNode] = useState<TreeNodeType | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showTree, setShowTree] = useState(true);
  const [showMetadata, setShowMetadata] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<TreeNodeType | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDeleteRequest = (node: TreeNodeType) => {
    setDeleteTarget(node);
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTarget || deletingId) return;

    setDeletingId(deleteTarget.id);
    const target = deleteTarget;
    setDeleteTarget(null);

    try {
      if (target.type === "file" && target.fileId != null) {
        await deleteFile(target.fileId);
      } else if (target.type === "folder" || target.type === "department") {
        const fileIds = collectFileIds(target);
        if (fileIds.length > 0) {
          await Promise.all(fileIds.map((fid) => deleteFile(fid)));
        }
      }
      removeNode(target.id);
      toast.success(`"${target.name}" berhasil dihapus`);
      if (selectedNode?.id === target.id) setSelectedNode(null);
      refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Gagal menghapus";
      toast.error(msg);
    } finally {
      setDeletingId(null);
    }
  };

  const selectedFile = useMemo(() => {
    if (!selectedNode || selectedNode.type !== "file" || !selectedNode.fileId) return null;
    return files.find((f) => f.id === selectedNode.fileId) || null;
  }, [selectedNode, files]);

  const isViewingFolder = selectedNode && (selectedNode.type === "department" || selectedNode.type === "folder");

  const filteredTree = useMemo(() => {
    if (!searchQuery.trim()) return tree;
    const q = searchQuery.toLowerCase();

    function filterNodes(nodes: TreeNodeType[]): TreeNodeType[] {
      return nodes
        .map((n) => {
          const children = n.children ? filterNodes(n.children) : undefined;
          const nameMatch = n.name.toLowerCase().includes(q);
          if (nameMatch || (children && children.length > 0)) {
            return { ...n, children: children && children.length > 0 ? children : undefined };
          }
          return null;
        })
        .filter((n): n is TreeNodeType => n !== null);
    }

    return filterNodes(tree);
  }, [tree, searchQuery]);

  const handleNodeSelect = (node: TreeNodeType) => {
    setSelectedNode(node);
  };

  return (
    <div className="flex h-full bg-background">
      {/* Left panel - Tree */}
      {showTree && (
        <div className="w-64 border-r border-border bg-card flex flex-col shrink-0">
          {/* Search */}
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search files..."
                className="w-full bg-input border border-border rounded-lg pl-8 pr-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/40"
              />
            </div>
          </div>

          {/* Tree */}
          <div className="flex-1 overflow-y-auto p-2">
            {treeLoading && (
              <div className="flex items-center justify-center py-8">
                <div className="w-4 h-4 border-2 border-muted border-t-primary rounded-full animate-spin" />
              </div>
            )}
            {treeError && (
              <div className="text-xs text-destructive text-center py-4 px-2">{treeError}</div>
            )}
            {!treeLoading && !treeError && filteredTree.length === 0 && (
              <div className="text-xs text-muted-foreground text-center py-4">
                {searchQuery ? "No matching files" : "No files found"}
              </div>
            )}
            {!treeLoading &&
              filteredTree.map((node) => (
                <TreeNode
                  key={node.id}
                  node={node}
                  depth={0}
                  selectedId={selectedNode?.id}
                  onSelect={handleNodeSelect}
                  onDelete={handleDeleteRequest}
                  deletingId={deletingId}
                />
              ))}
          </div>
        </div>
      )}

      {/* Center panel - Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Toolbar */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-card">
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowTree(!showTree)}
              className={cn(
                "p-1.5 rounded-lg transition-colors",
                showTree ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-secondary-foreground hover:bg-card"
              )}
              title="Toggle file tree"
            >
              <PanelLeft size={14} />
            </button>
            <button
              onClick={() => setShowMetadata(!showMetadata)}
              className={cn(
                "p-1.5 rounded-lg transition-colors",
                showMetadata ? "bg-secondary text-foreground" : "text-muted-foreground hover:text-secondary-foreground hover:bg-card"
              )}
              title="Toggle metadata panel"
            >
              <PanelRight size={14} />
            </button>
          </div>

          <div className="flex items-center gap-2">
            {/* Breadcrumb */}
            {selectedNode && (
              <span className="text-xs text-foreground/80 truncate max-w-[300px]">
                {selectedNode.type !== "file" && (
                  <span className="text-primary font-medium">{selectedNode.name}</span>
                )}
                {selectedNode.type === "file" && (
                  <>
                    <button
                      onClick={() => {
                        // Walk up to the parent in the tree
                        const parent = findParentNode(tree, selectedNode.id);
                        if (parent) setSelectedNode(parent);
                      }}
                      className="text-muted-foreground hover:text-foreground transition-colors mr-1"
                      title="Kembali ke folder"
                    >
                      <ArrowLeft size={12} className="inline" />
                    </button>
                    <span className="text-foreground">{selectedNode.name}</span>
                  </>
                )}
              </span>
            )}
            <button
              onClick={refresh}
              className="p-1.5 rounded-lg text-muted-foreground hover:text-secondary-foreground hover:bg-card transition-colors"
              title="Refresh"
            >
              <RotateCcw size={14} />
            </button>
          </div>
        </div>

        {/* Content area */}
        <div className="flex-1 overflow-hidden bg-background">
          {selectedFile ? (
            <FileContent file={selectedFile} />
          ) : isViewingFolder ? (
            <FolderFileList
              node={selectedNode}
              files={files}
              onSelectFile={handleNodeSelect}
            />
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/5 flex items-center justify-center mb-3">
                <PanelLeft size={24} className="text-muted-foreground/40" />
              </div>
              <p className="text-sm text-muted-foreground">Select a folder or file</p>
              <p className="text-xs text-muted-foreground/60 mt-1">
                Browse the file tree on the left
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Right panel - Metadata */}
      {showMetadata && (
        <MetadataSidebar
          file={selectedFile}
          onClose={() => setShowMetadata(false)}
          onDeleteFile={selectedFile ? () => {
            setDeleteTarget({
              id: String(selectedFile.id),
              name: selectedFile.name,
              type: "file",
              fileId: selectedFile.id,
            });
          } : undefined}
        />
      )}

      {/* Delete confirmation modal */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => { if (!open) setDeleteTarget(null); }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {deleteTarget?.type === "file" ? "Hapus File" : "Hapus Folder"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.type === "file" ? (
                <>Apakah Anda yakin ingin menghapus <strong>{deleteTarget.name}</strong>? Tindakan ini tidak dapat dibatalkan.</>
              ) : (
                <>Apakah Anda yakin ingin menghapus folder <strong>{deleteTarget?.name}</strong>? Semua file di dalamnya akan ikut terhapus. Tindakan ini tidak dapat dibatalkan.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Batal</AlertDialogCancel>
            <AlertDialogAction onClick={handleDeleteConfirm} className="bg-red-600 hover:bg-red-700 text-white">
              Hapus
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

/** Walk the tree to find the parent of a given node id */
function findParentNode(nodes: TreeNodeType[], childId: string): TreeNodeType | null {
  for (const node of nodes) {
    if (!node.children) continue;
    if (node.children.some((c) => c.id === childId)) return node;
    const found = findParentNode(node.children, childId);
    if (found) return found;
  }
  return null;
}

/** Collect all file IDs from a folder/department node, recursively */
function collectFileIds(node: TreeNodeType): number[] {
  const ids: number[] = [];
  if (!node.children) return ids;
  for (const child of node.children) {
    if (child.type === "file" && child.fileId != null) {
      ids.push(child.fileId);
    }
    if (child.children) {
      ids.push(...collectFileIds(child));
    }
  }
  return ids;
}

export default FileExplorer;