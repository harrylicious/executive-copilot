import { useState } from "react";
import { X, Plus } from "lucide-react";
import { updateFileTags } from "../../../api/kb";

interface TagEditorProps {
  tags: string[];
  fileId: number;
  onTagsChange: (tags: string[]) => void;
}

export function TagEditor({ tags, fileId, onTagsChange }: TagEditorProps) {
  const [input, setInput] = useState("");
  const [saving, setSaving] = useState(false);

  const handleAdd = async () => {
    const tag = input.trim().toLowerCase();
    if (!tag || tags.includes(tag)) return;
    setSaving(true);
    try {
      const newTags = [...tags, tag];
      await updateFileTags(fileId, newTags);
      onTagsChange(newTags);
      setInput("");
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  const handleRemove = async (tag: string) => {
    setSaving(true);
    try {
      const newTags = tags.filter((t) => t !== tag);
      await updateFileTags(fileId, newTags);
      onTagsChange(newTags);
    } catch {
      // silently fail
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {tags.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 bg-secondary border border-border rounded-md px-2 py-0.5 text-xs text-secondary-foreground"
          >
            {tag}
            <button
              onClick={() => handleRemove(tag)}
              disabled={saving}
              className="text-muted-foreground hover:text-destructive transition-colors"
            >
              <X size={10} />
            </button>
          </span>
        ))}
      </div>

      <div className="flex gap-1">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") { e.preventDefault(); handleAdd(); }
          }}
          placeholder="Add tag..."
          className="flex-1 bg-input border border-border rounded-md px-2 py-1 text-xs text-foreground placeholder-muted-foreground focus:outline-none focus:border-primary/40"
        />
        <button
          onClick={handleAdd}
          disabled={!input.trim() || saving}
          className="p-1 rounded-md bg-primary/10 text-primary hover:bg-primary/20 disabled:opacity-30 transition-colors"
        >
          <Plus size={12} />
        </button>
      </div>
    </div>
  );
}

export default TagEditor;
