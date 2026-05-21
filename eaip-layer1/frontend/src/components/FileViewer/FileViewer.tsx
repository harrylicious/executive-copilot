import type { FC } from "react";
import type { FileNode, SupportedFormat } from "../../types";
import { detectFormat } from "../../utils/fileFormat";
import { ScrollArea } from "@/components/ui/scroll-area";
import PdfViewer from "./PdfViewer";
import ExcelViewer from "./ExcelViewer";
import JsonViewer from "./JsonViewer";
import DocxViewer from "./DocxViewer";
import MarkdownViewer from "./MarkdownViewer";
import PlainTextViewer from "./PlainTextViewer";
import { FileText } from "lucide-react";

interface FileViewerProps {
  file: FileNode | null;
}

const VIEWER_MAP: Record<SupportedFormat, FC<{ fileId: number }>> = {
  pdf: PdfViewer,
  xlsx: ExcelViewer,
  json: JsonViewer,
  docx: DocxViewer,
  md: MarkdownViewer,
  txt: PlainTextViewer,
};

export const FileViewer: FC<FileViewerProps> = ({ file }) => {
  if (!file) {
    return (
      <div className="h-full flex flex-col items-center justify-center text-muted-foreground gap-2">
        <FileText className="size-8 opacity-40" />
        <span className="text-sm">Select a file to view</span>
      </div>
    );
  }

  const format = detectFormat(file.name);

  if (!format) {
    return (
      <div className="h-full flex items-center justify-center text-muted-foreground text-sm">
        Unsupported format: .{file.name.split(".").pop()}
      </div>
    );
  }

  const Viewer = VIEWER_MAP[format];

  // PDF viewer manages its own scrolling
  if (format === "pdf") {
    return (
      <div className="h-full flex flex-col overflow-hidden">
        <div className="px-4 py-2 border-b border-border shrink-0">
          <span className="text-xs text-muted-foreground truncate">{file.name}</span>
        </div>
        <div className="flex-1 overflow-hidden">
          <Viewer fileId={file.id} />
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="px-4 py-2 border-b border-border shrink-0">
        <span className="text-xs text-muted-foreground truncate">{file.name}</span>
      </div>
      <ScrollArea className="flex-1">
        <div className="p-4">
          <Viewer fileId={file.id} />
        </div>
      </ScrollArea>
    </div>
  );
};
