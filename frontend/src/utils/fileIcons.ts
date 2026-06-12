import type { LucideIcon } from "lucide-react";
import {
  FileText,
  FileSpreadsheet,
  Table,
  FileType,
  FileCode,
  FileJson,
  Image,
  File,
} from "lucide-react";

export interface FileIconInfo {
  icon: LucideIcon;
  color: string;
}

const iconMap: Record<string, FileIconInfo> = {
  pdf: { icon: FileText, color: "#ef4444" },
  xlsx: { icon: FileSpreadsheet, color: "#10b981" },
  xls: { icon: FileSpreadsheet, color: "#10b981" },
  csv: { icon: Table, color: "#22c55e" },
  docx: { icon: FileText, color: "#3b82f6" },
  txt: { icon: FileType, color: "#6b7280" },
  md: { icon: FileCode, color: "#6b7280" },
  json: { icon: FileJson, color: "#8b5cf6" },
  png: { icon: Image, color: "#a855f7" },
  jpg: { icon: Image, color: "#a855f7" },
  tiff: { icon: Image, color: "#a855f7" },
};

const defaultIcon: FileIconInfo = { icon: File, color: "#6b7280" };

/**
 * Returns the appropriate icon component and color for a given file extension.
 * Extension matching is case-insensitive.
 */
export function getFileIcon(extension: string): FileIconInfo {
  const normalized = extension.toLowerCase().replace(/^\./, "");
  return iconMap[normalized] ?? defaultIcon;
}
