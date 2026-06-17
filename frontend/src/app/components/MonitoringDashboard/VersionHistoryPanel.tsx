"use client";

import React, { useState, useEffect, useCallback } from "react";
import { X, GitCompare, RotateCcw, ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "../ui/button";
import { Checkbox } from "../ui/checkbox";
import { Badge } from "../ui/badge";
import { useMonitoringData, useVersionDiff } from "./hooks";
import type { FileVersion } from "./hooks";
import DiffViewer from "./DiffViewer";
import RestoreDialog from "./RestoreDialog";
import axios from "axios";

interface VersionHistoryPanelProps {
  fileId: number;
  fileName: string;
  currentVersion: number | null;
  onClose: () => void;
}

export default function VersionHistoryPanel({
  fileId,
  fileName,
  currentVersion,
  onClose,
}: VersionHistoryPanelProps) {
  const { versions, versionsTotalCount, versionsPage, versionsLoading, versionsError, loadVersions } =
    useMonitoringData();
  const { diff, loading: diffLoading, error: diffError, loadDiff, clearDiff } = useVersionDiff();

  const [selectedVersions, setSelectedVersions] = useState<Set<number>>(new Set());
  const [showDiff, setShowDiff] = useState(false);
  const [restoreVersion, setRestoreVersion] = useState<number | null>(null);
  const [restoreLoading, setRestoreLoading] = useState(false);

  const PAGE_SIZE = 50;
  const totalPages = Math.ceil(versionsTotalCount / PAGE_SIZE);

  useEffect(() => {
    loadVersions(fileId, 1);
  }, [fileId, loadVersions]);

  const handleCheckboxChange = useCallback((versionNumber: number, checked: boolean) => {
    setSelectedVersions((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(versionNumber);
      } else {
        next.delete(versionNumber);
      }
      return next;
    });
  }, []);

  const handleCompare = useCallback(async () => {
    if (selectedVersions.size !== 2) return;
    const [versionA, versionB] = Array.from(selectedVersions).sort((a, b) => a - b);
    await loadDiff(fileId, versionA, versionB);
    setShowDiff(true);
  }, [selectedVersions, fileId, loadDiff]);

  const handleRestore = useCallback(async () => {
    if (restoreVersion === null) return;
    setRestoreLoading(true);
    try {
      await axios.post(
        `/api/monitoring/files/${fileId}/versions/${restoreVersion}/restore`,
        { confirmed: true }
      );
      // Reload versions after restore
      await loadVersions(fileId, versionsPage);
    } finally {
      setRestoreLoading(false);
      setRestoreVersion(null);
    }
  }, [restoreVersion, fileId, loadVersions, versionsPage]);

  const handlePageChange = useCallback(
    (page: number) => {
      loadVersions(fileId, page);
      setSelectedVersions(new Set());
    },
    [fileId, loadVersions]
  );

  if (showDiff && diff) {
    return <DiffViewer diff={diff} onClose={() => { setShowDiff(false); clearDiff(); }} />;
  }

  return (
    <div className="flex flex-col h-full border rounded-lg bg-background">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Version History</h3>
          <Badge variant="secondary" className="text-xs">
            {fileName}
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={selectedVersions.size !== 2 || diffLoading}
            onClick={handleCompare}
          >
            <GitCompare className="size-4" />
            {diffLoading ? "Comparing..." : "Compare"}
          </Button>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="size-4" />
          </Button>
        </div>
      </div>

      {/* Error state */}
      {versionsError && (
        <div className="px-4 py-3 text-sm text-destructive">{versionsError}</div>
      )}

      {/* Diff error */}
      {diffError && (
        <div className="px-4 py-2 text-sm text-destructive">{diffError}</div>
      )}

      {/* Version list */}
      <div className="flex-1 overflow-auto">
        {versionsLoading ? (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            Loading versions...
          </div>
        ) : versions.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            No versions found.
          </div>
        ) : (
          <div className="divide-y">
            {versions.map((version: FileVersion) => (
              <div
                key={version.version_number}
                className="flex items-center gap-3 px-4 py-2.5 hover:bg-muted/50"
              >
                <Checkbox
                  checked={selectedVersions.has(version.version_number)}
                  onCheckedChange={(checked) =>
                    handleCheckboxChange(version.version_number, checked === true)
                  }
                  aria-label={`Select version ${version.version_number} for comparison`}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      v{version.version_number}
                    </span>
                    {version.version_number === currentVersion && (
                      <Badge variant="default" className="text-xs">
                        Current
                      </Badge>
                    )}
                    {version.is_restore && (
                      <Badge variant="secondary" className="text-xs">
                        Restored from v{version.restored_from_version}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                    <span>{new Date(version.timestamp).toLocaleString()}</span>
                    <span className="font-mono">{version.content_hash.slice(0, 8)}</span>
                    <span>{formatFileSize(version.file_size)}</span>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setRestoreVersion(version.version_number)}
                  disabled={version.version_number === currentVersion}
                  aria-label={`Restore version ${version.version_number}`}
                >
                  <RotateCcw className="size-3.5" />
                  Restore
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t px-4 py-2">
          <span className="text-xs text-muted-foreground">
            Page {versionsPage} of {totalPages} ({versionsTotalCount} versions)
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              disabled={versionsPage <= 1}
              onClick={() => handlePageChange(versionsPage - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft className="size-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              disabled={versionsPage >= totalPages}
              onClick={() => handlePageChange(versionsPage + 1)}
              aria-label="Next page"
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Restore Dialog */}
      <RestoreDialog
        open={restoreVersion !== null}
        fileName={fileName}
        versionToRestore={restoreVersion ?? 0}
        currentVersion={currentVersion}
        onConfirm={handleRestore}
        onCancel={() => setRestoreVersion(null)}
        loading={restoreLoading}
      />
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}
