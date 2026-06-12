/**
 * Visualization detection utilities for structured data in AI responses.
 * Detects markdown tables, numeric data patterns, and lists.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface TableData {
  headers: string[];
  rows: string[][];
}

export interface NumericData {
  labels: string[];
  values: number[];
}

export interface ListItem {
  content: string;
  level: number;
  ordered: boolean;
}

export interface ListData {
  items: ListItem[];
}

// ─── Constants ───────────────────────────────────────────────────────────────

const MAX_TABLE_ROWS = 100;
const MAX_TABLE_COLUMNS = 20;
const MAX_DATA_POINTS = 50;
const MAX_NESTING_LEVELS = 4;

// ─── Helpers ─────────────────────────────────────────────────────────────────

function parseCells(row: string): string[] {
  // Remove leading/trailing pipes then split on remaining pipes
  const trimmed = row.trim();
  const withoutOuterPipes = trimmed.startsWith("|")
    ? trimmed.slice(1)
    : trimmed;
  const cleaned = withoutOuterPipes.endsWith("|")
    ? withoutOuterPipes.slice(0, -1)
    : withoutOuterPipes;
  return cleaned.split("|").map((cell) => cell.trim());
}

function isSeparatorRow(row: string): boolean {
  const cells = parseCells(row);
  if (cells.length === 0) return false;
  // Each cell in separator row should contain only dashes, colons, and spaces
  return cells.every((cell) => /^[:\-\s]+$/.test(cell) && cell.includes("-"));
}

// ─── Detection Functions ─────────────────────────────────────────────────────

/**
 * Detect a markdown table in the text.
 * A valid markdown table has a header row, a separator row (dashes/pipes),
 * and at least one data row.
 *
 * @returns Parsed table data or null if no table is detected
 */
export function detectMarkdownTable(text: string): TableData | null {
  if (!text || typeof text !== "string") return null;

  const lines = text.split("\n");

  // Find the start of a table: look for a line with pipes followed by separator
  for (let i = 0; i < lines.length - 2; i++) {
    const headerLine = lines[i].trim();
    const separatorLine = lines[i + 1]?.trim();

    // Header must contain at least one pipe
    if (!headerLine.includes("|")) continue;
    // Separator must be a valid separator row
    if (!separatorLine || !isSeparatorRow(separatorLine)) continue;

    const headers = parseCells(headerLine);
    const separatorCells = parseCells(separatorLine);

    // Column count must match between header and separator
    if (headers.length !== separatorCells.length) continue;
    // Enforce column limit
    if (headers.length > MAX_TABLE_COLUMNS) continue;
    // Headers should not be empty
    if (headers.length === 0 || headers.every((h) => h === "")) continue;

    // Collect data rows
    const rows: string[][] = [];
    for (let j = i + 2; j < lines.length && rows.length < MAX_TABLE_ROWS; j++) {
      const line = lines[j].trim();
      // Stop at empty line or non-table line
      if (!line || !line.includes("|")) break;
      const cells = parseCells(line);
      // Normalize row to have same number of columns as headers
      const normalizedRow = headers.map((_, idx) => cells[idx] ?? "");
      rows.push(normalizedRow);
    }

    // Must have at least one data row
    if (rows.length === 0) continue;

    return { headers, rows };
  }

  return null;
}

/**
 * Detect numeric data with labels from text content.
 * Looks for patterns in markdown tables, key-value lists, or repeated
 * "label: number" patterns. Requires at least 2 data points.
 *
 * @returns Parsed numeric data or null if no pattern is detected
 */
export function detectNumericData(text: string): NumericData | null {
  if (!text || typeof text !== "string") return null;

  // Strategy 1: Try extracting from a markdown table
  const tableData = detectMarkdownTable(text);
  if (tableData) {
    const numericFromTable = extractNumericFromTable(tableData);
    if (numericFromTable) return numericFromTable;
  }

  // Strategy 2: Try "label: number" patterns (key-value pairs)
  const kvResult = extractKeyValuePairs(text);
  if (kvResult) return kvResult;

  // Strategy 3: Try list-style "- label: number" or "* label: number"
  const listKvResult = extractListKeyValues(text);
  if (listKvResult) return listKvResult;

  return null;
}

function extractNumericFromTable(table: TableData): NumericData | null {
  // Look for a column that contains numeric values and use
  // another column (preferably the first) as labels
  if (table.headers.length < 2 || table.rows.length < 2) return null;

  // Try each column pair: first non-numeric as label, first numeric as value
  let labelColIdx = -1;
  let valueColIdx = -1;

  for (let col = 0; col < table.headers.length; col++) {
    const allNumeric = table.rows.every((row) => {
      const cell = (row[col] || "").replace(/^Rp\.?\s*/, "");
      return isNumericString(cell);
    });
    if (allNumeric && valueColIdx === -1) {
      valueColIdx = col;
    } else if (!allNumeric && labelColIdx === -1) {
      labelColIdx = col;
    }
    if (labelColIdx !== -1 && valueColIdx !== -1) break;
  }

  if (labelColIdx === -1 || valueColIdx === -1) return null;

  const labels: string[] = [];
  const values: number[] = [];

  for (const row of table.rows.slice(0, MAX_DATA_POINTS)) {
    const label = row[labelColIdx];
    const rawValue = (row[valueColIdx] || "").replace(/^Rp\.?\s*/, "");
    const value = parseNumericValue(rawValue);
    if (label && value !== null) {
      labels.push(label);
      values.push(value);
    }
  }

  if (labels.length < 2) return null;
  return { labels, values };
}

