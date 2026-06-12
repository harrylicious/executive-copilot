import { useState } from "react";
import { X, FileText, Folder, Calendar, HardDrive, Tag, Sparkles, Check, Loader2, Pencil } from "lucide-react";
import type { FileNode } from "../../../types";
import { TagEditor } from "./TagEditor";
import { suggestTags, updateFileTags, suggestRename, renameFile } from "../../../api/kb";

interface MetadataSidebarProps {
  file: FileNode | null;
  onClose: () => void;
  onTagsChange?: (tags: string[]) => void;
  onRename?: (newName: string) => void;
}

function formatSize(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
}

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleDateString("id-ID", {
      year: "numeric", month: "short", day: "numeric",
    });
  } catch {
    return dateStr;
  }
}

export function MetadataSidebar({ file, onClose, onTagsChange, onRename }: MetadataSidebarProps) {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [suggestError, setSuggestError] = useState<string | null>(null);
  const [acceptingTag, setAcceptingTag] = useState<string | null>(null);

  // Rename state
  const [renameSuggestions, setRenameSuggestions] = useState<string[]>([]);
  const [loadingRename, setLoadingRename] = useState(false);
  const [renameError, setRenameError] = useState<string | null>(null);
  const [applyingRename, setApplyingRename] = useState<string | null>(null);
  const [displayName, setDisplayName] = useState<string | null>(null);

  if (!file) {
    return (
      <div className="w-72 border-l border-border bg-card p-4 flex flex-col items-center justify-center text-center">
        <FileText size={32} className="text-muted-foreground/30 mb-2" />
        <p className="text-xs text-muted-foreground">Select a file to view details</p>
      </div>
    );
  }

  const handleTagsChange = (tags: string[]) => {
    if (onTagsChange) onTagsChange(tags);
  };

  const handleSuggestTags = async () => {
    setLoadingSuggestions(true);
    setSuggestError(null);
    setSuggestions([]);
    try {
      const tags = await suggestTags(file.id);
      // Filter out tags already present on the file
      const newSuggestions = tags.filter(
        (t) => !file.tags.includes(t.toLowerCase())
      );
      setSuggestions(newSuggestions);
    } catch (err) {
      setSuggestError(
        err instanceof Error ? err.message : "Failed to get suggestions"
      );
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const handleAcceptTag = async (tag: string) => {
    setAcceptingTag(tag);
    try {
      const newTags = [...file.tags, tag.toLowerCase()];
      await updateFileTags(file.id, newTags);
      handleTagsChange(newTags);
      setSuggestions((prev) => prev.filter((t) => t !== tag));
    } catch {
      // silently fail on accept
    } finally {
      setAcceptingTag(null);
    }
  };

  const handleDismissTag = (tag: string) => {
    setSuggestions((prev) => prev.filter((t) => t !== tag));
  };

  const handleSuggestRename = async () => {
    setLoadingRename(true);
    setRenameError(null);
    setRenameSuggestions([]);
    try {
      const names = await suggestRename(file.id);
      setRenameSuggestions(names);
    } catch (err) {
      setRenameError(
        err instanceof Error ? err.message : "Failed to get rename suggestions"
      );
    } finally {
      setLoadingRename(false);
    }
  };

  const handleApplyRename = async (newName: string) => {
    setApplyingRename(newName);
    try {
      await renameFile(file.id, newName);
      setDisplayName(newName);
      setRenameSuggestions([]);
      if (onRename) onRename(newName);
    } catch (err) {
      setRenameError(
        err instanceof Error ? err.message : "Failed to rename file"
      );
    } finally {
      setApplyingRename(null);
    }
  };

  const handleDismissRename = (name: string) => {
    setRenameSuggestions((prev) => prev.filter((n) => n !== name));
  };

  return (
    <div className="w-72 border-l border-border bg-card flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-border">
        <span className="text-xs font-medium text-foreground">Details</span>
        <button
          onClick={onClose}
          className="text-muted-foreground hover:text-secondary-foreground p-0.5 rounded"
        >
          <X size={14} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* File name */}
        <div>
          <div className="flex items-center gap-2 mb-1">
            <FileText size={14} className="text-primary" />
            <span className="text-sm font-medium text-foreground break-all">{displayName || file.name}</span>
            <button
              onClick={handleSuggestRename}
              disabled={loadingRename}
              className="ml-auto inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 transition-colors shrink-0"
              title="Suggest rename using AI"
            >
              {loadingRename ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <Pencil size={10} />
              )}
              Rename
            </button>
          </div>

          {/* Rename suggestions */}
          {renameSuggestions.length > 0 && (
            <div className="mt-2 space-y-1">
              {renameSuggestions.map((name) => (
                <div
                  key={name}
                  className="flex items-center gap-1 bg-primary/5 border border-primary/20 rounded-md px-2 py-1 text-xs text-primary"
                >
                  <span className="flex-1 break-all">{name}</span>
                  <button
                    onClick={() => handleApplyRename(name)}
                    disabled={applyingRename === name}
                    className="text-primary hover:text-primary/80 transition-colors p-0.5 shrink-0"
                    title="Apply this name"
                  >
                    {applyingRename === name ? (
                      <Loader2 size={10} className="animate-spin" />
                    ) : (
                      <Check size={10} />
                    )}
                  </button>
                  <button
                    onClick={() => handleDismissRename(name)}
                    disabled={applyingRename === name}
                    className="text-muted-foreground hover:text-destructive transition-colors p-0.5 shrink-0"
                    title="Dismiss suggestion"
                  >
                    <X size={10} />
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Rename error */}
          {renameError && (
            <p className="text-[10px] text-destructive mt-1">{renameError}</p>
          )}
        </div>

        {/* Metadata rows */}
        <div className="space-y-2.5">
          <div className="flex items-start gap-2.5">
            <Folder size={13} className="text-muted-foreground shrink-0 mt-0.5" />
            <div className="min-w-0">
              <span className="text-[10px] text-muted-foreground block">Path</span>
              <span className="text-xs text-secondary-foreground break-all">{file.path}</span>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Folder size={13} className="text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] text-muted-foreground block">Department</span>
              <span className="text-xs text-secondary-foreground">{file.department}</span>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <HardDrive size={13} className="text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] text-muted-foreground block">Size</span>
              <span className="text-xs text-secondary-foreground">{formatSize(file.size)}</span>
            </div>
          </div>

          {file.fileType && (
            <div className="flex items-start gap-2.5">
              <FileText size={13} className="text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <span className="text-[10px] text-muted-foreground block">Type</span>
                <span className="text-xs text-secondary-foreground uppercase">{file.fileType}</span>
              </div>
            </div>
          )}

          <div className="flex items-start gap-2.5">
            <Calendar size={13} className="text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] text-muted-foreground block">Created</span>
              <span className="text-xs text-secondary-foreground">{formatDate(file.createdAt)}</span>
            </div>
          </div>

          <div className="flex items-start gap-2.5">
            <Calendar size={13} className="text-muted-foreground shrink-0 mt-0.5" />
            <div>
              <span className="text-[10px] text-muted-foreground block">Modified</span>
              <span className="text-xs text-secondary-foreground">{formatDate(file.modifiedAt)}</span>
            </div>
          </div>

          {file.syncStatus && (
            <div className="flex items-start gap-2.5">
              <div className="w-3 h-3 rounded-full border-2 shrink-0 mt-0.5"
                style={{
                  borderColor: file.syncStatus === "synced" ? "#10b981" :
                    file.syncStatus === "pending" ? "#f59e0b" : "#8b949e",
                  backgroundColor: file.syncStatus === "synced" ? "#10b981" : "transparent",
                }}
              />
              <div>
                <span className="text-[10px] text-muted-foreground block">Sync Status</span>
                <span className="text-xs text-secondary-foreground capitalize">{file.syncStatus}</span>
              </div>
            </div>
          )}

          {file.sensitivityLevel && (
            <div className="flex items-start gap-2.5">
              <Tag size={13} className="text-muted-foreground shrink-0 mt-0.5" />
              <div>
                <span className="text-[10px] text-muted-foreground block">Sensitivity</span>
                <span className={[
                  "text-xs px-1.5 py-0.5 rounded-full",
                  file.sensitivityLevel === "high" ? "bg-red-500/10 text-red-500" :
                  file.sensitivityLevel === "medium" ? "bg-amber-500/10 text-amber-500" :
                  "bg-emerald-500/10 text-emerald-500",
                ].join(" ")}>
                  {file.sensitivityLevel}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Tags */}
        <div className="pt-3 border-t border-border">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Tag size={12} className="text-muted-foreground" />
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Tags</span>
            </div>
            <button
              onClick={handleSuggestTags}
              disabled={loadingSuggestions}
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-medium bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-50 transition-colors"
              title="Suggest tags using AI"
            >
              {loadingSuggestions ? (
                <Loader2 size={10} className="animate-spin" />
              ) : (
                <Sparkles size={10} />
              )}
              Suggest Tags
            </button>
          </div>

          {/* Suggestion chips */}
          {suggestions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-2">
              {suggestions.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-0.5 bg-primary/5 border border-primary/20 rounded-md px-1.5 py-0.5 text-xs text-primary"
                >
                  {tag}
                  <button
                    onClick={() => handleAcceptTag(tag)}
                    disabled={acceptingTag === tag}
                    className="text-primary hover:text-primary/80 transition-colors p-0.5"
                    title="Accept tag"
                  >
                    {acceptingTag === tag ? (
                      <Loader2 size={10} className="animate-spin" />
                    ) : (
                      <Check size={10} />
                    )}
                  </button>
                  <button
                    onClick={() => handleDismissTag(tag)}
                    disabled={acceptingTag === tag}
                    className="text-muted-foreground hover:text-destructive transition-colors p-0.5"
                    title="Dismiss suggestion"
                  >
                    <X size={10} />
                  </button>
                </span>
              ))}
            </div>
          )}

          {/* Suggestion error */}
          {suggestError && (
            <p className="text-[10px] text-destructive mb-2">{suggestError}</p>
          )}

          <TagEditor
            tags={file.tags}
            fileId={file.id}
            onTagsChange={handleTagsChange}
          />
        </div>
      </div>
    </div>
  );
}

export default MetadataSidebar;
