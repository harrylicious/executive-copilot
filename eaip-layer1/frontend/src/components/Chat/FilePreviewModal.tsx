import { useState, type FC } from "react";
import type { FileNode, SupportedFormat } from "@/types";
import { detectFormat } from "@/utils/fileFormat";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import PdfViewer from "@/components/FileViewer/PdfViewer";
import ExcelViewer from "@/components/FileViewer/ExcelViewer";
import JsonViewer from "@/components/FileViewer/JsonViewer";
import DocxViewer from "@/components/FileViewer/DocxViewer";
import MarkdownViewer from "@/components/FileViewer/MarkdownViewer";
import PlainTextViewer from "@/components/FileViewer/PlainTextViewer";
import { FileText, Maximize2, Minimize2 } from "lucide-react";
import { cn } from "@/lib/utils";

const VIEWER_MAP: Record<SupportedFormat, FC<{ fileId: number }>> = {
  pdf: PdfViewer,
  xlsx: ExcelViewer,
  json: JsonViewer,
  docx: DocxViewer,
  md: MarkdownViewer,
  txt: PlainTextViewer,
};

interface FilePreviewModalProps {
  file: FileNode | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export const FilePreviewModal: FC<FilePreviewModalProps> = ({
  file,
  open,
  onOpenChange,
}) => {
  const [isFullscreen, setIsFullscreen] = useState(false);

  if (!file) return null;

  const format = detectFormat(file.name);
  const Viewer = format ? VIEWER_MAP[format] : null;

  return (
    <Dialog open={open} onOpenChange={(v) => { onOpenChange(v); if (!v) setIsFullscreen(false); }}>
      <DialogContent
        className={cn(
          "flex flex-col p-0 gap-0 transition-all duration-200 overflow-hidden",
          isFullscreen
            ? "max-w-none w-screen h-screen rounded-none sm:max-w-none"
            : "max-w-5xl w-[92vw] h-[55vh] sm:max-w-5xl"
        )}
        showCloseButton={false}
      >
        {/* Header */}
        <DialogHeader className="px-4 py-2.5 border-b border-border shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 min-w-0">
              <FileText className="size-4 text-muted-foreground shrink-0" />
              <DialogTitle className="text-sm font-medium truncate">
                {file.name}
              </DialogTitle>
            </div>
            <div className="flex items-center gap-1 shrink-0">
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => setIsFullscreen((f) => !f)}
                aria-label={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
              >
                {isFullscreen ? (
                  <Minimize2 className="size-3.5" />
                ) : (
                  <Maximize2 className="size-3.5" />
                )}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                onClick={() => onOpenChange(false)}
                aria-label="Close"
              >
                <span className="text-lg leading-none">&times;</span>
              </Button>
            </div>
          </div>
          <DialogDescription className="flex items-center gap-2 mt-0.5">
            <Badge variant="secondary" className="text-[10px] h-5">
              {file.department.replace(/_/g, " ")}
            </Badge>
            {file.fileType && (
              <Badge variant="outline" className="text-[10px] h-5 uppercase">
                {file.fileType}
              </Badge>
            )}
            <span className="text-[10px] text-muted-foreground">
              {formatSize(file.size)}
            </span>
          </DialogDescription>
        </DialogHeader>

        {/* Content */}
        <div className="min-h-0 flex-1 overflow-hidden">
          {Viewer ? (
            format === "pdf" ? (
              <div className="h-full">
                <Viewer fileId={file.id} />
              </div>
            ) : (
              <div className="h-full overflow-auto p-4">
                <Viewer fileId={file.id} />
              </div>
            )
          ) : (
            <div className="h-40 flex items-center justify-center text-muted-foreground text-sm">
              Unsupported format: .{file.name.split(".").pop()}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