function extractKeyValuePairs(text: string): NumericData | null {
  // Match patterns like "Label: 123" or "Label: 1,234.56" or "Label: 45%" or "Label: Rp 111,000"
  const pattern = /^(.+?):\s*(?:Rp\.?\s*)?([\d,.]+)\s*%?\s*$/gm;
  const labels: string[] = [];
  const values: number[] = [];

  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null && labels.length < MAX_DATA_POINTS) {
    const label = match[1].trim();
    const value = parseNumericValue(match[2]);
    if (label && value !== null && value > 0) {
      labels.push(label);
      values.push(value);
    }
  }

  if (labels.length < 2) return null;
  return { labels, values };
}

function extractListKeyValues(text: string): NumericData | null {
  // Match patterns like "- Label: 123" or "* Label: 42" or "- Label: Rp 3,345.10"
  const pattern = /^[\s]*[-*]\s+(.+?):\s*(?:Rp\.?\s*)?([\d,.]+)\s*%?\s*$/gm;
  const labels: string[] = [];
  const values: number[] = [];

  let match: RegExpExecArray | null;
  while ((match = pattern.exec(text)) !== null && labels.length < MAX_DATA_POINTS) {
    const label = match[1].trim();
    const value = parseNumericValue(match[2]);
    if (label && value !== null && value > 0) {
      labels.push(label);
      values.push(value);
    }
  }

  if (labels.length >= 2) return { labels, values };

  // Strategy 3b: Try numbered list "1. Label ... number" patterns
  const numberedPattern = /^\s*\d+\.\s+(.+?)\s*[-–:]\s*(?:Rp\.?\s*)?([\d,.]+)\s*$/gm;
  const labels2: string[] = [];
  const values2: number[] = [];

  let match2: RegExpExecArray | null;
  while ((match2 = numberedPattern.exec(text)) !== null && labels2.length < MAX_DATA_POINTS) {
    const label = match2[1].trim();
    const value = parseNumericValue(match2[2]);
    if (label && value !== null && value > 0) {
      labels2.push(label);
      values2.push(value);
    }
  }

  if (labels2.length < 2) return null;
  return { labels: labels2, values: values2 };
}

function isNumericString(str: string): boolean {
  if (!str || str.trim() === "") return false;
  // Also treat Rp-prefixed values as numeric
  const cleaned = str.trim().replace(/^Rp\.?\s*/, "");
  return parseNumericValue(cleaned) !== null;
}

function parseNumericValue(str: string): number | null {
  if (!str || str.trim() === "") return null;
  // Remove percentage signs and trim
  let cleaned = str.trim().replace(/%$/, "");
  
  // Handle Indonesian number format: 111.000 (dot as thousands separator)
  // If string has dots but no comma, and dots are at 3-digit intervals, treat as thousand separator
  if (cleaned.includes(".") && !cleaned.includes(",")) {
    const parts = cleaned.split(".");
    const allThreeDigits = parts.slice(1).every(p => p.length === 3);
    if (parts.length > 1 && allThreeDigits) {
      // It's a thousands-separated number (e.g., 111.000 → 111000)
      cleaned = cleaned.replace(/\./g, "");
    }
  }
  // Handle format like 3,345.10 (comma as thousands, dot as decimal)
  else if (cleaned.includes(",") && cleaned.includes(".")) {
    const lastDot = cleaned.lastIndexOf(".");
    const lastComma = cleaned.lastIndexOf(",");
    if (lastDot > lastComma) {
      // Standard format: 3,345.10 → remove commas
      cleaned = cleaned.replace(/,/g, "");
    } else {
      // European format: 3.345,10 → swap separators
      cleaned = cleaned.replace(/\./g, "").replace(",", ".");
    }
  }
  // Handle comma-only (could be thousands: 111,000 or decimal: 3,5)
  else if (cleaned.includes(",")) {
    const parts = cleaned.split(",");
    if (parts.length === 2 && parts[1].length === 3) {
      // Likely thousands separator: 111,000 → 111000
      cleaned = cleaned.replace(/,/g, "");
    } else {
      // Likely decimal: 3,5 → 3.5
      cleaned = cleaned.replace(",", ".");
    }
  }

  const num = Number(cleaned);
  return isNaN(num) ? null : num;
}

/**
 * Detect bulleted or numbered lists in text.
 * Recognizes lines starting with "- ", "* ", or "1. " patterns.
 * Supports up to 4 nesting levels based on indentation.
 *
 * @returns Parsed list data or null if no list is detected
 */
export function detectList(text: string): ListData | null {
  if (!text || typeof text !== "string") return null;

  const lines = text.split("\n");
  const items: ListItem[] = [];

  // Patterns for list item detection
  const unorderedPattern = /^(\s*)([-*])\s+(.+)$/;
  const orderedPattern = /^(\s*)(\d+)\.\s+(.+)$/;

  for (const line of lines) {
    if (items.length >= MAX_DATA_POINTS) break;

    const unorderedMatch = line.match(unorderedPattern);
    const orderedMatch = line.match(orderedPattern);

    if (unorderedMatch) {
      const indent = unorderedMatch[1].length;
      const level = Math.min(Math.floor(indent / 2), MAX_NESTING_LEVELS - 1);
      items.push({
        content: unorderedMatch[3].trim(),
        level,
        ordered: false,
      });
    } else if (orderedMatch) {
      const indent = orderedMatch[1].length;
      const level = Math.min(Math.floor(indent / 2), MAX_NESTING_LEVELS - 1);
      items.push({
        content: orderedMatch[3].trim(),
        level,
        ordered: true,
      });
    }
  }

  // Must have at least one list item to be considered a list
  if (items.length === 0) return null;

  return { items };
}
