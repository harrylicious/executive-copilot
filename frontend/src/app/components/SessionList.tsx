import { useEffect, useState, useCallback } from "react";
import { getSessions, deleteSession } from "../../api/kb";
import type { ChatSessionSummary } from "../../types";
import { MessageSquare, Trash2, Plus, PanelLeftClose, Loader2 } from "lucide-react";
import { cn } from "./ui/utils";

const PAGE_SIZE = 20;

interface SessionListProps {
  activeSessionId?: string;
  onSelect: (sessionId: string) => void;
  onNewSession: () => void;
  onClose: () => void;
  refreshKey?: number;
}

export function SessionList({
  activeSessionId,
  onSelect,
  onNewSession,
  onClose,
  refreshKey,
}: SessionListProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);

  // Load the first page on mount or when refreshKey changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCurrentPage(1);
    getSessions({ page: 1, page_size: PAGE_SIZE })
      .then((data) => {
        if (!cancelled) {
          setSessions(data.items);
          setHasMore(data.has_more);
          setTotal(data.total);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSessions([]);
          setHasMore(false);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  // Load more sessions (next page)
  const handleLoadMore = useCallback(async () => {
    const nextPage = currentPage + 1;
    setLoadingMore(true);
    try {
      const data = await getSessions({ page: nextPage, page_size: PAGE_SIZE });
      setSessions((prev) => [...prev, ...data.items]);
      setHasMore(data.has_more);
      setTotal(data.total);
      setCurrentPage(nextPage);
    } catch {
      // Keep existing sessions on error
    } finally {
      setLoadingMore(false);
    }
  }, [currentPage]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
      setTotal((prev) => Math.max(0, prev - 1));
    } catch {
      // silently fail
    }
  };

  return (
    <div className="w-64 border-r border-border flex flex-col shrink-0 bg-card/50">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border shrink-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Riwayat Chat {total > 0 && `(${total})`}
        </span>
        <div className="flex items-center gap-1">
          <button
            onClick={onNewSession}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Chat baru"
          >
            <Plus className="size-3.5" />
          </button>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title="Tutup sidebar"
          >
            <PanelLeftClose className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="size-4 animate-spin text-muted-foreground mr-2" />
            <span className="text-xs text-muted-foreground">Memuat...</span>
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex items-center justify-center px-4 py-8">
            <p className="text-xs text-muted-foreground text-center">
              Belum ada riwayat chat. Mulai percakapan baru untuk menyimpannya di sini.
            </p>
          </div>
        ) : (
          <>
            {sessions.map((session) => (
              <button
                key={session.id}
                onClick={() => onSelect(session.id)}
                className={cn(
                  "w-full text-left px-3 py-2.5 hover:bg-muted/50 border-b border-border/50 group flex items-start gap-2.5 transition-colors",
                  activeSessionId === session.id && "bg-muted/30 border-l-2 border-l-primary"
                )}
              >
                <MessageSquare className="size-3.5 mt-0.5 text-muted-foreground shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-foreground truncate">
                    {session.title || "Tanpa judul"}
                  </p>
                  {session.updatedAt && (
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {new Date(session.updatedAt).toLocaleDateString("id-ID", {
                        day: "numeric",
                        month: "short",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  )}
                </div>
                <button
                  onClick={(e) => handleDelete(e, session.id)}
                  className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-all shrink-0"
                  title="Hapus sesi"
                >
                  <Trash2 className="size-3" />
                </button>
              </button>
            ))}

            {/* Load More button */}
            {hasMore && (
              <div className="px-3 py-3 border-t border-border/50">
                {loadingMore ? (
                  <div className="flex items-center justify-center py-1">
                    <Loader2 className="size-3.5 animate-spin text-muted-foreground mr-2" />
                    <span className="text-xs text-muted-foreground">Memuat...</span>
                  </div>
                ) : (
                  <button
                    onClick={handleLoadMore}
                    className="w-full text-center text-xs text-primary hover:text-primary/80 font-medium py-1.5 rounded hover:bg-muted/50 transition-colors"
                  >
                    Muat Lebih Banyak
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
