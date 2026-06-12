import { type FC, useEffect, useState } from "react";
import mammoth from "mammoth";
import { getFileContentUrl } from "../../../api/kb";

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
        const response = await fetch(getFileContentUrl(fileId));
        if (!response.ok) throw new Error(`Failed to fetch: ${response.status}`);

        const arrayBuffer = await response.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });

        if (!cancelled) setHtml(result.value);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load DOCX");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadDocx();
    return () => { cancelled = true; };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-muted border-t-primary rounded-full animate-spin" />
          <span>Loading document...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-destructive">
        <span>{error}</span>
      </div>
    );
  }

  return (
    <div className="h-full overflow-auto p-6">
      <div
        className="docx-content max-w-none text-foreground leading-relaxed
          [&_h1]:text-2xl [&_h1]:font-bold [&_h1]:mt-6 [&_h1]:mb-3
          [&_h2]:text-xl [&_h2]:font-semibold [&_h2]:mt-5 [&_h2]:mb-2
          [&_h3]:text-lg [&_h3]:font-semibold [&_h3]:mt-4 [&_h3]:mb-2
          [&_h4]:text-base [&_h4]:font-medium [&_h4]:mt-3 [&_h4]:mb-1
          [&_p]:mb-3
          [&_ul]:list-disc [&_ul]:pl-6 [&_ul]:mb-3
          [&_ol]:list-decimal [&_ol]:pl-6 [&_ol]:mb-3
          [&_li]:mb-1
          [&_table]:w-full [&_table]:border-collapse [&_table]:mb-4
          [&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-3 [&_th]:py-2 [&_th]:text-left
          [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-2
          [&_a]:text-primary [&_a]:underline
          [&_strong]:font-bold
          [&_em]:italic
          [&_blockquote]:border-l-4 [&_blockquote]:border-muted-foreground [&_blockquote]:pl-4 [&_blockquote]:italic [&_blockquote]:my-3"
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
};

export default DocxViewer;
