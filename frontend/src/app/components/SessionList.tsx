import { useEffect, useState, useCallback, useMemo } from "react";
import { getSessions, deleteSession } from "../../api/kb";
import type { ChatSessionSummary } from "../../types";
import { MessageSquare, Trash2, Plus, PanelLeftClose, Loader2, Search, X } from "lucide-react";
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
  const [searchQuery, setSearchQuery] = useState("");

  // Load the first page on mount or when refreshKey changes
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setCurrentPage(1);
    setSearchQuery("");
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

  // Client-side search filtering
  const filteredSessions = useMemo(() => {
    if (!searchQuery.trim()) return sessions;
    const q = searchQuery.toLowerCase().trim();
    return sessions.filter((s) => s.title && s.title.toLowerCase().includes(q));
  }, [sessions, searchQuery]);

  const isSearching = searchQuery.trim().length > 0;
  const showEmptyState = !loading && sessions.length === 0;
  const showSearchEmpty = isSearching && filteredSessions.length === 0 && !loading;
  const showList = !loading && !showEmptyState && !showSearchEmpty;

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

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
  };

  const clearSearch = () => {
    setSearchQuery("");
  };

  return (
    <div className="w-64 border-r border-border/60 flex flex-col shrink-0 bg-card/40 backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-3 border-b border-border/50 shrink-0">
        <div className="flex items-center gap-2">
          <MessageSquare className="size-3.5 text-muted-foreground" />
          <span className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
            Riwayat
          </span>
          {total > 0 && (
            <span className="text-[10px] font-medium text-muted-foreground/60 bg-secondary/50 px-1.5 py-0.5 rounded-md tabular-nums">
              {isSearching ? `${filteredSessions.length}` : total}
            </span>
          )}
        </div>
        <div className="flex items-center gap-0.5">
          <button
            onClick={onNewSession}
            className="p-1.5 rounded-lg hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all"
            title="Chat baru"
          >
            <Plus className="size-3.5" />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-muted/80 text-muted-foreground hover:text-foreground transition-all"
            title="Tutup sidebar"
          >
            <PanelLeftClose className="size-3.5" />
          </button>
        </div>
      </div>

      {/* Search input */}
      <div className="px-3 py-2 border-b border-border/30 shrink-0">
        <div className="relative">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 size-3 text-muted-foreground/50 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={handleSearchChange}
            placeholder="Cari percakapan..."
            className="w-full bg-secondary/50 border border-border/40 rounded-lg pl-7 pr-7 py-1.5 text-[11px] text-secondary-foreground placeholder-muted-foreground/50 focus:outline-none focus:border-primary/30 focus:bg-secondary/80 transition-all"
          />
          {isSearching && (
            <button
              onClick={clearSearch}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/40 hover:text-secondary-foreground transition-colors"
            >
              <X className="size-3" />
            </button>
          )}
        </div>
      </div>

      {/* Session list */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-10 gap-2">
            <Loader2 className="size-4 animate-spin text-muted-foreground" />
            <span className="text-[11px] text-muted-foreground">Memuat riwayat...</span>
          </div>
        ) : showEmptyState ? (
          <div className="flex flex-col items-center justify-center px-6 py-10">
            <div className="w-8 h-8 rounded-xl bg-secondary/50 border border-border/50 flex items-center justify-center mb-3">
              <MessageSquare className="size-4 text-muted-foreground/60" />
            </div>
            <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
              Belum ada riwayat chat.
            </p>
            <p className="text-[10px] text-muted-foreground/50 text-center mt-1">
              Mulai percakapan baru untuk menyimpannya di sini.
            </p>
          </div>
        ) : showSearchEmpty ? (
          <div className="flex flex-col items-center justify-center px-6 py-10">
            <div className="w-8 h-8 rounded-xl bg-secondary/50 border border-border/50 flex items-center justify-center mb-3">
              <Search className="size-4 text-muted-foreground/60" />
            </div>
            <p className="text-[11px] text-muted-foreground text-center leading-relaxed">
              Tidak ditemukan untuk "{searchQuery}"
            </p>
            <p className="text-[10px] text-muted-foreground/50 text-center mt-1">
              Coba kata kunci lain
            </p>
          </div>
        ) : (
          <>
            {filteredSessions.map((session) => (
              <button
                key={session.id}
                onClick={() => { onSelect(session.id); setSearchQuery(""); }}
                className={cn(
                  "w-full text-left px-3 py-3 hover:bg-muted/40 transition-all group flex items-start gap-2.5 border-b border-border/30",
                  activeSessionId === session.id && "bg-muted/30 border-l-[2.5px] border-l-primary shadow-sm"
                )}
              >
                <div className={cn(
                  "w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5 transition-colors",
                  activeSessionId === session.id
                    ? "bg-primary/10 text-primary"
                    : "bg-secondary/50 text-muted-foreground group-hover:text-secondary-foreground"
                )}>
                  <MessageSquare className="size-3" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className={cn(
                    "text-xs truncate leading-snug",
                    activeSessionId === session.id ? "text-foreground font-medium" : "text-secondary-foreground"
                  )}>
                    {highlightMatch(session.title || "Tanpa judul", searchQuery)}
                  </p>
                  {session.updatedAt && (
                    <p className="text-[10px] text-muted-foreground/60 mt-1 tabular-nums">
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
                  className="p-1.5 rounded-lg opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-all shrink-0 self-start mt-0.5"
                  title="Hapus sesi"
                >
                  <Trash2 className="size-3" />
                </button>
              </button>
            ))}

            {/* Load More button — only show when not searching */}
            {hasMore && !isSearching && (
              <div className="px-3 py-3">
                {loadingMore ? (
                  <div className="flex items-center justify-center py-2">
                    <Loader2 className="size-3.5 animate-spin text-muted-foreground mr-2" />
                    <span className="text-[11px] text-muted-foreground">Memuat...</span>
                  </div>
                ) : (
                  <button
                    onClick={handleLoadMore}
                    className="w-full text-center text-[11px] font-medium text-primary/70 hover:text-primary py-2 rounded-lg hover:bg-muted/40 transition-all"
                  >
                    Muat Lebih Banyak
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>

      {/* New chat button at bottom */}
      <div className="px-3 py-2.5 border-t border-border/50">
        <button
          onClick={onNewSession}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl bg-primary/5 hover:bg-primary/10 border border-primary/10 hover:border-primary/25 text-primary text-xs font-medium transition-all"
        >
          <Plus className="size-3.5" />
          Percakapan Baru
        </button>
      </div>
    </div>
  );
}

/** Highlight matching text in session titles */
function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  if (parts.length === 1) return text;
  return (
    <>
      {parts.map((part, i) =>
        part.toLowerCase() === query.toLowerCase() ? (
          <mark key={i} className="bg-primary/20 text-foreground rounded-sm px-0.5">{part}</mark>
        ) : (
          part
        )
      )}
    </>
  );
}
