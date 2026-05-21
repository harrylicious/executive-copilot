import { type FC, useState, useCallback } from "react";
import type { FileNode } from "../../types";
import { updateFileTags } from "../../api/client";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

interface TagEditorProps {
  fileId: number;
  tags: string[];
  onTagsUpdated?: (updatedFile: FileNode) => void;
}

export const TagEditor: FC<TagEditorProps> = ({
  fileId,
  tags,
  onTagsUpdated,
}) => {
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const persistTags = useCallback(
    async (newTags: string[]) => {
      setIsLoading(true);
      try {
        const updatedFile = await updateFileTags(fileId, newTags);
        onTagsUpdated?.(updatedFile);
      } finally {
        setIsLoading(false);
      }
    },
    [fileId, onTagsUpdated]
  );

  const handleAddTag = useCallback(async () => {
    const trimmed = inputValue.trim();
    if (!trimmed || tags.includes(trimmed)) {
      setInputValue("");
      return;
    }
    const newTags = [...tags, trimmed];
    setInputValue("");
    await persistTags(newTags);
  }, [inputValue, tags, persistTags]);

  const handleRemoveTag = useCallback(
    async (tagToRemove: string) => {
      const newTags = tags.filter((t) => t !== tagToRemove);
      await persistTags(newTags);
    },
    [tags, persistTags]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddTag();
      }
    },
    [handleAddTag]
  );

  return (
    <div className="space-y-3">
      <span className="text-muted-foreground block text-xs uppercase tracking-wide">
        Tags
      </span>

      {/* Current tags */}
      <div className="flex flex-wrap gap-1.5">
        {tags.length === 0 && (
          <span className="text-muted-foreground text-xs italic">No tags</span>
        )}
        {tags.map((tag) => (
          <Badge
            key={tag}
            variant="outline"
            className="gap-1 bg-primary/20 text-primary border-primary/40"
          >
            {tag}
            <button
              type="button"
              onClick={() => handleRemoveTag(tag)}
              disabled={isLoading}
              className="hover:text-destructive ml-0.5 disabled:opacity-50"
              aria-label={`Remove tag ${tag}`}
            >
              ×
            </button>
          </Badge>
        ))}
      </div>

      {/* Add tag input */}
      <div className="flex gap-2">
        <Input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          placeholder="Add tag..."
          className="flex-1 h-7 text-xs"
        />
        <Button
          type="button"
          onClick={handleAddTag}
          disabled={isLoading || !inputValue.trim()}
          size="xs"
        >
          Add
        </Button>
      </div>

      {/* Loading indicator */}
      {isLoading && (
        <span className="text-xs text-muted-foreground">Saving...</span>
      )}
    </div>
  );
};

export default TagEditor;
