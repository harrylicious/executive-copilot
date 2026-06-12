import { type FC, useEffect, useState } from "react";
import { marked } from "marked";
import { getFileContentUrl } from "../../../api/kb";

interface MarkdownViewerProps {
  fileId: number;
}

const MarkdownViewer: FC<MarkdownViewerProps> = ({ fileId }) => {
  const [html, setHtml] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchAndRender() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(getFileContentUrl(fileId));
        if (!response.ok) throw new Error(`Failed to load (${response.status})`);
        const text = await response.text();
        const rendered = await marked(text);
        if (!cancelled) setHtml(rendered);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load markdown");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchAndRender();
    return () => { cancelled = true; };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading markdown...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div
        className="prose prose-sm dark:prose-invert max-w-none"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};

export default MarkdownViewer;
