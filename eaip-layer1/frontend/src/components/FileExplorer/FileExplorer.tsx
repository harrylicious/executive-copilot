import { useState, useEffect, type FC, useRef, useCallback } from "react";
import { useFiles } from "../../hooks/useFiles";
import { uploadFile, revealFileInExplorer, createFolder } from "../../api/client";
import TreeNode from "./TreeNode";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FolderPlus } from "lucide-react";
import type { TreeNode as TreeNodeType } from "../../types";
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

const DEPARTMENTS: Record<string, string[]> = {
  demand_supply: ["demand_plans", "supply_plans", "deal_orders", "forecasts", "reference"],
  accounting_tax: ["invoices", "transactions", "tax_reports", "journal_entries", "policies"],
  logistic: ["inbound", "outbound", "warehouse", "shipping_docs", "sops"],
  finance: ["cashflow", "payments", "receivables", "budgets", "reports"],
};

const DEPARTMENT_LABELS: Record<string, string> = {
  demand_supply: "Demand-Supply Planning",
  accounting_tax: "Controller Accounting Tax",
  logistic: "Logistic",
  finance: "Finance",
};

type ViewMode = "department" | "list";

interface FileExplorerProps {
  onFileSelect: (fileId: number) => void;
}

export const FileExplorer: FC<FileExplorerProps> = ({ onFileSelect }) => {
  const [viewMode, setViewMode] = useState<ViewMode>("department");
  const { tree, treeLoading, treeError, files, filesLoading, filesError, refresh } = useFiles();

  const [showNewFolder, setShowNewFolder] = useState(false);
  const [newFolderDept, setNewFolderDept] = useState("");
  const [newFolderName, setNewFolderName] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderError, setNewFolderError] = useState<string | null>(null);

  const [showUpload, setShowUpload] = useState(false);
  const [uploadDept, setUploadDept] = useState("");
  const [uploadSub, setUploadSub] = useState("");
  const [uploadFileState, setUploadFileState] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loading = viewMode === "department" ? treeLoading : filesLoading;
  const error = viewMode === "department" ? treeError : filesError;

  // Restore last selected file on mount
  useEffect(() => {
    const lastFileId = localStorage.getItem("eaip-last-file");
    if (lastFileId) {
      onFileSelect(Number(lastFileId));
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFileSelect = useCallback((fileId: number) => {
    localStorage.setItem("eaip-last-file", String(fileId));
    onFileSelect(fileId);
  }, [onFileSelect]);

  const handleOpenInFolder = useCallback((node: TreeNodeType) => {
    // Call backend to open Windows Explorer at the file/folder location
    if (node.type === "file" && node.fileId != null) {
      revealFileInExplorer(node.fileId).catch(() => {
        // silently fail if backend can't open explorer
      });
    }
  }, []);

  const handleCreateFolder = async () => {
    if (!newFolderDept || !newFolderName.trim()) return;
    setCreatingFolder(true);
    setNewFolderError(null);
    try {
      const name = newFolderName.trim().replace(/\s+/g, "_").toLowerCase();
      await createFolder(newFolderDept, name);
      DEPARTMENTS[newFolderDept].push(name);
      DEPARTMENTS[newFolderDept].sort();
      setShowNewFolder(false);
      setNewFolderDept("");
      setNewFolderName("");
      refresh();
    } catch (err) {
      setNewFolderError(err instanceof Error ? err.message : "Failed to create folder");
    } finally {
      setCreatingFolder(false);
    }
  };

  const handleUpload = async () => {
    if (!uploadFileState || !uploadDept || !uploadSub) return;
    setUploading(true);
    setUploadError(null);
    try {
      await uploadFile(uploadFileState, uploadDept, uploadSub);
      setShowUpload(false);
      setUploadFileState(null);
      setUploadDept("");
      setUploadSub("");
      refresh();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const renderToggle = () => (
    <div className="flex gap-1 px-3 pb-2">
      <Button
        variant={viewMode === "department" ? "default" : "secondary"}
        size="xs"
        onClick={() => setViewMode("department")}
        className="flex-1"
      >
        Departments
      </Button>
      <Button
        variant={viewMode === "list" ? "default" : "secondary"}
        size="xs"
        onClick={() => setViewMode("list")}
        className="flex-1"
      >
        All Files
      </Button>
    </div>
  );

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-32 text-muted-foreground text-sm">
          <svg className="animate-spin w-4 h-4 mr-2 text-primary" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading files...
        </div>
      );
    }

    if (error) {
      return (
        <div className="p-4 text-sm">
          <p className="text-destructive mb-2">Failed to load files</p>
          <p className="text-muted-foreground text-xs mb-3">{error}</p>
          <Button variant="secondary" size="xs" onClick={refresh}>
            Retry
          </Button>
        </div>
      );
    }

    if (viewMode === "department") {
      if (tree.length === 0) {
        return (
          <div className="p-4 text-muted-foreground text-sm">
            No departments found. Run a sync to populate the file tree.
          </div>
        );
      }
      return (
        <div role="tree" aria-label="File explorer">
          {tree.map((node) => (
            <TreeNode key={node.id} node={node} depth={0} onFileSelect={handleFileSelect} onOpenInFolder={handleOpenInFolder} />
          ))}
        </div>
      );
    }

    if (files.length === 0) {
      return (
        <div className="p-4 text-muted-foreground text-sm">
          No files found. Run a sync to populate.
        </div>
      );
    }

    return (
      <div className="space-y-0.5 px-2">
        {files.map((file) => (
          <div
            key={file.id}
            role="button"
            tabIndex={0}
            onClick={() => handleFileSelect(file.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleFileSelect(file.id); }
            }}
            className="flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded hover:bg-muted text-sm text-foreground transition-colors"
          >
            {(() => {
              const Icon = getFileIcon(file.name);
              const color = getFileColor(file.name);
              return <Icon className={`w-4 h-4 shrink-0 ${color}`} />;
            })()}
            <div className="flex flex-col min-w-0">
              <span className="truncate">{file.name}</span>
              <span className="text-[11px] text-muted-foreground truncate">{file.department}</span>
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full">
      <div className="py-2 flex-1 overflow-hidden flex flex-col">
        {renderToggle()}
        <ScrollArea className="flex-1">
          {renderContent()}
        </ScrollArea>
      </div>

      <div className="px-3 pb-3 flex gap-2">
        <Button
          onClick={() => { setNewFolderDept(""); setNewFolderName(""); setNewFolderError(null); setShowNewFolder(true); }}
          variant="secondary"
          className="flex-1"
          size="sm"
        >
          <FolderPlus className="size-4" />
          New Folder
        </Button>
        <Button
          onClick={() => setShowUpload(true)}
          className="flex-1"
          size="sm"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
          </svg>
          Upload
        </Button>
      </div>

      {showNewFolder && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => { if (!creatingFolder) setShowNewFolder(false); }}>
          <div
            className="bg-card border border-border rounded-xl shadow-2xl w-[400px] max-w-full mx-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">New Folder</h3>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => setShowNewFolder(false)}
                disabled={creatingFolder}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </Button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">Department</label>
                <select
                  value={newFolderDept}
                  onChange={(e) => setNewFolderDept(e.target.value)}
                  className="w-full bg-secondary border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-ring"
                >
                  <option value="">Select department...</option>
                  {Object.keys(DEPARTMENTS).map((d) => (
                    <option key={d} value={d}>{DEPARTMENT_LABELS[d] || d}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">Folder Name</label>
                <Input
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleCreateFolder(); }}
                  placeholder="e.g. monthly_reports"
                  disabled={creatingFolder}
                />
                <p className="text-[11px] text-muted-foreground mt-1">Spaces will be replaced with underscores</p>
              </div>

              {newFolderError && (
                <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                  {newFolderError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border">
              <Button
                variant="secondary"
                onClick={() => setShowNewFolder(false)}
                disabled={creatingFolder}
              >
                Cancel
              </Button>
              <Button
                onClick={handleCreateFolder}
                disabled={!newFolderDept || !newFolderName.trim() || creatingFolder}
              >
                {creatingFolder ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Creating...
                  </>
                ) : (
                  "Create"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}

      {showUpload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => { if (!uploading) setShowUpload(false); }}>
          <div
            className="bg-card border border-border rounded-xl shadow-2xl w-[400px] max-w-full mx-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h3 className="text-sm font-semibold text-foreground">Upload File</h3>
              <Button
                variant="ghost"
                size="icon-xs"
                onClick={() => setShowUpload(false)}
                disabled={uploading}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </Button>
            </div>

            <div className="p-5 space-y-4">
              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">Department</label>
                <select
                  value={uploadDept}
                  onChange={(e) => { setUploadDept(e.target.value); setUploadSub(""); }}
                  className="w-full bg-secondary border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-ring"
                >
                  <option value="">Select department...</option>
                  {Object.keys(DEPARTMENTS).map((d) => (
                    <option key={d} value={d}>{DEPARTMENT_LABELS[d] || d}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">Subfolder</label>
                <select
                  value={uploadSub}
                  onChange={(e) => setUploadSub(e.target.value)}
                  disabled={!uploadDept}
                  className="w-full bg-secondary border border-input rounded-lg px-3 py-2 text-sm text-foreground focus:outline-none focus:border-ring disabled:opacity-50"
                >
                  <option value="">Select subfolder...</option>
                  {uploadDept && DEPARTMENTS[uploadDept]?.map((s) => (
                    <option key={s} value={s}>{s.replace(/_/g, " ")}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-muted-foreground mb-1.5">File</label>
                <Input
                  ref={fileInputRef}
                  type="file"
                  onChange={(e) => setUploadFileState(e.target.files?.[0] ?? null)}
                />
              </div>

              {uploadError && (
                <div className="text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg px-3 py-2">
                  {uploadError}
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 px-5 py-4 border-t border-border">
              <Button
                variant="secondary"
                onClick={() => setShowUpload(false)}
                disabled={uploading}
              >
                Cancel
              </Button>
              <Button
                onClick={handleUpload}
                disabled={!uploadFileState || !uploadDept || !uploadSub || uploading}
              >
                {uploading ? (
                  <>
                    <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Uploading...
                  </>
                ) : (
                  "Upload"
                )}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default FileExplorer;
