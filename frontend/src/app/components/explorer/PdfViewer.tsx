import { type FC, useEffect, useRef, useState, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { getFileContentUrl } from "../../../api/kb";
import { ChevronLeft, ChevronRight, ZoomIn, ZoomOut, RotateCcw, MousePointer2, Hand } from "lucide-react";
import { cn } from "../../../utils/cn";

import pdfjsWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

interface PdfViewerProps {
  fileId: number;
}

type ViewMode = "view" | "text";

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const DEFAULT_ZOOM_INDEX = 2;

const PdfViewer: FC<PdfViewerProps> = ({ fileId }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const pageContainerRef = useRef<HTMLDivElement>(null);
  const [pdfDoc, setPdfDoc] = useState<PDFDocumentProxy | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [zoomIndex, setZoomIndex] = useState(DEFAULT_ZOOM_INDEX);
  const [viewMode, setViewMode] = useState<ViewMode>("view");
  const renderTaskRef = useRef<RenderTask | null>(null);

  const zoom = ZOOM_LEVELS[zoomIndex];

  useEffect(() => {
    let cancelled = false;
    let loadedDoc: PDFDocumentProxy | null = null;

    const loadPdf = async () => {
      setLoading(true);
      setError(null);
      setPdfDoc(null);
      setCurrentPage(1);
      setTotalPages(0);
      setZoomIndex(DEFAULT_ZOOM_INDEX);

      try {
        const url = getFileContentUrl(fileId);
        const loadingTask = pdfjsLib.getDocument({ url, cMapPacked: true });
        const doc = await loadingTask.promise;

        if (cancelled) { doc.destroy(); return; }

        loadedDoc = doc;
        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setCurrentPage(1);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
      if (loadedDoc) loadedDoc.destroy();
    };
  }, [fileId]);

  useEffect(() => {
    if (!pdfDoc || !canvasRef.current) return;

    let cancelled = false;

    const renderPage = async () => {
      if (renderTaskRef.current) {
        try { renderTaskRef.current.cancel(); } catch { /* ignore */ }
        renderTaskRef.current = null;
      }

      try {
        const page = await pdfDoc.getPage(currentPage);
        if (cancelled) return;

        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext("2d");
        if (!ctx) return;

        const dpr = window.devicePixelRatio || 1;
        const scale = zoom * dpr;
        const viewport = page.getViewport({ scale });
        const cssViewport = page.getViewport({ scale: zoom });

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${cssViewport.width}px`;
        canvas.style.height = `${cssViewport.height}px`;

        if (pageContainerRef.current) {
          pageContainerRef.current.style.width = `${cssViewport.width}px`;
          pageContainerRef.current.style.height = `${cssViewport.height}px`;
        }

        const renderTask = page.render({ canvasContext: ctx, viewport });
        renderTaskRef.current = renderTask;

        await renderTask.promise;
        renderTaskRef.current = null;

        if (textLayerRef.current) {
          textLayerRef.current.innerHTML = "";
          const textContent = await page.getTextContent();
          if (cancelled) return;

          const textItems = textContent.items;
          for (const item of textItems) {
            if (!("str" in item) || !item.str) continue;

            const tx = pdfjsLib.Util.transform(cssViewport.transform, item.transform);

            const span = document.createElement("span");
            span.textContent = item.str;
            span.style.position = "absolute";
            span.style.left = `${tx[4]}px`;
            span.style.top = `${cssViewport.height - tx[5]}px`;
            span.style.fontSize = `${Math.abs(tx[0])}px`;
            span.style.fontFamily = "sans-serif";
            span.style.transformOrigin = "0% 0%";
            span.style.color = "transparent";
            span.style.whiteSpace = "pre";
            span.style.lineHeight = "1";

            textLayerRef.current.appendChild(span);
          }
        }
      } catch (err) {
        if (cancelled) return;
        if (err instanceof Error && err.message.includes("Rendering cancelled")) return;
        setError(err instanceof Error ? err.message : "Failed to render page");
      }
    };

    renderPage();

    return () => {
      cancelled = true;
      if (renderTaskRef.current) {
        try { renderTaskRef.current.cancel(); } catch { /* ignore */ }
        renderTaskRef.current = null;
      }
    };
  }, [pdfDoc, currentPage, zoom]);

  const goToPreviousPage = useCallback(() => {
    setCurrentPage((prev) => Math.max(1, prev - 1));
  }, []);

  const goToNextPage = useCallback(() => {
    setCurrentPage((prev) => Math.min(totalPages, prev + 1));
  }, [totalPages]);

  const handleZoomIn = useCallback(() => {
    setZoomIndex((prev) => Math.min(ZOOM_LEVELS.length - 1, prev + 1));
  }, []);

  const handleZoomOut = useCallback(() => {
    setZoomIndex((prev) => Math.max(0, prev - 1));
  }, []);

  const handleZoomReset = useCallback(() => {
    setZoomIndex(DEFAULT_ZOOM_INDEX);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <div className="w-5 h-5 border-2 border-muted border-t-primary rounded-full animate-spin" />
          <span className="text-xs">Loading PDF...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-1.5 text-center px-4">
          <span className="text-sm text-destructive">Failed to load PDF</span>
          <span className="text-xs text-muted-foreground max-w-sm">{error}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border shrink-0 bg-muted/30">
        <div className="flex items-center gap-1.5">
          <button
            onClick={goToPreviousPage}
            disabled={currentPage <= 1}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Previous page"
          >
            <ChevronLeft className="size-3.5" />
          </button>
          <span className="text-xs text-muted-foreground tabular-nums min-w-[4rem] text-center">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={goToNextPage}
            disabled={currentPage >= totalPages}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Next page"
          >
            <ChevronRight className="size-3.5" />
          </button>
        </div>

        <div className="flex items-center gap-1">
          <div className="flex items-center border border-border rounded-md mr-2">
            <button
              onClick={() => setViewMode("view")}
              className={`p-1 rounded-l-md transition-colors ${viewMode === "view" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"}`}
              aria-label="View mode"
              title="View mode"
            >
              <Hand className="size-3.5" />
            </button>
            <button
              onClick={() => setViewMode("text")}
              className={`p-1 rounded-r-md transition-colors ${viewMode === "text" ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground"}`}
              aria-label="Text selection mode"
              title="Text selection mode"
            >
              <MousePointer2 className="size-3.5" />
            </button>
          </div>

          <button
            onClick={handleZoomOut}
            disabled={zoomIndex <= 0}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Zoom out"
          >
            <ZoomOut className="size-3.5" />
          </button>
          <button
            onClick={handleZoomReset}
            className="text-xs text-muted-foreground hover:text-foreground tabular-nums min-w-[3rem] text-center transition-colors"
            title="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            onClick={handleZoomIn}
            disabled={zoomIndex >= ZOOM_LEVELS.length - 1}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground disabled:opacity-30"
            aria-label="Zoom in"
          >
            <ZoomIn className="size-3.5" />
          </button>
          <button
            onClick={handleZoomReset}
            className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground ml-1"
            aria-label="Reset zoom"
          >
            <RotateCcw className="size-3" />
          </button>
        </div>
      </div>

      <div
        className={`flex-1 overflow-auto flex justify-center p-4 bg-muted/10 ${viewMode === "text" ? "cursor-text" : ""}`}
      >
        <div ref={pageContainerRef} className="relative shadow-sm rounded">
          <canvas ref={canvasRef} className="block" />
          <div
            ref={textLayerRef}
            className={`absolute inset-0 overflow-hidden ${
              viewMode === "text"
                ? "pointer-events-auto select-text"
                : "pointer-events-none select-none"
            }`}
            style={viewMode === "text" ? { mixBlendMode: "multiply" } : undefined}
          />
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
