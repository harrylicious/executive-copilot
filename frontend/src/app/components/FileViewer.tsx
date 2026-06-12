import { useState, useMemo, useEffect, lazy, Suspense } from "react";
import { X, FileText, FileSpreadsheet, Download, Loader2 } from "lucide-react";
import { getFileContentUrl } from "../../api/files";
import { detectFormat } from "../../utils/fileFormat";

export interface FileViewerDoc {
  id: string;
  name: string;
  type: string;
  size: string;
  dept: string;
  uploadedBy: string;
  uploadedAt: string;
  status?: string;
  pages?: number;
  chunks?: number;
}

const PdfViewer = lazy(() => import("./explorer/PdfViewer"));
const ExcelViewer = lazy(() => import("./explorer/ExcelViewer"));
const DocxViewer = lazy(() => import("./explorer/DocxViewer"));
const JsonViewer = lazy(() => import("./explorer/JsonViewer"));
const MarkdownViewer = lazy(() => import("./explorer/MarkdownViewer"));
const PlainTextViewer = lazy(() => import("./explorer/PlainTextViewer"));
const CsvViewer = lazy(() => import("./explorer/CsvViewer"));

function ViewerFallback({ fileId, format }: { fileId: number; format: string }) {
  const [textContent, setTextContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    setTextContent(null);
    fetch(getFileContentUrl(fileId))
      .then((r) => (r.ok ? r.text() : null))
      .then((t) => { if (!cancelled) { if (t) setTextContent(t); else setError(true); } })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fileId]);

  if (loading) return <div className="flex items-center justify-center py-10"><Loader2 size={20} className="animate-spin text-muted-foreground" /></div>;
  if (error) return <div className="text-sm text-muted-foreground text-center py-10">Preview not available for {format.toUpperCase()} files</div>;
  return (
    <div className="bg-background rounded-xl border border-border p-4">
      <pre className="text-xs text-secondary-foreground font-mono whitespace-pre-wrap break-words leading-relaxed">
        {textContent?.slice(0, 5000)}
      </pre>
    </div>
  );
}

export function FileViewer({ doc, onClose }: { doc: FileViewerDoc | null; onClose: () => void }) {
  const fileId = useMemo(() => Number(doc?.id), [doc?.id]);
  const format = useMemo(() => doc ? detectFormat(doc.name) : null, [doc]);

  const ext = doc?.name.split(".").pop()?.toLowerCase() || "";
  const isSheet = ["xlsx", "xls", "csv"].includes(ext);
  const iconColor = doc?.type === "pdf" ? "#f85149" : "#10b981";

  let viewer: React.ReactNode = null;
  if (doc && !isNaN(fileId) && fileId > 0 && format) {
    switch (format) {
      case "pdf": viewer = <PdfViewer fileId={fileId} />; break;
      case "xlsx": viewer = <ExcelViewer fileId={fileId} />; break;
      case "docx": viewer = <DocxViewer fileId={fileId} />; break;
      case "json": viewer = <JsonViewer fileId={fileId} />; break;
      case "md": viewer = <MarkdownViewer fileId={fileId} />; break;
      case "txt": viewer = <PlainTextViewer fileId={fileId} />; break;
      case "csv": viewer = <CsvViewer fileId={fileId} />; break;
      default: viewer = <ViewerFallback fileId={fileId} format={format} />;
    }
  } else if (doc && !isNaN(fileId) && fileId > 0 && !format) {
    // File name has no recognized extension — try generic fallback preview
    viewer = <ViewerFallback fileId={fileId} format={ext || "unknown"} />;
  }

  if (!doc) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60" onClick={onClose}>
      <div className="bg-card border border-border rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col" onClick={e => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-xl flex items-center justify-center shrink-0" style={{ background: `${iconColor}18` }}>
              {isSheet
                ? <FileSpreadsheet size={16} style={{ color: iconColor }} />
                : <FileText size={16} style={{ color: iconColor }} />
              }
            </div>
            <div className="min-w-0">
              <h3 className="text-foreground text-sm font-medium truncate">{doc.name}</h3>
              <div className="text-muted-foreground text-xs">
                {doc.dept} · {doc.size}
                {doc.pages ? ` · ${doc.pages} halaman` : ""}
                {doc.chunks ? ` · ${doc.chunks} chunks` : ""}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1">
            <a href={getFileContentUrl(fileId)} download={doc.name}
              className="text-muted-foreground hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-secondary transition-colors inline-flex">
              <Download size={14} />
            </a>
            <button onClick={onClose} className="text-muted-foreground hover:text-secondary-foreground p-1.5 rounded-lg hover:bg-secondary transition-colors">
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 min-h-0 overflow-hidden">
          {viewer ? (
            <Suspense fallback={
              <div className="flex items-center justify-center h-full py-16">
                <Loader2 size={20} className="animate-spin text-muted-foreground" />
              </div>
            }>
              <div className="h-full overflow-hidden">
                {viewer}
              </div>
            </Suspense>
          ) : (
            <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
              <FileText size={40} className="mb-3 opacity-30" />
              <p className="text-sm">Pratinjau tidak tersedia</p>
              <p className="text-xs mt-1">Gunakan tombol unduh untuk membuka file.</p>
            </div>
          )}
        </div>

        {/* Metadata footer */}
        <div className="shrink-0 px-4 py-3 border-t border-border grid grid-cols-4 gap-3 text-xs text-muted-foreground">
          <div>
            <span className="block text-muted-foreground">Diunggah oleh</span>
            <span className="text-secondary-foreground">{doc.uploadedBy || "—"}</span>
          </div>
          <div>
            <span className="block text-muted-foreground">Tanggal</span>
            <span className="text-secondary-foreground">{doc.uploadedAt || "—"}</span>
          </div>
          <div>
            <span className="block text-muted-foreground">Departemen</span>
            <span className="text-secondary-foreground">{doc.dept}</span>
          </div>
          <div>
            <span className="block text-muted-foreground">Status</span>
            <span className="text-secondary-foreground">{doc.status === "processed" ? "Selesai diproses" : doc.status || "Tersedia"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
