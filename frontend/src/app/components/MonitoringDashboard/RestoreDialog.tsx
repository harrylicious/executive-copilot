"use client";

import React from "react";
import { RotateCcw } from "lucide-react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "../ui/alert-dialog";

interface RestoreDialogProps {
  open: boolean;
  fileName: string;
  versionToRestore: number;
  currentVersion: number | null;
  onConfirm: () => void;
  onCancel: () => void;
  loading?: boolean;
}

export default function RestoreDialog({
  open,
  fileName,
  versionToRestore,
  currentVersion,
  onConfirm,
  onCancel,
  loading = false,
}: RestoreDialogProps) {
  return (
    <AlertDialog open={open} onOpenChange={(isOpen) => { if (!isOpen) onCancel(); }}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle className="flex items-center gap-2">
            <RotateCcw className="size-5" />
            Restore Version
          </AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>
                Are you sure you want to restore this file to a previous version? This will
                overwrite the current file content and trigger re-embedding.
              </p>
              <div className="rounded-md border bg-muted/50 p-3 space-y-1.5">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">File</span>
                  <span className="font-medium">{fileName}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Restore to version</span>
                  <span className="font-medium">v{versionToRestore}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">Current version</span>
                  <span className="font-medium">
                    {currentVersion !== null ? `v${currentVersion}` : "—"}
                  </span>
                </div>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={loading} onClick={onCancel}>
            Cancel
          </AlertDialogCancel>
          <AlertDialogAction disabled={loading} onClick={onConfirm}>
            {loading ? "Restoring..." : "Confirm Restore"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
