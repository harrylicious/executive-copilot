import { type FC, type ReactNode, useState, useCallback, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  FolderOpen,
  Network,
  MessageSquare,
  Search,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  Zap,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  triggerSync,
  getIndexStatus,
  getSyncLogs,
  runIncrementalEmbedding,
  getEmbeddingStatus,
  getEmbeddingLogs,
} from "@/api/client";
import type { IndexStatus, EmbeddingStatus, SyncLog, EmbeddingLog } from "@/types";

const NAV_ITEMS = [
  { label: "Explorer", path: "/", icon: FolderOpen },
  { label: "Graph", path: "/graph", icon: Network },
  { label: "Playground", path: "/playground", icon: MessageSquare },
  { label: "Search", path: "/search", icon: Search },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  children?: ReactNode;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const isSuccess = status === "success" || status === "completed";
  const isError = status === "error" || status === "failed";
  const isPending = status === "pending" || status === "running";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
        isSuccess && "bg-green-500/10 text-green-600 dark:text-green-400",
        isError && "bg-red-500/10 text-red-600 dark:text-red-400",
        isPending && "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
      )}
    >
      {isSuccess && <CheckCircle2 className="size-3" />}
      {isError && <XCircle className="size-3" />}
      {isPending && <Clock className="size-3" />}
      {status}
    </span>
  );
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts);
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

// ─── Sidebar ─────────────────────────────────────────────────────────────────

