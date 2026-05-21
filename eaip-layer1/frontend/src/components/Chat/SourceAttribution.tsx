import { useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { FileText, ExternalLink } from "lucide-react";
import type { SourceAttribution as SourceType, FileNode } from "@/types";
import { cn } from "@/lib/utils";
import { getFile } from "@/api/client";
import { FilePreviewModal } from "./FilePreviewModal";

interface Props {
  sources: SourceType[];
}

export function SourceAttribution({ sources }: Props) {
  const navigate = useNavigate();
  const [previewFile, setPreviewFile] = useState<FileNode | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [loadingPreview, setLoadingPreview] = useState(false);

  // Deduplicate by fileId (show unique files, aggregate chunk info)
  const grouped = sources.reduce<
    Map<number, { source: SourceType; chunks: number[] }>
  >((acc, source) => {
    const existing = acc.get(source.fileId);
    if (existing) {
      existing.chunks.push(source.chunkIndex);
    } else {
      acc.set(source.fileId, { source, chunks: [source.chunkIndex] });
    }
    return acc;
  }, new Map());

  const entries = [...grouped.values()];

  const handlePreview = useCallback(async (fileId: number) => {
    setLoadingPreview(true);
    try {
      const file = await getFile(fileId);
      setPreviewFile(file);
      setPreviewOpen(true);
    } catch {
      // fallback: navigate to explorer
      navigate(`/?fileId=${fileId}`);
    } finally {
      setLoadingPreview(false);
    }
  }, [navigate]);

  const handleOpenInExplorer = useCallback((e: React.MouseEvent, fileId: number) => {
    e.stopPropagation();
    navigate(`/?fileId=${fileId}`);
  }, [navigate]);

  return (
    <>
      <div className="space-y-1.5 pt-2">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
          Sources ({entries.length})
        </span>
        <div className="flex flex-col gap-1">
          {entries.map(({ source, chunks }) => (
            <div
              key={source.fileId}
              onClick={() => handlePreview(source.fileId)}
              className={cn(
                "group flex items-start gap-2 px-2.5 py-1.5 rounded-md text-left w-full",
                "border border-border bg-muted/30 hover:bg-muted hover:border-primary/30",
                "transition-colors cursor-pointer",
                loadingPreview && "opacity-60 pointer-events-none"
              )}
            >
              <FileText className="size-3.5 text-muted-foreground shrink-0 mt-0.5 group-hover:text-primary transition-colors" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-xs font-medium text-foreground truncate">
                    {source.fileName}
                  </span>
                  {/* External link icon — navigates to Explorer */}
                  <button
                    onClick={(e) => handleOpenInExplorer(e, source.fileId)}
                    className="shrink-0 p-0.5 rounded hover:bg-primary/10 transition-colors opacity-0 group-hover:opacity-100"
                    title="Open in Explorer"
                    aria-label="Open in Explorer"
                  >
                    <ExternalLink className="size-3 text-muted-foreground hover:text-primary transition-colors" />
                  </button>
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[10px] text-muted-foreground">
                    {source.department.replace(/_/g, " ")}
                  </span>
                  <span className="text-[10px] text-muted-foreground/60">·</span>
                  <span className="text-[10px] text-muted-foreground">
                    {chunks.length === 1
                      ? `chunk ${chunks[0]}`
                      : `chunks ${chunks.join(", ")}`}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* File Preview Modal */}
      <FilePreviewModal
        file={previewFile}
        open={previewOpen}
        onOpenChange={setPreviewOpen}
      />
    </>
  );
}
