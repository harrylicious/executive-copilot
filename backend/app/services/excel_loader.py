"""Excel file loader that produces structured Documents with column-value pairs per row.

Reads .xlsx/.xls files using pandas, converts each non-empty sheet into a
LangChain Document with rows formatted as 'KolomA: nilaiA | KolomB: nilaiB'.
"""

import logging
from pathlib import Path

import pandas as pd
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class ExcelLoader:
    """Loads Excel files into structured Documents with column-value pairs per row.

    Each non-empty sheet becomes one Document. Rows are formatted with column
    headers and values separated by pipes. Empty/NaN columns are omitted per row.
    """

    def load(self, file_path: Path) -> list[Document]:
        """Load an Excel file and return one Document per non-empty sheet.

        Args:
            file_path: Path to the .xlsx or .xls file.

        Returns:
            List of Documents, one per non-empty sheet. Returns an empty list
            if the file cannot be read or contains no non-empty sheets.
        """
        try:
            sheets = pd.read_excel(
                file_path,
                sheet_name=None,
                header=None,
                dtype=str,
                engine=None,
            )
        except Exception as e:
            logger.warning(
                f"Skipping unreadable Excel file '{file_path}': {e}"
            )
            return []

        documents: list[Document] = []
        for sheet_name, df in sheets.items():
            doc = self._process_sheet(df, str(sheet_name), file_path)
            if doc is not None:
                documents.append(doc)

        return documents

    def _process_sheet(
        self, df: pd.DataFrame, sheet_name: str, file_path: Path
    ) -> Document | None:
        """Convert a DataFrame to a Document with structured row format.

        Uses a heuristic to find the actual header row: the first row where
        multiple columns have short non-empty string values (typical column
        headers). Skips title rows that only have one or two non-empty cells.

        Args:
            df: Raw DataFrame (read without header inference).
            sheet_name: Name of the sheet in the Excel file.
            file_path: Path to the source file.

        Returns:
            A Document with formatted page_content and metadata, or None if
            the sheet has no data rows after the header.
        """
        if df.empty:
            return None

        # Find the header row: look for the first row with multiple non-empty
        # short values (column names are typically short strings).
        # Skip rows that look like titles (single cell or very few cells filled).
        header_idx = None
        num_cols = len(df.columns)
        min_filled_ratio = 0.4  # At least 40% of columns should be filled

        for idx in range(len(df)):
            row = df.iloc[idx]
            non_empty_values = [
                str(v).strip() for v in row
                if pd.notna(v) and str(v).strip()
            ]
            filled_count = len(non_empty_values)

            # A header row should have multiple filled columns
            if filled_count < 2:
                continue

            # Check if this looks like a header: multiple short strings,
            # filling a reasonable fraction of columns
            if filled_count >= num_cols * min_filled_ratio:
                # Additionally skip "data type" rows (all values are type names)
                type_names = {"text", "whole number", "decimal number", "date", "boolean", "number", "integer", "float", "string"}
                lower_values = {v.lower() for v in non_empty_values}
                if lower_values.issubset(type_names):
                    continue
                header_idx = idx
                break

        if header_idx is None:
            # Fallback: use the first non-empty row (original behavior)
            for idx in range(len(df)):
                row = df.iloc[idx]
                if row.notna().any() and any(
                    str(v).strip() for v in row if pd.notna(v)
                ):
                    header_idx = idx
                    break

        if header_idx is None:
            return None

        # Extract column headers from the first non-empty row
        header_row = df.iloc[header_idx]
        columns = [
            str(v).strip() if pd.notna(v) else ""
            for v in header_row
        ]

        # Get data rows (everything after the header row)
        data_df = df.iloc[header_idx + 1:]

        if data_df.empty:
            return None

        # Format each non-empty data row
        formatted_rows: list[str] = []
        for _, row in data_df.iterrows():
            # Check if this row has at least one non-empty value
            has_data = False
            for val in row:
                if pd.notna(val) and str(val).strip():
                    has_data = True
                    break

            if not has_data:
                continue

            formatted = self._format_row(row, columns)
            if formatted:
                formatted_rows.append(formatted)

        # Skip sheets with only headers and zero non-empty data rows
        if not formatted_rows:
            return None

        page_content = "\n".join(formatted_rows)

        return Document(
            page_content=page_content,
            metadata={
                "sheet_name": sheet_name,
                "source": str(file_path),
                "filename": file_path.name,
            },
        )

    def _format_row(self, row: pd.Series, columns: list[str]) -> str:
        """Format a single row as 'KolomA: nilaiA | KolomB: nilaiB'.

        Omits columns whose cell value is empty or NaN for that row.

        Args:
            row: A pandas Series representing one data row.
            columns: List of column header strings.

        Returns:
            Formatted string with pipe-separated column-value pairs.
        """
        parts: list[str] = []
        for col_name, value in zip(columns, row):
            if pd.notna(value) and str(value).strip():
                # Only include columns that have a non-empty header
                if col_name:
                    parts.append(f"{col_name}: {str(value).strip()}")

        return " | ".join(parts)