export const Sidebar: FC<SidebarProps> = ({ collapsed, onToggle, children }) => {
  const location = useLocation();

  // Sync state
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState<IndexStatus | null>(null);
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncLogs, setSyncLogs] = useState<SyncLog[]>([]);
  const [syncLogsLoading, setSyncLogsLoading] = useState(false);

  // Embedding state
  const [isEmbedding, setIsEmbedding] = useState(false);
  const [embeddingStatus, setEmbeddingStatus] = useState<EmbeddingStatus | null>(null);
  const [embedModalOpen, setEmbedModalOpen] = useState(false);
  const [embeddingLogs, setEmbeddingLogs] = useState<EmbeddingLog[]>([]);
  const [embedLogsLoading, setEmbedLogsLoading] = useState(false);

  const isActive = (path: string) => {
    if (path === "/") return location.pathname === "/";
    return location.pathname.startsWith(path);
  };

  // Fetch sync logs when modal opens
  const fetchSyncLogs = useCallback(async () => {
    setSyncLogsLoading(true);
    try {
      const [logs, status] = await Promise.all([getSyncLogs(), getIndexStatus()]);
      setSyncLogs(logs);
      setSyncStatus(status);
    } catch {
      // silent
    } finally {
      setSyncLogsLoading(false);
    }
  }, []);

  // Fetch embedding logs when modal opens
  const fetchEmbeddingLogs = useCallback(async () => {
    setEmbedLogsLoading(true);
    try {
      const [logs, status] = await Promise.all([getEmbeddingLogs(), getEmbeddingStatus()]);
      setEmbeddingLogs(logs);
      setEmbeddingStatus(status);
    } catch {
      // silent
    } finally {
      setEmbedLogsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (syncModalOpen) fetchSyncLogs();
  }, [syncModalOpen, fetchSyncLogs]);

  useEffect(() => {
    if (embedModalOpen) fetchEmbeddingLogs();
  }, [embedModalOpen, fetchEmbeddingLogs]);

  const handleSync = useCallback(async () => {
    setIsSyncing(true);
    try {
      await triggerSync();
      const status = await getIndexStatus();
      setSyncStatus(status);
      // Refresh logs after sync
      const logs = await getSyncLogs();
      setSyncLogs(logs);
    } catch {
      // silent
    } finally {
      setIsSyncing(false);
    }
  }, []);

  const handleEmbed = useCallback(async () => {
    setIsEmbedding(true);
    try {
      await runIncrementalEmbedding();
      const status = await getEmbeddingStatus();
      setEmbeddingStatus(status);
      // Refresh logs after embed
      const logs = await getEmbeddingLogs();
      setEmbeddingLogs(logs);
    } catch {
      // silent
    } finally {
      setIsEmbedding(false);
    }
  }, []);

  return (
    <>
      <aside
        className={cn(
          "flex flex-col h-full border-r border-border bg-card transition-all duration-200 shrink-0 overflow-hidden",
          collapsed ? "w-12" : "w-60"
        )}
      >
        {/* Header: Brand + Toggle */}
        <div
          className={cn(
            "flex items-center h-11 border-b border-border shrink-0",
            collapsed ? "justify-center px-0" : "px-3 gap-2"
          )}
        >
          {!collapsed && (
            <span className="text-xs font-bold text-primary truncate tracking-wide">
              JB Executive Copilot
            </span>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggle}
            className={cn(!collapsed && "ml-auto")}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? (
              <PanelLeftOpen className="size-4" />
            ) : (
              <PanelLeftClose className="size-4" />
            )}
          </Button>
        </div>

        {/* Navigation */}
        <nav className="py-1.5 space-y-0.5 px-1.5 shrink-0">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.path);
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "flex items-center gap-2.5 rounded-md text-sm font-medium transition-colors",
                  collapsed ? "justify-center h-8 w-8 mx-auto" : "px-2.5 h-7",
                  active
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                )}
                title={collapsed ? item.label : undefined}
              >
                <Icon className="size-3.5 shrink-0" />
                {!collapsed && <span className="truncate text-xs">{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Sync & Embed actions — now open modals */}
        <div className={cn("px-1.5 py-1.5 border-t border-border shrink-0 space-y-1")}>
          {/* Sync */}
          <button
            onClick={() => setSyncModalOpen(true)}
            title={collapsed ? "Sync Files" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md text-xs font-medium transition-colors w-full",
              collapsed ? "justify-center h-8 w-8 mx-auto" : "px-2.5 h-7",
              "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            <RefreshCw className={cn("size-3.5 shrink-0", isSyncing && "animate-spin")} />
            {!collapsed && (
              <span className="truncate">Sync</span>
            )}
            {!collapsed && syncStatus && (
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {syncStatus.totalFiles}
              </span>
            )}
          </button>

          {/* Embed */}
          <button
            onClick={() => setEmbedModalOpen(true)}
            title={collapsed ? "Run Embedding" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md text-xs font-medium transition-colors w-full",
              collapsed ? "justify-center h-8 w-8 mx-auto" : "px-2.5 h-7",
              "text-muted-foreground hover:text-foreground hover:bg-muted"
            )}
          >
            <Zap className={cn("size-3.5 shrink-0", isEmbedding && "animate-pulse")} />
            {!collapsed && (
              <span className="truncate">Embed</span>
            )}
            {!collapsed && embeddingStatus && (
              <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">
                {embeddingStatus.totalFilesEmbedded}
                {embeddingStatus.filesPending > 0 && (
                  <span className="text-yellow-500 ml-0.5">+{embeddingStatus.filesPending}</span>
                )}
              </span>
            )}
          </button>
        </div>

        {/* Page-specific content (e.g. file explorer) */}
        {!collapsed && children && (
          <div className="flex-1 overflow-hidden border-t border-border">
            {children}
          </div>
        )}

        {/* Spacer when no children */}
        {(!children || collapsed) && <div className="flex-1" />}

        {/* Bottom: Theme toggle */}
        <div
          className={cn(
            "border-t border-border py-1.5 shrink-0",
            collapsed ? "flex justify-center" : "px-2"
          )}
        >
          <ThemeToggle />
        </div>
      </aside>

      {/* ─── Sync Modal ─────────────────────────────────────────────────────── */}
      <Dialog open={syncModalOpen} onOpenChange={setSyncModalOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <RefreshCw className="size-4" />
              Sync Logs
            </DialogTitle>
            <DialogDescription>
              File synchronization history.
              {syncStatus && (
                <span className="ml-2 text-foreground">
                  {syncStatus.totalFiles} files indexed
                  {syncStatus.pendingCount ? `, ${syncStatus.pendingCount} pending` : ""}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>

          {/* Action button */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleSync}
              disabled={isSyncing}
            >
              {isSyncing ? (
                <Loader2 className="size-3.5 animate-spin mr-1.5" />
              ) : (
                <RefreshCw className="size-3.5 mr-1.5" />
              )}
              {isSyncing ? "Syncing..." : "Run Sync"}
            </Button>
          </div>

          {/* Log list */}
          <div className="flex-1 overflow-auto border rounded-md">
            {syncLogsLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin mr-2" />
                Loading...
              </div>
            ) : syncLogs.length === 0 ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
                No sync logs yet.
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-card border-b border-border">
                  <tr className="text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Timestamp</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium text-right">Added</th>
                    <th className="px-3 py-2 font-medium text-right">Updated</th>
                    <th className="px-3 py-2 font-medium text-right">Removed</th>
                    <th className="px-3 py-2 font-medium">Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {syncLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/50 transition-colors">
                      <td className="px-3 py-2 tabular-nums whitespace-nowrap">
                        {formatTimestamp(log.timestamp)}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={log.status} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-green-600 dark:text-green-400">
                        {log.filesAdded > 0 ? `+${log.filesAdded}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-blue-600 dark:text-blue-400">
                        {log.filesUpdated > 0 ? log.filesUpdated : "—"}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums text-red-600 dark:text-red-400">
                        {log.filesRemoved > 0 ? `-${log.filesRemoved}` : "—"}
                      </td>
                      <td className="px-3 py-2 text-muted-foreground truncate max-w-[200px]">
                        {log.summary || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* ─── Embedding Modal ────────────────────────────────────────────────── */}
      <Dialog open={embedModalOpen} onOpenChange={setEmbedModalOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Zap className="size-4" />
              Embedding Logs
            </DialogTitle>
            <DialogDescription>
              Embedding job history.
              {embeddingStatus && (
                <span className="ml-2 text-foreground">
                  {embeddingStatus.totalFilesEmbedded} embedded
                  {embeddingStatus.filesPending > 0 && `, ${embeddingStatus.filesPending} pending`}
                </span>
              )}
            </DialogDescription>
          </DialogHeader>

          {/* Action button */}
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              onClick={handleEmbed}
              disabled={isEmbedding}
            >
              {isEmbedding ? (
                <Loader2 className="size-3.5 animate-spin mr-1.5" />
              ) : (
                <Zap className="size-3.5 mr-1.5" />
              )}
              {isEmbedding ? "Embedding..." : "Run Embedding"}
            </Button>
          </div>

          {/* Log list */}
          <div className="flex-1 overflow-auto border rounded-md">
            {embedLogsLoading ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
                <Loader2 className="size-4 animate-spin mr-2" />
                Loading...
              </div>
            ) : embeddingLogs.length === 0 ? (
              <div className="flex items-center justify-center py-8 text-muted-foreground text-sm">
                No embedding logs yet.
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead className="sticky top-0 bg-card border-b border-border">
                  <tr className="text-left text-muted-foreground">
                    <th className="px-3 py-2 font-medium">Timestamp</th>
                    <th className="px-3 py-2 font-medium">Status</th>
                    <th className="px-3 py-2 font-medium text-right">Files</th>
                    <th className="px-3 py-2 font-medium text-right">Chunks</th>
                    <th className="px-3 py-2 font-medium text-right">Errors</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {embeddingLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/50 transition-colors">
                      <td className="px-3 py-2 tabular-nums whitespace-nowrap">
                        {formatTimestamp(log.timestamp)}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge status={log.status} />
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.filesProcessed}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.chunksGenerated}
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">
                        {log.errorsCount > 0 ? (
                          <span className="text-red-600 dark:text-red-400">
                            {log.errorsCount}
                          </span>
                        ) : (
                          "—"
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
};

export default Sidebar;
