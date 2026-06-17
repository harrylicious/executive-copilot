import {
  FilePlus,
  FileEdit,
  Trash2,
  Zap,
  CheckCircle,
  XCircle,
  GitBranch,
  RotateCcw,
  AlertTriangle,
  RefreshCw,
  Activity,
} from "lucide-react";
import type { ActivityEvent } from "./hooks/useMonitoringData";

// ─── Types ───────────────────────────────────────────────────────────────────

interface ActivityFeedProps {
  events: ActivityEvent[];
  onRetry?: (fileId: number) => void;
  loading?: boolean;
}

// ─── Event Config ────────────────────────────────────────────────────────────

interface EventConfig {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  color: string;
  bgColor: string;
  label: string;
}

const EVENT_CONFIG: Record<string, EventConfig> = {
  file_created: {
    icon: FilePlus,
    color: "text-green-500",
    bgColor: "bg-green-500/10",
    label: "File Created",
  },
  file_modified: {
    icon: FileEdit,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
    label: "File Modified",
  },
  file_deleted: {
    icon: Trash2,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    label: "File Deleted",
  },
  embedding_started: {
    icon: Zap,
    color: "text-blue-500",
    bgColor: "bg-blue-500/10",
    label: "Embedding Started",
  },
  embedding_completed: {
    icon: CheckCircle,
    color: "text-green-500",
    bgColor: "bg-green-500/10",
    label: "Embedding Completed",
  },
  embedding_failed: {
    icon: XCircle,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    label: "Embedding Failed",
  },
  version_created: {
    icon: GitBranch,
    color: "text-purple-500",
    bgColor: "bg-purple-500/10",
    label: "Version Created",
  },
  version_restored: {
    icon: RotateCcw,
    color: "text-orange-500",
    bgColor: "bg-orange-500/10",
    label: "Version Restored",
  },
  system_error: {
    icon: AlertTriangle,
    color: "text-red-500",
    bgColor: "bg-red-500/10",
    label: "System Error",
  },
};

const DEFAULT_EVENT_CONFIG: EventConfig = {
  icon: Activity,
  color: "text-muted-foreground",
  bgColor: "bg-secondary",
  label: "Event",
};

// ─── Helpers ─────────────────────────────────────────────────────────────────

function formatTimestamp(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSeconds = Math.floor(diffMs / 1000);
  const diffMinutes = Math.floor(diffSeconds / 60);
  const diffHours = Math.floor(diffMinutes / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSeconds < 60) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function getFileIdFromDetails(
  details: Record<string, unknown> | null
): number | null {
  if (!details) return null;
  const fileId = details.file_id;
  if (typeof fileId === "number") return fileId;
  if (typeof fileId === "string") {
    const parsed = parseInt(fileId, 10);
    return isNaN(parsed) ? null : parsed;
  }
  return null;
}

// ─── Skeleton ────────────────────────────────────────────────────────────────

function ActivityItemSkeleton() {
  return (
    <div className="flex items-center gap-3 py-3 animate-pulse">
      <div className="w-8 h-8 rounded-lg bg-secondary shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="h-3.5 w-32 bg-secondary rounded mb-1.5" />
        <div className="h-3 w-24 bg-secondary rounded" />
      </div>
      <div className="h-3 w-14 bg-secondary rounded shrink-0" />
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

export function ActivityFeed({ events, onRetry, loading }: ActivityFeedProps) {
  if (loading) {
    return (
      <div className="bg-card border border-border rounded-xl p-4">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={16} className="text-muted-foreground" />
          <h3 className="text-foreground text-sm font-medium">
            Activity Feed
          </h3>
        </div>
        <div className="space-y-1">
          {Array.from({ length: 6 }).map((_, i) => (
            <ActivityItemSkeleton key={i} />
          ))}
        </div>
      </div>
    );
  }

  const displayEvents = events.slice(0, 50);

  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <div className="flex items-center gap-2 mb-4">
        <Activity size={16} className="text-muted-foreground" />
        <h3 className="text-foreground text-sm font-medium">Activity Feed</h3>
        <span className="text-muted-foreground text-xs ml-auto">
          {displayEvents.length} event{displayEvents.length !== 1 ? "s" : ""}
        </span>
      </div>

      {displayEvents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-center">
          <Activity size={32} className="text-muted-foreground/50 mb-2" />
          <p className="text-muted-foreground text-sm">No recent activity</p>
        </div>
      ) : (
        <div className="max-h-[400px] overflow-y-auto space-y-0.5">
          {displayEvents.map((event) => {
            const config =
              EVENT_CONFIG[event.event_type] ?? DEFAULT_EVENT_CONFIG;
            const Icon = config.icon;
            const showRetry =
              event.event_type === "embedding_failed" && onRetry;
            const fileId = getFileIdFromDetails(event.details);

            return (
              <div
                key={event.id}
                className="flex items-center gap-3 py-2.5 border-b border-border last:border-0"
              >
                {/* Event icon */}
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${config.bgColor}`}
                >
                  <Icon size={14} className={config.color} />
                </div>

                {/* Event details */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs font-medium px-1.5 py-0.5 rounded ${config.bgColor} ${config.color}`}
                    >
                      {config.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    {event.file_name && (
                      <span className="text-secondary-foreground text-xs truncate max-w-[180px]">
                        {event.file_name}
                      </span>
                    )}
                    {event.file_name && event.actor && (
                      <span className="text-muted-foreground text-xs">·</span>
                    )}
                    {event.actor && (
                      <span className="text-muted-foreground text-xs">
                        {event.actor}
                      </span>
                    )}
                  </div>
                </div>

                {/* Retry button for failed embeddings */}
                {showRetry && fileId !== null && (
                  <button
                    onClick={() => onRetry(fileId)}
                    className="flex items-center gap-1 px-2 py-1 text-xs text-orange-500 bg-orange-500/10 hover:bg-orange-500/20 rounded transition-colors shrink-0"
                    title="Retry embedding"
                  >
                    <RefreshCw size={12} />
                    Retry
                  </button>
                )}

                {/* Timestamp */}
                <span className="text-muted-foreground text-[11px] shrink-0">
                  {formatTimestamp(event.timestamp)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
