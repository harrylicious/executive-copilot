import { useEffect } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { useWebSocket, useMonitoringData } from "./hooks";
import { ConnectionIndicator } from "./ConnectionIndicator";
import { EmbeddingProgressBar } from "./EmbeddingProgressBar";
import { FileStatusTable } from "./FileStatusTable";
import type { FileStatus } from "./hooks";

export default function MonitoringDashboard() {
  const { messages, connectionState } = useWebSocket();
  const {
    files,
    filesTotalCount,
    filesPage,
    filesLoading,
    filesError,
    loadFiles,
    embeddingStatus,
    embeddingStatusLoading,
    embeddingStatusError,
    loadEmbeddingStatus,
  } = useMonitoringData(messages);

  // Load initial data on mount
  useEffect(() => {
    loadFiles();
    loadEmbeddingStatus();
  }, [loadFiles, loadEmbeddingStatus]);

  const handlePageChange = (page: number) => {
    loadFiles(page);
  };

  const handleFileSelect = (_file: FileStatus) => {
    // Will be handled in task 15.2 (version history panel)
  };

  const handleRetry = () => {
    loadFiles(filesPage);
    loadEmbeddingStatus();
  };

  // Error state
  const hasError = filesError || embeddingStatusError;
  const isInitialLoading = filesLoading && (files ?? []).length === 0;

  if (hasError && (files ?? []).length === 0) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-foreground text-lg">Embedding Monitor</h1>
            <p className="text-muted-foreground text-sm">Real-time file processing status</p>
          </div>
          <ConnectionIndicator connectionState={connectionState} />
        </div>

        <div className="flex flex-col items-center justify-center py-12 text-center">
          <AlertCircle size={40} className="text-destructive mb-4" />
          <h2 className="text-foreground text-lg mb-1">Failed to load data</h2>
          <p className="text-muted-foreground text-sm mb-4">
            {filesError || embeddingStatusError}
          </p>
          <button
            onClick={handleRetry}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm hover:opacity-90 transition-opacity"
          >
            <RefreshCw size={14} />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6">
      {/* Header with connection indicator */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-foreground text-lg">Embedding Monitor</h1>
          <p className="text-muted-foreground text-sm">Real-time file processing status</p>
        </div>
        <ConnectionIndicator connectionState={connectionState} />
      </div>

      {/* Embedding progress summary */}
      <div className="mb-6">
        <EmbeddingProgressBar
          status={embeddingStatus}
          loading={embeddingStatusLoading && !embeddingStatus}
        />
      </div>

      {/* Main content grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* File status table - main content */}
        <div className="lg:col-span-2">
          <FileStatusTable
            files={files}
            totalCount={filesTotalCount}
            page={filesPage}
            loading={isInitialLoading}
            onPageChange={handlePageChange}
            onFileSelect={handleFileSelect}
          />
        </div>

        {/* Right sidebar */}
        <div className="space-y-6">
          {/* Version history panel placeholder (task 15.2) */}
          <div className="bg-card border border-border rounded-xl p-4">
            <h3 className="text-foreground text-sm mb-2">Version History</h3>
            <p className="text-muted-foreground text-xs">
              Select a file to view its version history.
            </p>
          </div>

          {/* Activity feed placeholder (task 15.3) */}
          <div className="bg-card border border-border rounded-xl p-4">
            <h3 className="text-foreground text-sm mb-2">Activity Feed</h3>
            <p className="text-muted-foreground text-xs">
              Real-time system events will appear here.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
