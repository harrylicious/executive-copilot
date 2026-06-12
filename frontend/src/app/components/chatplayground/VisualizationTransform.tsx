import { useState, useMemo } from "react";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  detectMarkdownTable,
  detectNumericData,
  detectList,
} from "../../../utils/visualizationDetector";
import type {
  TableData,
  NumericData,
  ListData,
  ListItem,
} from "../../../utils/visualizationDetector";

// ─── Constants ───────────────────────────────────────────────────────────────

const CHART_COLORS = ["#10b981", "#059669", "#047857", "#065f46", "#064e3b", "#6ee7b7"];

type ChartType = "bar" | "line" | "pie";
type SortDirection = "asc" | "desc" | null;

// ─── Sub-Components ──────────────────────────────────────────────────────────

interface TableViewProps {
  data: TableData;
}

function TableView({ data }: TableViewProps) {
  const [sortCol, setSortCol] = useState<number | null>(null);
  const [sortDir, setSortDir] = useState<SortDirection>(null);

  const sortedRows = useMemo(() => {
    if (sortCol === null || sortDir === null) return data.rows;
    return [...data.rows].sort((a, b) => {
      const aVal = a[sortCol] ?? "";
      const bVal = b[sortCol] ?? "";
      const aNum = Number(aVal.replace(/,/g, ""));
      const bNum = Number(bVal.replace(/,/g, ""));
      // Try numeric comparison first
      if (!isNaN(aNum) && !isNaN(bNum)) {
        return sortDir === "asc" ? aNum - bNum : bNum - aNum;
      }
      // Fall back to string comparison
      return sortDir === "asc"
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    });
  }, [data.rows, sortCol, sortDir]);

  function handleSort(colIndex: number) {
    if (sortCol === colIndex) {
      // Cycle: asc → desc → null
      if (sortDir === "asc") setSortDir("desc");
      else if (sortDir === "desc") {
        setSortCol(null);
        setSortDir(null);
      }
    } else {
      setSortCol(colIndex);
      setSortDir("asc");
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-secondary/50">
            {data.headers.map((header, i) => (
              <th
                key={i}
                className="px-3 py-2 text-left font-medium text-foreground cursor-pointer hover:bg-secondary/80 select-none border-b border-border"
                onClick={() => handleSort(i)}
              >
                <span className="flex items-center gap-1">
                  {header}
                  {sortCol === i && (
                    <span className="text-xs">
                      {sortDir === "asc" ? "▲" : "▼"}
                    </span>
                  )}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, rowIdx) => (
            <tr
              key={rowIdx}
              className="border-b border-border last:border-b-0 hover:bg-secondary/30"
            >
              {row.map((cell, cellIdx) => (
                <td key={cellIdx} className="px-3 py-2 text-muted-foreground">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ChartViewProps {
  data: NumericData;
}

function ChartView({ data }: ChartViewProps) {
  const [chartType, setChartType] = useState<ChartType>("bar");

  const chartData = useMemo(
    () => data.labels.map((label, i) => ({ name: label, value: data.values[i] })),
    [data]
  );

  return (
    <div className="space-y-3">
      {/* Chart type toggle */}
      <div className="flex gap-1 bg-secondary/50 rounded-lg p-1 w-fit">
        {(["bar", "line", "pie"] as ChartType[]).map((type) => (
          <button
            key={type}
            onClick={() => setChartType(type)}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
              chartType === type
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {type.charAt(0).toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>

      {/* Chart rendering */}
      <div className="w-full h-64">
        <ResponsiveContainer width="100%" height="100%">
          {chartType === "bar" ? (
            <BarChart data={chartData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Bar dataKey="value" fill={CHART_COLORS[0]} radius={[4, 4, 0, 0]} />
            </BarChart>
          ) : chartType === "line" ? (
            <LineChart data={chartData}>
              <XAxis dataKey="name" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                stroke={CHART_COLORS[0]}
                strokeWidth={2}
                dot={{ fill: CHART_COLORS[1], r: 4 }}
              />
            </LineChart>
          ) : (
            <PieChart>
              <Tooltip />
              <Pie
                data={chartData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={({ name, percent }) =>
                  `${name} (${(percent * 100).toFixed(0)}%)`
                }
                labelLine={false}
              >
                {chartData.map((_, index) => (
                  <Cell
                    key={`cell-${index}`}
                    fill={CHART_COLORS[index % CHART_COLORS.length]}
                  />
                ))}
              </Pie>
            </PieChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

interface ListViewProps {
  data: ListData;
}

function ListView({ data }: ListViewProps) {
  // Group consecutive items by their ordered/unordered type and level for proper nesting
  return (
    <div className="space-y-1">
      <ListGroup items={data.items} />
    </div>
  );
}

function ListGroup({ items }: { items: ListItem[] }) {
  if (items.length === 0) return null;

  // Render items respecting their nesting levels
  const elements: React.ReactNode[] = [];
  let i = 0;

  while (i < items.length) {
    const item = items[i];
    const isOrdered = item.ordered;
    const level = item.level;

    // Collect consecutive items at the same level and type
    const group: ListItem[] = [];
    while (
      i < items.length &&
      items[i].level === level &&
      items[i].ordered === isOrdered
    ) {
      group.push(items[i]);
      i++;
    }

    // Check for nested items (items at a deeper level following this group)
    // We already moved past the group, so just render it
    const ListTag = isOrdered ? "ol" : "ul";
    const listStyle = isOrdered ? "list-decimal" : "list-disc";

    elements.push(
      <ListTag
        key={`list-${elements.length}`}
        className={`${listStyle} pl-5 space-y-1 text-sm text-muted-foreground`}
        style={{ marginLeft: `${level * 16}px` }}
      >
        {group.map((listItem, idx) => (
          <li key={idx} className="leading-relaxed">
            {listItem.content}
          </li>
        ))}
      </ListTag>
    );
  }

  return <>{elements}</>;
}

// ─── Main Component ──────────────────────────────────────────────────────────

interface VisualizationTransformProps {
  text: string;
}

/**
 * Detects structured data in AI response text and renders appropriate visualizations.
 * Priority: table > numeric > list. Returns null if no structure detected.
 */
export function VisualizationTransform({ text }: VisualizationTransformProps) {
  const detected = useMemo(() => {
    // Priority order: table > numeric > list
    const table = detectMarkdownTable(text);
    if (table) return { type: "table" as const, data: table };

    const numeric = detectNumericData(text);
    if (numeric) return { type: "numeric" as const, data: numeric };

    const list = detectList(text);
    if (list) return { type: "list" as const, data: list };

    return null;
  }, [text]);

  if (!detected) return null;

  switch (detected.type) {
    case "table":
      return <TableView data={detected.data as TableData} />;
    case "numeric":
      return <ChartView data={detected.data as NumericData} />;
    case "list":
      return <ListView data={detected.data as ListData} />;
    default:
      return null;
  }
}
