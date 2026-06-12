import { useState, useRef, useCallback, useEffect } from "react";
import { Upload, FileUp, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { uploadFile } from "../../../api/ingestion";
import { fetchDepartments, type TreeNode } from "../../../api/departments";
import type { UploadResponse } from "../../../types/ingestion";

interface FileUploadProps {
  department?: string;
  onUploadComplete?: (response: UploadResponse) => void;
}

interface DeptOption {
  id: string;
  name: string;
}

/**
 * Flatten a department tree into a list of department options.
 * Only nodes with type "department" are included.
 * Extracts the internal department ID from the node.id field (format: "dept-{id}").
 */
function flattenDepartments(nodes: TreeNode[]): DeptOption[] {
  const result: DeptOption[] = [];
  for (const node of nodes) {
    if (node.type === "department") {
      const deptId = node.id?.replace(/^dept-/, "") || node.name;
      result.push({ id: deptId, name: node.name });
    }
    if (node.children) {
      result.push(...flattenDepartments(node.children));
    }
  }
  return result;
}

export function FileUpload({ department = "", onUploadComplete }: FileUploadProps) {
  const [dept, setDept] = useState(department);
  const [departments, setDepartments] = useState<DeptOption[]>([]);
  const [loadingDepts, setLoadingDepts] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  // Fetch departments on mount
  useEffect(() => {
    let cancelled = false;
    setLoadingDepts(true);
    fetchDepartments()
      .then((tree) => {
        if (!cancelled) {
          const depts = flattenDepartments(tree);
          setDepartments(depts);
          // Auto-select first department if none was provided
          if (!dept && depts.length > 0) {
            setDept(depts[0].id);
          }
        }
      })
      .catch(() => {
        // Silently fail — user can still type a department manually
      })
      .finally(() => {
        if (!cancelled) setLoadingDepts(false);
      });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleFile = useCallback(async (file: File) => {
    if (!dept.trim()) {
      setResult({ success: false, message: "Department is required" });
      return;
    }
    setUploading(true);
    setResult(null);
    try {
      const res = await uploadFile(file, dept.trim());
      setResult({ success: true, message: `Uploaded: ${file.name}` });
      onUploadComplete?.(res);
    } catch (err) {
      setResult({
        success: false,
        message: err instanceof Error ? err.message : "Upload failed",
      });
    } finally {
      setUploading(false);
    }
  }, [dept, onUploadComplete]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  }, [handleFile]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    if (inputRef.current) inputRef.current.value = "";
  }, [handleFile]);

  return (
    <div className="space-y-4">
      {/* Department selector */}
      <div className="flex items-center gap-2">
        <label className="text-xs text-muted-foreground shrink-0">Department:</label>
        {loadingDepts ? (
          <Loader2 size={14} className="animate-spin text-muted-foreground" />
        ) : departments.length > 0 ? (
          <select
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            className="flex-1 bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground focus:outline-none focus:border-primary/40 appearance-none"
          >
            <option value="">Select department...</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={dept}
            onChange={(e) => setDept(e.target.value)}
            placeholder="e.g., Finance"
            className="flex-1 bg-input border border-border rounded-lg px-3 py-1.5 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/40"
          />
        )}
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => inputRef.current?.click()}
        className={[
          "border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all",
          isDragOver
            ? "border-primary bg-primary/5"
            : "border-border hover:border-muted-foreground/30 bg-card",
        ].join(" ")}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.xlsx,.xls,.docx,.json,.md,.txt,.csv"
          className="hidden"
          onChange={handleInputChange}
        />

        {uploading ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 size={24} className="animate-spin text-primary" />
            <span className="text-sm text-muted-foreground">Uploading...</span>
          </div>
        ) : isDragOver ? (
          <div className="flex flex-col items-center gap-2">
            <FileUp size={24} className="text-primary" />
            <span className="text-sm text-foreground">Drop file here</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <Upload size={24} className="text-muted-foreground/40" />
            <span className="text-sm text-muted-foreground">
              Drag & drop files here
            </span>
            <span className="text-xs text-muted-foreground/60">
              or click to browse
            </span>
            <span className="text-[10px] text-muted-foreground/40 mt-1">
              PDF, XLSX, DOCX, JSON, MD, TXT, CSV
            </span>
          </div>
        )}
      </div>

      {/* Result feedback */}
      {result && (
        <div className={[
          "flex items-center gap-2 px-3 py-2 rounded-lg text-xs",
          result.success
            ? "bg-emerald-500/10 text-emerald-500 border border-emerald-500/20"
            : "bg-red-500/10 text-red-500 border border-red-500/20",
        ].join(" ")}>
          {result.success ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
          {result.message}
        </div>
      )}
    </div>
  );
}

export default FileUpload;
