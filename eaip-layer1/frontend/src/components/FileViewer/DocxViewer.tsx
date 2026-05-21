import { type FC, useEffect, useState } from "react";
import mammoth from "mammoth";

interface DocxViewerProps {
  fileId: number;
}

const DocxViewer: FC<DocxViewerProps> = ({ fileId }) => {
  const [html, setHtml] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadDocx() {
      setLoading(true);
      setError(null);
      setHtml("");

      try {
        const response = await fetch(`/api/files/${fileId}/content`);
        if (!response.ok) {
          throw new Error(
            `Failed to fetch file: ${response.status} ${response.statusText}`
          );
        }

        const arrayBuffer = await response.arrayBuffer();

        const result = await mammoth.convertToHtml({ arrayBuffer });

        if (!cancelled) {
          setHtml(result.value);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load DOCX file"
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDocx();

    return () => {
      cancelled = true;
    };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="flex flex-col items-center gap-2">
          <svg
            className="animate-spin h-6 w-6 text-gray-400"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span>Loading document...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        <div className="flex flex-col items-center gap-2">
          <svg
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div
        className="docx-content max-w-none text-gray-200 leading-relaxed
          [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:text-gray-100 [&_h1]:mt-6 [&_h1]:mb-3
          [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:text-gray-100 [&_h2]:mt-5 [&_h2]:mb-2
          [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:text-gray-200 [&_h3]:mt-4 [&_h3]:mb-2
          [&_h4]:text-base [&_h4]:font-medium [&_h4]:text-gray-200 [&_h4]:mt-3 [&_h4]:mb-1
          [&_p]:mb-3 [&_p]:text-gray-300
          [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-3
          [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-3
          [&_li]:mb-1 [&_li]:text-gray-300
          [&_table]:w-full [&_table]:border-collapse [&_table]:mb-4
          [&_th]:border [&_th]:border-gray-600 [&_th]:bg-gray-700 [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-gray-200
          [&_td]:border [&_td]:border-gray-600 [&_td]:px-3 [&_td]:py-2 [&_td]:text-gray-300
          [&_a]:text-blue-400 [&_a]:underline hover:[&_a]:text-blue-300
          [&_strong]:font-bold [&_strong]:text-gray-100
          [&_em]:italic
          [&_blockquote]:border-l-4 [&_blockquote]:border-gray-500 [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:text-gray-400 [&_blockquote]:my-3
          [&_img]:max-w-full [&_img]:h-auto [&_img]:my-3"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};

export default DocxViewer;
