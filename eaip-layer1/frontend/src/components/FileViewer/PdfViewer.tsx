import { type FC, useEffect, useRef, useState, useCallback } from "react";
import * as pdfjsLib from "pdfjs-dist";
import type { PDFDocumentProxy, RenderTask } from "pdfjs-dist";
import { getFileContentUrl } from "../../api/client";
import { Button } from "@/components/ui/button";
import {
  ChevronLeft,
  ChevronRight,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  MousePointer2,
  Hand,
} from "lucide-react";
import { cn } from "@/lib/utils";

import pdfjsWorkerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorkerUrl;

interface PdfViewerProps {
  fileId: number;
}

type ViewMode = "view" | "text";

const ZOOM_LEVELS = [0.5, 0.75, 1, 1.25, 1.5, 2, 2.5, 3];
const DEFAULT_ZOOM_INDEX = 2; // 1x

const PdfViewer: FC<PdfViewerProps> = ({ fileId }) => {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const textLayerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
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

  // Load the PDF document
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
        const loadingTask = pdfjsLib.getDocument({
          url,
          cMapPacked: true,
        });
        const doc = await loadingTask.promise;

        if (cancelled) {
          doc.destroy();
          return;
        }

        loadedDoc = doc;
        setPdfDoc(doc);
        setTotalPages(doc.numPages);
        setCurrentPage(1);
      } catch (err) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : String(err);
          setError(msg);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    loadPdf();

    return () => {
      cancelled = true;
      if (loadedDoc) {
        loadedDoc.destroy();
      }
    };
  }, [fileId]);

  // Render the current page at current zoom
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

        // Use zoom level as scale, with device pixel ratio for sharpness
        const dpr = window.devicePixelRatio || 1;
        const scale = zoom * dpr;
        const viewport = page.getViewport({ scale });
        const cssViewport = page.getViewport({ scale: zoom });

        canvas.width = viewport.width;
        canvas.height = viewport.height;
        canvas.style.width = `${cssViewport.width}px`;
        canvas.style.height = `${cssViewport.height}px`;

        // Set page container size for text layer alignment
        if (pageContainerRef.current) {
          pageContainerRef.current.style.width = `${cssViewport.width}px`;
          pageContainerRef.current.style.height = `${cssViewport.height}px`;
        }

        const renderTask = page.render({
          canvasContext: ctx,
          viewport,
        });
        renderTaskRef.current = renderTask;

        await renderTask.promise;
        renderTaskRef.current = null;

        // Render text layer for text selection mode
        if (textLayerRef.current) {
          textLayerRef.current.innerHTML = "";
          const textContent = await page.getTextContent();
          if (cancelled) return;

          const textItems = textContent.items;
          for (const item of textItems) {
            if (!("str" in item) || !item.str) continue;

            const tx = pdfjsLib.Util.transform(
              cssViewport.transform,
              item.transform
            );

            const span = document.createElement("span");
            span.textContent = item.str;
            span.style.position = "absolute";
            span.style.left = `${tx[4]}px`;
            span.style.top = `${cssViewport.height - tx[5]}px`;
            span.style.fontSize = `${Math.abs(tx[0])}px`;
            span.style.fontFamily = "sans-serif";
            span.style.transformOrigin = "0% 0%";
            // Make text transparent in view mode, visible in text mode
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
      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border shrink-0 bg-muted/30">
        {/* Page navigation */}
        <div className="flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={goToPreviousPage}
            disabled={currentPage <= 1}
            aria-label="Previous page"
          >
            <ChevronLeft className="size-3.5" />
          </Button>
          <span className="text-xs text-muted-foreground tabular-nums min-w-[4rem] text-center">
            {currentPage} / {totalPages}
          </span>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={goToNextPage}
            disabled={currentPage >= totalPages}
            aria-label="Next page"
          >
            <ChevronRight className="size-3.5" />
          </Button>
        </div>

        {/* Mode toggle + Zoom controls */}
        <div className="flex items-center gap-1">
          {/* View/Text mode toggle */}
          <div className="flex items-center border border-border rounded-md mr-2">
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setViewMode("view")}
              className={cn(
                "rounded-r-none",
                viewMode === "view" && "bg-primary/10 text-primary"
              )}
              aria-label="View mode"
              title="View mode"
            >
              <Hand className="size-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={() => setViewMode("text")}
              className={cn(
                "rounded-l-none",
                viewMode === "text" && "bg-primary/10 text-primary"
              )}
              aria-label="Text selection mode"
              title="Text selection mode (select & copy)"
            >
              <MousePointer2 className="size-3.5" />
            </Button>
          </div>

          {/* Zoom */}
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handleZoomOut}
            disabled={zoomIndex <= 0}
            aria-label="Zoom out"
          >
            <ZoomOut className="size-3.5" />
          </Button>
          <button
            onClick={handleZoomReset}
            className="text-xs text-muted-foreground hover:text-foreground tabular-nums min-w-[3rem] text-center transition-colors"
            title="Reset zoom"
          >
            {Math.round(zoom * 100)}%
          </button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handleZoomIn}
            disabled={zoomIndex >= ZOOM_LEVELS.length - 1}
            aria-label="Zoom in"
          >
            <ZoomIn className="size-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="icon-xs"
            onClick={handleZoomReset}
            aria-label="Reset zoom"
            className="ml-1"
          >
            <RotateCcw className="size-3" />
          </Button>
        </div>
      </div>

      {/* PDF canvas + text layer */}
      <div
        ref={containerRef}
        className={cn(
          "flex-1 overflow-auto flex justify-center p-4 bg-muted/10",
          viewMode === "text" && "cursor-text"
        )}
      >
        <div ref={pageContainerRef} className="relative shadow-sm rounded">
          <canvas ref={canvasRef} className="block" />
          {/* Text layer overlay for selection */}
          <div
            ref={textLayerRef}
            className={cn(
              "absolute inset-0 overflow-hidden",
              viewMode === "text"
                ? "pointer-events-auto select-text [&_span]:!text-transparent [&_span]:selection:bg-primary/30"
                : "pointer-events-none select-none"
            )}
            style={{ mixBlendMode: viewMode === "text" ? "multiply" : undefined }}
          />
        </div>
      </div>
    </div>
  );
};

export default PdfViewer;
