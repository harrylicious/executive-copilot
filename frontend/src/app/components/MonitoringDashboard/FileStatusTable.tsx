import { ChevronLeft, ChevronRight } from "lucide-react";
import type { FileStatus } from "./hooks";

interface FileStatusTableProps {
  files: FileStatus[];
  totalCount: number;
  page: number;
  loading: boolean;
  onPageChange: (page: number) => void;
  onFileSelect?: (file: FileStatus) => void;
}

const PAGE_SIZE = 25;

const statusBadgeConfig: Record<string, { label: string; className: string }> = {
  embedded: { label: "Embedded", className: "bg-green-500/10 text-green-500 border-green-500/20" },
  embedding: { label: "Embedding", className: "bg-blue-500/10 text-blue-500 border-blue-500/20" },
  pending: { label: "Pending", className: "bg-yellow-500/10 text-yellow-500 border-yellow-500/20" },
  stale: { label: "Stale", className: "bg-orange-500/10 text-orange-500 border-orange-500/20" },
  failed: { label: "Failed", className: "bg-red-500/10 text-red-500 border-red-500/20" },
};

function StatusBadge({ status }: { status: string | null }) {
  if (!status) {
    return (
      <span className="inline-flex items-center px-2 py-0.5 rounded-md text-xs border bg-secondary/50 text-muted-foreground border-border">
        Unknown
      </span>
    );
  }

  const config = statusBadgeConfig[status] ?? {
    label: status,
    className: "bg-secondary/50 text-muted-foreground border-border",
  };

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-md text-xs border ${config.className}`}>
      {config.label}
    </span>
  );
}

function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function TableSkeleton() {
  return (
    <div className="animate-pulse space-y-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4 py-3 border-b border-border">
          <div className="h-4 w-40 bg-secondary rounded" />
          <div className="h-4 w-24 bg-secondary rounded" />
          <div className="h-4 w-16 bg-secondary rounded" />
          <div className="h-4 w-8 bg-secondary rounded" />
          <div className="h-4 w-28 bg-secondary rounded" />
        </div>
      ))}
    </div>
  );
}

export function FileStatusTable({
  files = [],
  totalCount,
  page,
  loading,
  onPageChange,
  onFileSelect,
}: FileStatusTableProps) {
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));

  if (loading && files.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-4">
        <h3 className="text-foreground text-sm mb-4">Tracked Files</h3>
        <TableSkeleton />
      </div>
    );
  }

  if (!loading && files.length === 0) {
    return (
      <div className="bg-card border border-border rounded-xl p-6 flex flex-col items-center justify-center text-center">
        <p className="text-muted-foreground text-sm">No files are being tracked</p>
        <p className="text-muted-foreground text-xs mt-1">
          Files will appear here once they are added to the knowledge base.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="p-4 border-b border-border">
        <h3 className="text-foreground text-sm">Tracked Files</h3>
        <p className="text-muted-foreground text-xs mt-0.5">
          {totalCount} file{totalCount !== 1 ? "s" : ""} total
        </p>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground text-xs">
              <th className="px-4 py-3 font-medium">File Name</th>
              <th className="px-4 py-3 font-medium">Department</th>
              <th className="px-4 py-3 font-medium">Status</th>
              <th className="px-4 py-3 font-medium">Version</th>
              <th className="px-4 py-3 font-medium">Last Modified</th>
            </tr>
          </thead>
          <tbody>
            {files.map((file) => (
              <tr
                key={file.id}
                className="border-b border-border last:border-0 hover:bg-secondary/30 transition-colors cursor-pointer"
                onClick={() => onFileSelect?.(file)}
              >
                <td className="px-4 py-3">
                  <span className="text-secondary-foreground text-xs truncate block max-w-[200px]">
                    {file.name}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-muted-foreground text-xs">{file.department}</span>
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={file.embedding_status} />
                </td>
                <td className="px-4 py-3">
                  <span className="text-muted-foreground text-xs">
                    {file.current_version != null ? `v${file.current_version}` : "—"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className="text-muted-foreground text-xs">
                    {formatDate(file.modified_at)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border">
          <span className="text-muted-foreground text-xs">
            Page {page} of {totalPages}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="p-1.5 rounded-md hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Previous page"
            >
              <ChevronLeft size={14} className="text-muted-foreground" />
            </button>
            <button
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="p-1.5 rounded-md hover:bg-secondary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              aria-label="Next page"
            >
              <ChevronRight size={14} className="text-muted-foreground" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
