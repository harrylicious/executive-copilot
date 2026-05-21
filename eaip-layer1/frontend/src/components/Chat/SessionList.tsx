import { useEffect, useState } from "react";
import { getSessions, deleteSession } from "@/api/client";
import type { ChatSessionSummary } from "@/types";
import { MessageSquare, Trash2 } from "lucide-react";

interface SessionListProps {
  onSelect: (sessionId: string) => void;
  refreshKey?: number;
}

export function SessionList({ onSelect, refreshKey }: SessionListProps) {
  const [sessions, setSessions] = useState<ChatSessionSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getSessions()
      .then((data) => {
        if (!cancelled) setSessions(data);
      })
      .catch(() => {
        if (!cancelled) setSessions([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  const handleDelete = async (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.id !== sessionId));
    } catch {
      // Silently fail
    }
  };

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-xs text-muted-foreground">Loading...</span>
      </div>
    );
  }

  if (sessions.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center px-3">
        <p className="text-xs text-muted-foreground text-center">
          No saved sessions yet. Start a conversation and it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      {sessions.map((session) => (
        <button
          key={session.id}
          onClick={() => onSelect(session.id)}
          className="w-full text-left px-3 py-2 hover:bg-muted/50 border-b border-border/50 group flex items-start gap-2"
        >
          <MessageSquare className="size-3.5 mt-0.5 text-muted-foreground shrink-0" />
          <div className="flex-1 min-w-0">
            <p className="text-xs font-medium truncate">
              {session.title || "Untitled session"}
            </p>
            {session.updatedAt && (
              <p className="text-[10px] text-muted-foreground mt-0.5">
                {new Date(session.updatedAt).toLocaleDateString()}
              </p>
            )}
          </div>
          <button
            onClick={(e) => handleDelete(e, session.id)}
            className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-destructive/10 hover:text-destructive transition-opacity"
            title="Delete session"
          >
            <Trash2 className="size-3" />
          </button>
        </button>
      ))}
    </div>
  );
}
