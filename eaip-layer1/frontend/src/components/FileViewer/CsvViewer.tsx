import { type FC, useEffect, useState } from "react";
import { getFileContentUrl } from "../../api/client";

interface CsvViewerProps {
  fileId: number;
}

interface ParsedCsv {
  headers: string[];
  rows: string[][];
}

function parseCsv(text: string): ParsedCsv {
  const lines: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (i + 1 < text.length && text[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += ch;
      }
    } else {
      if (ch === '"') {
        inQuotes = true;
      } else if (ch === "\n") {
        lines.push(current);
        current = "";
      } else if (ch === "\r") {
        // skip
      } else {
        current += ch;
      }
    }
  }
  if (current) lines.push(current);

  const data = lines.map((line) => {
    const fields: string[] = [];
    let field = "";
    let q = false;
    for (let i = 0; i < line.length; i++) {
      const c = line[i];
      if (q) {
        if (c === '"') {
          if (i + 1 < line.length && line[i + 1] === '"') {
            field += '"';
            i++;
          } else {
            q = false;
          }
        } else {
          field += c;
        }
      } else {
        if (c === '"') {
          q = true;
        } else if (c === ",") {
          fields.push(field);
          field = "";
        } else {
          field += c;
        }
      }
    }
    fields.push(field);
    return fields;
  });

  if (data.length === 0) return { headers: [], rows: [] };
  return { headers: data[0], rows: data.slice(1) };
}

const CsvViewer: FC<CsvViewerProps> = ({ fileId }) => {
  const [data, setData] = useState<ParsedCsv | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchCsv() {
      setLoading(true);
      setError(null);
      setData(null);

      try {
        const response = await fetch(getFileContentUrl(fileId));
        if (!response.ok) {
          throw new Error(`Failed to load CSV (${response.status})`);
        }
        const text = await response.text();
        if (!cancelled) {
          setData(parseCsv(text));
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load CSV"
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    fetchCsv();
    return () => {
      cancelled = true;
    };
  }, [fileId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-gray-400">
        <div className="flex flex-col items-center gap-2">
          <div className="w-6 h-6 border-2 border-gray-500 border-t-green-400 rounded-full animate-spin" />
          <span>Loading CSV…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full text-red-400">
        <div className="flex flex-col items-center gap-2">
          <span className="text-lg">⚠</span>
          <span>{error}</span>
        </div>
      </div>
    );
  }

  if (!data || data.headers.length === 0) {
    return (
      <div className="flex items-center justify-center h-full text-gray-500">
        This CSV is empty
      </div>
    );
  }

  return (
    <div className="overflow-auto">
      <table className="w-full border-collapse text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="bg-gray-800">
            {data.headers.map((header, idx) => (
              <th
                key={idx}
                className="px-3 py-2 text-left text-gray-200 font-medium border border-gray-700 whitespace-nowrap"
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, rowIdx) => (
            <tr
              key={rowIdx}
              className={
                rowIdx % 2 === 0 ? "bg-gray-900" : "bg-gray-900/60"
              }
            >
              {row.map((cell, cellIdx) => (
                <td
                  key={cellIdx}
                  className="px-3 py-1.5 text-gray-300 border border-gray-700 whitespace-nowrap"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default CsvViewer;
