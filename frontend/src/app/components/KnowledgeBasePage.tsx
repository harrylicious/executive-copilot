import { useState, useRef, useEffect } from "react";
import {
  Upload, Trash2, Search,
  CheckCircle, Clock, AlertCircle, Eye, ChevronDown, List, Layers
} from "lucide-react";
import type { UserProfile } from "./Sidebar";
import { FileViewer } from "./FileViewer";
import { fetchFiles, uploadFile, deleteFile, type BackendFile } from "../../api/files";
import { getFileIcon } from "../../utils/fileIcons";

interface Doc {
  id: string;
  name: string;
  type: string;
  extension: string;
  size: string;
  dept: string;
  uploadedBy: string;
  uploadedAt: string;
  status: "processed" | "processing" | "failed";
  pages?: number;
  chunks?: number;
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function mapStatus(syncStatus: string | null): Doc["status"] {
  if (!syncStatus || syncStatus === "synced" || syncStatus === "indexed") return "processed";
  if (syncStatus === "pending" || syncStatus === "modified") return "processing";
  return "failed";
}

function getExtension(name: string): string {
  const parts = name.split(".");
  return parts.length > 1 ? parts[parts.length - 1].toLowerCase() : "";
}

function mapType(fileType: string | null, name: string): string {
  const ext = fileType?.toLowerCase() || getExtension(name);
  return ext || "other";
}

function toDoc(f: BackendFile): Doc {
  const ext = f.file_type?.toLowerCase() || getExtension(f.name);
  return {
    id: String(f.id),
    name: f.name,
    type: mapType(f.file_type, f.name),
    extension: ext,
    size: formatSize(f.size),
    dept: f.department,
    uploadedBy: "",
    uploadedAt: f.created_at ? f.created_at.split("T")[0] : "",
    status: mapStatus(f.sync_status),
  };
}

const STATUS_CONFIG = {
  processed: { label: "Selesai", color: "#10b981", bg: "rgba(16,185,129,0.1)", icon: CheckCircle },
  processing: { label: "Memproses", color: "#f59e0b", bg: "rgba(245,158,11,0.1)", icon: Clock },
  failed: { label: "Gagal", color: "#f85149", bg: "rgba(248,81,73,0.1)", icon: AlertCircle },
};

const FILE_TYPE_CATEGORIES: { label: string; extensions: string[] }[] = [
  { label: "PDF", extensions: ["pdf"] },
  { label: "XLSX", extensions: ["xlsx", "xls"] },
  { label: "CSV", extensions: ["csv"] },
  { label: "DOCX", extensions: ["docx"] },
  { label: "TXT", extensions: ["txt"] },
  { label: "Other", extensions: [] },
];

function getFileTypeCategory(ext: string): string {
  for (const cat of FILE_TYPE_CATEGORIES) {
    if (cat.extensions.includes(ext)) return cat.label;
  }
  return "Other";
}

type ViewMode = "flat" | "grouped";
type GroupBy = "type" | "department";

interface Props { user: UserProfile; }

export function KnowledgeBasePage({ user }: Props) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterDept, setFilterDept] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [viewingDoc, setViewingDoc] = useState<Doc | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("flat");
  const [groupBy, setGroupBy] = useState<GroupBy>("type");
  const [collapsedSections, setCollapsedSections] = useState<Set<string>>(new Set());
  const fileRef = useRef<HTMLInputElement>(null);

  const isExecOrAdmin = user.role === "executive" || user.role === "admin";

  useEffect(() => {
    setLoading(true);
    fetchFiles()
      .then(files => setDocs(files.map(toDoc)))
      .catch(() => setDocs([]))
      .finally(() => setLoading(false));
  }, []);

  const visibleDocs = docs.filter(d => {
    if (!isExecOrAdmin && d.dept !== user.department) return false;
    if (filterDept !== "all" && d.dept !== filterDept) return false;
    if (filterStatus !== "all" && d.status !== filterStatus) return false;
    if (search && !d.name.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const depts = isExecOrAdmin ? ["all", ...new Set(docs.map(d => d.dept))] : [user.department];

  const toggleSection = (section: string) => {
    setCollapsedSections(prev => {
      const next = new Set(prev);
      if (next.has(section)) {
        next.delete(section);
      } else {
        next.add(section);
      }
      return next;
    });
  };

  const groupedByType = () => {
    const groups: { label: string; docs: Doc[] }[] = [];
    for (const cat of FILE_TYPE_CATEGORIES) {
      const groupDocs = cat.label === "Other"
        ? visibleDocs.filter(d => {
            const knownExts = FILE_TYPE_CATEGORIES.flatMap(c => c.extensions);
            return !knownExts.includes(d.extension);
          })
        : visibleDocs.filter(d => cat.extensions.includes(d.extension));
      if (groupDocs.length > 0) {
        groups.push({ label: cat.label, docs: groupDocs });
      }
    }
    return groups;
  };

  const groupedByDepartment = () => {
    const deptMap = new Map<string, Doc[]>();
    for (const doc of visibleDocs) {
      const existing = deptMap.get(doc.dept) || [];
      existing.push(doc);
      deptMap.set(doc.dept, existing);
    }
    return Array.from(deptMap.entries())
      .filter(([, docs]) => docs.length > 0)
      .map(([dept, docs]) => ({ label: dept, docs }));
  };

  const realUpload = async (file: File) => {
    setUploading(true);
    setUploadProgress(0);
    const interval = setInterval(() => {
      setUploadProgress(p => Math.min(p + 15, 90));
    }, 200);
    try {
      const result = await uploadFile(file, user.department, "uploads");
      clearInterval(interval);
      setUploadProgress(100);
      setDocs(prev => [toDoc(result), ...prev]);
      setTimeout(() => setUploadProgress(0), 500);
    } catch {
      clearInterval(interval);
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) realUpload(file);
  };

  const handleDelete = async (id: string) => {
    setDocs(prev => prev.filter(d => d.id !== id));
    try { await deleteFile(Number(id)); } catch { /* ignore */ }
  };

  const totalChunks = visibleDocs.filter(d => d.status === "processed").reduce((s, d) => s + (d.chunks || 0), 0);

  const renderDocRow = (doc: Doc, i: number) => {
    const iconInfo = getFileIcon(doc.extension);
    const Icon = iconInfo.icon;
    const color = iconInfo.color;
    const st = STATUS_CONFIG[doc.status];
    return (
      <div key={doc.id} className="px-4 py-3 grid grid-cols-12 gap-4 items-center border-b border-border last:border-0 hover:bg-[rgba(255,255,255,0.02)] transition-colors">
        <div className="col-span-5 flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0" style={{ background: `${color}18` }}>
            <Icon size={15} style={{ color }} />
          </div>
          <div className="min-w-0">
            <div className="text-secondary-foreground text-xs font-medium truncate">{doc.name}</div>
            <div className="text-muted-foreground text-[11px]">{doc.size}{doc.chunks ? ` · ${doc.chunks} chunks` : ""}</div>
          </div>
        </div>
        {isExecOrAdmin && (
          <div className="col-span-2">
            <span className="text-[#10b981] text-xs bg-primary/10 px-2 py-0.5 rounded">{doc.dept}</span>
          </div>
        )}
        <div className={isExecOrAdmin ? "col-span-2" : "col-span-3"}>
          <div className="text-secondary-foreground text-xs">{doc.uploadedBy.split(" ")[0]}</div>
          <div className="text-muted-foreground text-[11px]">{doc.uploadedAt}</div>
        </div>
        <div className="col-span-2">
          <div className="flex items-center gap-1.5" style={{ color: st.color }}>
            <st.icon size={11} />
            <span className="text-xs">{st.label}</span>
          </div>
        </div>
        <div className="col-span-1 flex justify-end gap-1">
          <button onClick={() => setViewingDoc(doc)} className="text-muted-foreground hover:text-secondary-foreground p-1 rounded transition-colors"><Eye size={13} /></button>
          {doc.status !== "processing" && (
            <button onClick={() => handleDelete(doc.id)} className="text-muted-foreground hover:text-[#f85149] p-1 rounded transition-colors">
              <Trash2 size={13} />
            </button>
          )}
        </div>
      </div>
    );
  };

  const renderGroupedSection = (label: string, groupDocs: Doc[]) => {
    const isCollapsed = collapsedSections.has(label);
    return (
      <div key={label} className="border-b border-border last:border-0">
        <button
          onClick={() => toggleSection(label)}
          className="w-full px-4 py-3 flex items-center gap-2 hover:bg-[rgba(255,255,255,0.02)] transition-colors"
        >
          <ChevronDown
            size={14}
            className={`text-muted-foreground transition-transform ${isCollapsed ? "-rotate-90" : ""}`}
          />
          <span className="text-secondary-foreground text-sm font-medium">{label}</span>
          <span className="text-muted-foreground text-xs bg-input border border-border rounded-full px-2 py-0.5">
            {groupDocs.length}
          </span>
        </button>
        {!isCollapsed && (
          <div>
            {groupDocs.map((doc, i) => renderDocRow(doc, i))}
          </div>
        )}
      </div>
    );
  };

  const renderDocList = () => {
    if (visibleDocs.length === 0) {
      const { icon: FileIcon, color: fileColor } = getFileIcon("txt");
      return (
        <div className="py-16 text-center text-muted-foreground text-sm">
          <FileIcon size={32} className="mx-auto mb-3 opacity-30" />
          Belum ada dokumen. Unggah file pertama Anda.
        </div>
      );
    }

    if (viewMode === "flat") {
      return visibleDocs.map((doc, i) => renderDocRow(doc, i));
    }

    const groups = groupBy === "type" ? groupedByType() : groupedByDepartment();
    return groups.map(group => renderGroupedSection(group.label, group.docs));
  };

  return (
    <div className="p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-foreground mb-1">Knowledge Base</h1>
          <p className="text-muted-foreground text-sm">
            {isExecOrAdmin ? "Kelola semua dokumen seluruh departemen." : `Kelola dokumen departemen ${user.department}.`}
          </p>
        </div>
        <div className="flex gap-2">
          <div className="flex items-center gap-3">
            {[
              { label: "Dokumen", val: visibleDocs.length.toString() },
              { label: "Chunks", val: totalChunks.toString() },
              { label: "Diproses", val: visibleDocs.filter(d => d.status === "processed").length.toString() },
            ].map(s => (
              <div key={s.label} className="text-center bg-card border border-border rounded-lg px-3 py-2">
                <div className="text-[#10b981] text-sm font-light">{s.val}</div>
                <div className="text-muted-foreground text-[10px]">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Upload zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => fileRef.current?.click()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all mb-6 ${
          dragging
            ? "border-[#059669] bg-[rgba(5,150,105,0.05)]"
            : "border-[rgba(255,255,255,0.1)] hover:border-[rgba(255,255,255,0.2)] bg-card"
        }`}>
        <input ref={fileRef} type="file" className="hidden" accept=".pdf,.xlsx,.csv,.docx,.txt"
          onChange={e => { const f = e.target.files?.[0]; if (f) realUpload(f); }} />
        {uploading ? (
          <div className="max-w-xs mx-auto">
            <div className="text-secondary-foreground text-sm mb-3">Mengunggah dokumen...</div>
            <div className="bg-input rounded-full h-1.5">
              <div className="bg-[#059669] h-1.5 rounded-full transition-all" style={{ width: `${uploadProgress}%` }} />
            </div>
            <div className="text-muted-foreground text-xs mt-2">{uploadProgress}%</div>
          </div>
        ) : (
          <>
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mx-auto mb-3">
              <Upload size={22} className="text-[#10b981]" />
            </div>
            <p className="text-secondary-foreground text-sm mb-1">Seret & lepas file di sini, atau <span className="text-[#10b981]">pilih file</span></p>
            <p className="text-muted-foreground text-xs">PDF, XLSX, CSV, DOCX, TXT — maks. 50MB per file</p>
            {!isExecOrAdmin && (
              <div className="mt-3 inline-flex items-center gap-1.5 bg-secondary border border-border rounded-lg px-3 py-1.5">
                <span className="text-muted-foreground text-xs">Akan diunggah ke:</span>
                <span className="text-[#10b981] text-xs font-medium">{user.department}</span>
              </div>
            )}
          </>
        )}
      </div>

      {/* Filters + View Mode Toggle */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-48">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Cari dokumen..."
            className="w-full bg-input border border-border text-secondary-foreground text-sm rounded-lg pl-9 pr-3 py-2 focus:outline-none focus:border-[#059669] placeholder-[#8b949e]" />
        </div>
        {isExecOrAdmin && (
          <select value={filterDept} onChange={e => setFilterDept(e.target.value)}
            className="bg-input border border-border text-secondary-foreground text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-[#059669]">
            {depts.map(d => <option key={d} value={d}>{d === "all" ? "Semua Departemen" : d}</option>)}
          </select>
        )}
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="bg-input border border-border text-secondary-foreground text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-[#059669]">
          <option value="all">Semua Status</option>
          <option value="processed">Selesai</option>
          <option value="processing">Memproses</option>
          <option value="failed">Gagal</option>
        </select>

        {/* View Mode Toggle */}
        <div className="flex items-center bg-input border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => setViewMode("flat")}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              viewMode === "flat"
                ? "bg-[#059669] text-white"
                : "text-muted-foreground hover:text-secondary-foreground"
            }`}
          >
            <List size={13} />
            Flat List
          </button>
          <button
            onClick={() => setViewMode("grouped")}
            className={`flex items-center gap-1.5 px-3 py-2 text-xs transition-colors ${
              viewMode === "grouped"
                ? "bg-[#059669] text-white"
                : "text-muted-foreground hover:text-secondary-foreground"
            }`}
          >
            <Layers size={13} />
            Grouped
          </button>
        </div>

        {/* Group By sub-options (visible only in grouped mode) */}
        {viewMode === "grouped" && (
          <div className="flex items-center bg-input border border-border rounded-lg overflow-hidden">
            <button
              onClick={() => setGroupBy("type")}
              className={`px-3 py-2 text-xs transition-colors ${
                groupBy === "type"
                  ? "bg-[#10b981] text-white"
                  : "text-muted-foreground hover:text-secondary-foreground"
              }`}
            >
              By File Type
            </button>
            <button
              onClick={() => setGroupBy("department")}
              className={`px-3 py-2 text-xs transition-colors ${
                groupBy === "department"
                  ? "bg-[#10b981] text-white"
                  : "text-muted-foreground hover:text-secondary-foreground"
              }`}
            >
              By Department
            </button>
          </div>
        )}
      </div>

      {/* Doc list */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        {viewMode === "flat" && (
          <div className="px-4 py-3 border-b border-border grid grid-cols-12 gap-4 text-muted-foreground text-xs">
            <div className="col-span-5">Dokumen</div>
            {isExecOrAdmin && <div className="col-span-2">Departemen</div>}
            <div className={isExecOrAdmin ? "col-span-2" : "col-span-3"}>Diunggah</div>
            <div className="col-span-2">Status</div>
            <div className="col-span-1 text-right">Aksi</div>
          </div>
        )}

        {renderDocList()}
      </div>
      <FileViewer doc={viewingDoc} onClose={() => setViewingDoc(null)} />
    </div>
  );
}
