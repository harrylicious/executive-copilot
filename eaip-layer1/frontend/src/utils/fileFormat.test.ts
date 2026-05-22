import { describe, it, expect } from "vitest";
import { detectFormat, isSupported } from "./fileFormat";

describe("detectFormat", () => {
  it("detects PDF format", () => {
    expect(detectFormat("report.pdf")).toBe("pdf");
  });

  it("detects Excel formats", () => {
    expect(detectFormat("data.xlsx")).toBe("xlsx");
    expect(detectFormat("legacy.xls")).toBe("xlsx");
  });

  it("detects JSON format", () => {
    expect(detectFormat("config.json")).toBe("json");
  });

  it("detects DOCX format", () => {
    expect(detectFormat("document.docx")).toBe("docx");
  });

  it("detects Markdown format", () => {
    expect(detectFormat("readme.md")).toBe("md");
  });

  it("detects plain text format", () => {
    expect(detectFormat("notes.txt")).toBe("txt");
  });

  it("detects CSV format", () => {
    expect(detectFormat("data.csv")).toBe("csv");
  });

  it("returns null for unsupported formats", () => {
    expect(detectFormat("image.png")).toBeNull();
    expect(detectFormat("video.mp4")).toBeNull();
    expect(detectFormat("archive.zip")).toBeNull();
  });

  it("handles case-insensitive extensions", () => {
    expect(detectFormat("REPORT.PDF")).toBe("pdf");
    expect(detectFormat("Data.XLSX")).toBe("xlsx");
    expect(detectFormat("README.MD")).toBe("md");
  });

  it("handles filenames with multiple dots", () => {
    expect(detectFormat("my.report.v2.pdf")).toBe("pdf");
    expect(detectFormat("data.backup.json")).toBe("json");
  });
});

describe("isSupported", () => {
  it("returns true for supported formats", () => {
    expect(isSupported("file.pdf")).toBe(true);
    expect(isSupported("file.xlsx")).toBe(true);
    expect(isSupported("file.xls")).toBe(true);
    expect(isSupported("file.json")).toBe(true);
    expect(isSupported("file.docx")).toBe(true);
    expect(isSupported("file.md")).toBe(true);
    expect(isSupported("file.txt")).toBe(true);
    expect(isSupported("file.csv")).toBe(true);
  });

  it("returns false for unsupported formats", () => {
    expect(isSupported("file.png")).toBe(false);
    expect(isSupported("file.exe")).toBe(false);
  });
});
