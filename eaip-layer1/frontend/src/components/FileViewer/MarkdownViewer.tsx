import { type FC, useEffect, useState } from "react";
import { marked } from "marked";
import { getFileContentUrl } from "../../api/client";

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
        if (!response.ok) {
          throw new Error(`Failed to load file (${response.status})`);
        }
        const text = await response.text();
        const rendered = await marked(text);
        if (!cancelled) {
          setHtml(rendered);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load markdown"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchAndRender();
    return () => {
      cancelled = true;
    };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        Loading markdown…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        {error}
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div
        className="prose prose-invert prose-sm max-w-none
          prose-headings:text-gray-100
          prose-p:text-gray-300
          prose-a:text-blue-400
          prose-strong:text-gray-200
          prose-code:text-green-400 prose-code:bg-gray-800 prose-code:px-1 prose-code:rounded
          prose-pre:bg-gray-800 prose-pre:border prose-pre:border-gray-700
          prose-blockquote:border-gray-600 prose-blockquote:text-gray-400
          prose-li:text-gray-300
          prose-table:text-gray-300
          prose-th:text-gray-200 prose-th:border-gray-600
          prose-td:border-gray-700"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};

export default MarkdownViewer;
