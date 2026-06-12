import { type FC, useEffect, useState } from "react";
import { getFileContentUrl } from "../../../api/kb";

interface PlainTextViewerProps {
  fileId: number;
}

const PlainTextViewer: FC<PlainTextViewerProps> = ({ fileId }) => {
  const [content, setContent] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchContent() {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(getFileContentUrl(fileId));
        if (!response.ok) throw new Error(`Failed to load (${response.status})`);
        const text = await response.text();
        if (!cancelled) setContent(text);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load file");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchContent();
    return () => { cancelled = true; };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        Loading file...
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
      <pre className="font-mono text-sm text-foreground whitespace-pre-wrap break-words bg-muted/50 border border-border rounded-lg p-4">
        {content}
      </pre>
    </div>
  );
};

export default PlainTextViewer;
