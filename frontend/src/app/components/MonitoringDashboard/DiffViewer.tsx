"use client";

import React from "react";
import { X, Plus, Minus, Pencil } from "lucide-react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import type { DiffResult, DiffOperation } from "./hooks";

interface DiffViewerProps {
  diff: DiffResult;
  onClose: () => void;
}

export default function DiffViewer({ diff, onClose }: DiffViewerProps) {
  const { operations, summary } = diff;

  return (
    <div className="flex flex-col h-full border rounded-lg bg-background">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold">Diff View</h3>
          <div className="flex items-center gap-2">
            <Badge className="bg-green-100 text-green-800 border-green-200 dark:bg-green-900/30 dark:text-green-400 dark:border-green-800">
              <Plus className="size-3" />
              {summary.lines_added} added
            </Badge>
            <Badge className="bg-red-100 text-red-800 border-red-200 dark:bg-red-900/30 dark:text-red-400 dark:border-red-800">
              <Minus className="size-3" />
              {summary.lines_deleted} deleted
            </Badge>
            <Badge className="bg-yellow-100 text-yellow-800 border-yellow-200 dark:bg-yellow-900/30 dark:text-yellow-400 dark:border-yellow-800">
              <Pencil className="size-3" />
              {summary.lines_modified} modified
            </Badge>
          </div>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose}>
          <X className="size-4" />
        </Button>
      </div>

      {/* Diff content */}
      <div className="flex-1 overflow-auto font-mono text-xs">
        {operations.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-sm text-muted-foreground">
            No differences found. The versions are identical.
          </div>
        ) : (
          <div className="divide-y">
            {operations.map((op: DiffOperation, index: number) => (
              <DiffLine key={index} operation={op} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function DiffLine({ operation }: { operation: DiffOperation }) {
  switch (operation.operation) {
    case "addition":
      return (
        <div className="flex items-start gap-2 px-4 py-1.5 bg-green-50 dark:bg-green-950/20">
          <span className="text-muted-foreground w-8 text-right shrink-0 select-none">
            {operation.line_number}
          </span>
          <Plus className="size-3.5 text-green-600 dark:text-green-400 mt-0.5 shrink-0" />
          <span className="text-green-800 dark:text-green-300 whitespace-pre-wrap break-all">
            {operation.content}
          </span>
        </div>
      );

    case "deletion":
      return (
        <div className="flex items-start gap-2 px-4 py-1.5 bg-red-50 dark:bg-red-950/20">
          <span className="text-muted-foreground w-8 text-right shrink-0 select-none">
            {operation.line_number}
          </span>
          <Minus className="size-3.5 text-red-600 dark:text-red-400 mt-0.5 shrink-0" />
          <span className="text-red-800 dark:text-red-300 whitespace-pre-wrap break-all">
            {operation.content}
          </span>
        </div>
      );

    case "modification":
      return (
        <div className="bg-yellow-50 dark:bg-yellow-950/20">
          <div className="flex items-start gap-2 px-4 py-1 border-b border-yellow-100 dark:border-yellow-900/30">
            <span className="text-muted-foreground w-8 text-right shrink-0 select-none">
              {operation.line_number}
            </span>
            <Pencil className="size-3.5 text-yellow-600 dark:text-yellow-400 mt-0.5 shrink-0" />
            <div className="flex flex-col gap-0.5">
              {operation.old_content && (
                <span className="text-yellow-800 dark:text-yellow-300 line-through opacity-70 whitespace-pre-wrap break-all">
                  {operation.old_content}
                </span>
              )}
              <span className="text-yellow-900 dark:text-yellow-200 whitespace-pre-wrap break-all">
                {operation.content}
              </span>
            </div>
          </div>
        </div>
      );

    default:
      return null;
  }
}
