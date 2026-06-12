import { useState, useMemo, lazy, Suspense } from "react";
import { Search, RotateCcw, PanelLeft, PanelRight } from "lucide-react";
import { cn } from "../../../utils/cn";
import { useFiles } from "../../../hooks/useFiles";
import { detectFormat } from "../../../utils/fileFormat";
import { TreeNode } from "./TreeNode";
import { MetadataSidebar } from "./MetadataSidebar";
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

export function FileExplorer() {
  const { tree, treeLoading, treeError, files, filesLoading, refresh } = useFiles();
  const [selectedNode, setSelectedNode] = useState<TreeNodeType | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [showTree, setShowTree] = useState(true);
  const [showMetadata, setShowMetadata] = useState(true);

  const selectedFile = useMemo(() => {
    if (!selectedNode || selectedNode.type !== "file" || !selectedNode.fileId) return null;
    return files.find((f) => f.id === selectedNode.fileId) || null;
  }, [selectedNode, files]);

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
            {selectedNode && (
              <span className="text-xs text-muted-foreground truncate max-w-[200px]">
                {selectedNode.name}
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
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center px-4">
              <div className="w-12 h-12 rounded-2xl bg-primary/5 flex items-center justify-center mb-3">
                <PanelLeft size={24} className="text-muted-foreground/40" />
              </div>
              <p className="text-sm text-muted-foreground">Select a file to preview</p>
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
        />
      )}
    </div>
  );
}

export default FileExplorer;
