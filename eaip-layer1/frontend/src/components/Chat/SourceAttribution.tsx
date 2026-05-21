import { useNavigate } from "react-router-dom";
import { FileText, ExternalLink } from "lucide-react";
import type { SourceAttribution as SourceType } from "@/types";
import { cn } from "@/lib/utils";

interface Props {
  sources: SourceType[];
}

export function SourceAttribution({ sources }: Props) {
  const navigate = useNavigate();

  const handleClick = (source: SourceType) => {
    navigate(`/?fileId=${source.fileId}`);
  };

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

  return (
    <div className="space-y-1.5 pt-2">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-medium">
        Sources ({entries.length})
      </span>
      <div className="flex flex-col gap-1">
        {entries.map(({ source, chunks }) => (
          <button
            key={source.fileId}
            onClick={() => handleClick(source)}
            className={cn(
              "group flex items-start gap-2 px-2.5 py-1.5 rounded-md text-left w-full",
              "border border-border bg-muted/30 hover:bg-muted hover:border-primary/30",
              "transition-colors cursor-pointer"
            )}
          >
            <FileText className="size-3.5 text-muted-foreground shrink-0 mt-0.5 group-hover:text-primary transition-colors" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs font-medium text-foreground truncate">
                  {source.fileName}
                </span>
                <ExternalLink className="size-2.5 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity shrink-0" />
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
          </button>
        ))}
      </div>
    </div>
  );
}
