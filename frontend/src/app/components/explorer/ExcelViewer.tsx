import { type FC, useEffect, useState } from "react";
import * as XLSX from "xlsx";
import { getFileContentUrl } from "../../../api/kb";

interface ExcelViewerProps {
  fileId: number;
}

interface SheetData {
  headers: string[];
  rows: string[][];
}

const ExcelViewer: FC<ExcelViewerProps> = ({ fileId }) => {
  const [sheetNames, setSheetNames] = useState<string[]>([]);
  const [activeSheet, setActiveSheet] = useState<string>("");
  const [sheetData, setSheetData] = useState<SheetData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [workbook, setWorkbook] = useState<XLSX.WorkBook | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchExcel() {
      setLoading(true);
      setError(null);
      setSheetData(null);
      setSheetNames([]);
      setActiveSheet("");
      setWorkbook(null);

      try {
        const url = getFileContentUrl(fileId);
        const response = await fetch(url);
        if (cancelled) return;
        const blob = await response.arrayBuffer();
        const data = new Uint8Array(blob);
        const wb = XLSX.read(data, { type: "array" });

        setWorkbook(wb);
        setSheetNames(wb.SheetNames);
        setActiveSheet(wb.SheetNames[0] || "");
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "Failed to load Excel file");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchExcel();
    return () => { cancelled = true; };
  }, [fileId]);

  useEffect(() => {
    if (!workbook || !activeSheet) {
      setSheetData(null);
      return;
    }

    const worksheet = workbook.Sheets[activeSheet];
    if (!worksheet) { setSheetData(null); return; }

    const jsonData = XLSX.utils.sheet_to_json<string[]>(worksheet, { header: 1, defval: "" });

    if (jsonData.length === 0) {
      setSheetData({ headers: [], rows: [] });
      return;
    }

    const headers = jsonData[0].map((cell) => String(cell ?? ""));
    const rows = jsonData.slice(1).map((row) =>
      row.map((cell) => String(cell ?? ""))
    );

    setSheetData({ headers, rows });
  }, [workbook, activeSheet]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-muted-foreground">
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-muted border-t-primary rounded-full animate-spin" />
          <span>Loading spreadsheet...</span>
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
    <div className="flex flex-col h-full overflow-hidden">
      {sheetNames.length > 1 && (
        <div className="flex border-b border-border bg-muted/30 shrink-0 overflow-x-auto">
          {sheetNames.map((name) => (
            <button
              key={name}
              onClick={() => setActiveSheet(name)}
              className={`px-4 py-2 text-sm whitespace-nowrap transition-colors ${
                name === activeSheet
                  ? "bg-card text-foreground border-b-2 border-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {name}
            </button>
          ))}
        </div>
      )}

      <div className="flex-1 overflow-auto">
        {sheetData && sheetData.headers.length > 0 ? (
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 z-10">
              <tr className="bg-muted/80">
                {sheetData.headers.map((header, idx) => (
                  <th
                    key={idx}
                    className="px-3 py-2 text-left text-foreground font-medium border border-border whitespace-nowrap"
                  >
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sheetData.rows.map((row, rowIdx) => (
                <tr key={rowIdx} className={rowIdx % 2 === 0 ? "bg-card" : "bg-muted/20"}>
                  {row.map((cell, cellIdx) => (
                    <td
                      key={cellIdx}
                      className="px-3 py-1.5 text-foreground border border-border whitespace-nowrap"
                    >
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div className="flex items-center justify-center h-full text-muted-foreground">
            This sheet is empty
          </div>
        )}
      </div>
    </div>
  );
};

export default ExcelViewer;
