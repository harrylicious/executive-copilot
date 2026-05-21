import type { SupportedFormat } from "../types";

const FORMAT_MAP: Record<string, SupportedFormat> = {
  ".pdf": "pdf",
  ".xlsx": "xlsx",
  ".xls": "xlsx",
  ".json": "json",
  ".docx": "docx",
  ".md": "md",
  ".txt": "txt",
};

export function detectFormat(filename: string): SupportedFormat | null {
  const ext = filename.substring(filename.lastIndexOf(".")).toLowerCase();
  return FORMAT_MAP[ext] ?? null;
}

export function isSupported(filename: string): boolean {
  return detectFormat(filename) !== null;
}
