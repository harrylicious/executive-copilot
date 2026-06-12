"""Unit tests for the ExcelLoader service."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from app.services.excel_loader import ExcelLoader


@pytest.fixture
def loader():
    return ExcelLoader()


@pytest.fixture
def sample_excel(tmp_path):
    """Create a sample Excel file with one sheet containing data."""
    file_path = tmp_path / "test_data.xlsx"
    df = pd.DataFrame({
        "Nama": ["Budi", "Ani"],
        "Usia": [30, 25],
        "Kota": ["Jakarta", "Bandung"],
    })
    df.to_excel(file_path, index=False, sheet_name="Sheet1")
    return file_path


@pytest.fixture
def multi_sheet_excel(tmp_path):
    """Create an Excel file with multiple sheets."""
    file_path = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
        pd.DataFrame({
            "Produk": ["Mie", "Roti"],
            "Harga": [5000, 3000],
        }).to_excel(writer, index=False, sheet_name="Produk")
        pd.DataFrame({
            "Outlet": ["Toko A", "Toko B"],
            "Alamat": ["Jl. Merdeka", "Jl. Sudirman"],
        }).to_excel(writer, index=False, sheet_name="Outlet")
    return file_path


class TestExcelLoaderLoad:
    """Tests for ExcelLoader.load method."""

    def test_load_single_sheet(self, loader, sample_excel):
        """Each sheet produces one Document."""
        docs = loader.load(sample_excel)
        assert len(docs) == 1
        assert docs[0].metadata["sheet_name"] == "Sheet1"
        assert docs[0].metadata["source"] == str(sample_excel)
        assert docs[0].metadata["filename"] == "test_data.xlsx"

    def test_load_multi_sheet(self, loader, multi_sheet_excel):
        """Multiple non-empty sheets produce multiple Documents."""
        docs = loader.load(multi_sheet_excel)
        assert len(docs) == 2
        sheet_names = {d.metadata["sheet_name"] for d in docs}
        assert sheet_names == {"Produk", "Outlet"}

    def test_load_corrupted_file(self, loader, tmp_path):
        """Corrupted/unreadable files produce no Documents."""
        bad_file = tmp_path / "corrupted.xlsx"
        bad_file.write_bytes(b"this is not an excel file")
        docs = loader.load(bad_file)
        assert docs == []

    def test_load_nonexistent_file(self, loader, tmp_path):
        """Non-existent files produce no Documents."""
        docs = loader.load(tmp_path / "does_not_exist.xlsx")
        assert docs == []

    def test_load_empty_sheet_skipped(self, loader, tmp_path):
        """Sheets with only a header and no data rows are skipped."""
        file_path = tmp_path / "empty_data.xlsx"
        # Write a sheet with only headers (no data rows)
        df = pd.DataFrame(columns=["Kolom1", "Kolom2"])
        df.to_excel(file_path, index=False, sheet_name="EmptySheet")
        docs = loader.load(file_path)
        assert docs == []


class TestExcelLoaderFormatRow:
    """Tests for ExcelLoader._format_row method."""

    def test_format_row_basic(self, loader):
        """Row is formatted as 'Col: Val | Col: Val'."""
        row = pd.Series(["Budi", "30", "Jakarta"])
        columns = ["Nama", "Usia", "Kota"]
        result = loader._format_row(row, columns)
        assert result == "Nama: Budi | Usia: 30 | Kota: Jakarta"

    def test_format_row_omits_nan(self, loader):
        """NaN values are omitted from formatted output."""
        row = pd.Series(["Budi", None, "Jakarta"])
        columns = ["Nama", "Usia", "Kota"]
        result = loader._format_row(row, columns)
        assert result == "Nama: Budi | Kota: Jakarta"

    def test_format_row_omits_empty_string(self, loader):
        """Empty string values are omitted from formatted output."""
        row = pd.Series(["Budi", "", "Jakarta"])
        columns = ["Nama", "Usia", "Kota"]
        result = loader._format_row(row, columns)
        assert result == "Nama: Budi | Kota: Jakarta"

    def test_format_row_omits_whitespace_only(self, loader):
        """Whitespace-only values are omitted."""
        row = pd.Series(["Budi", "   ", "Jakarta"])
        columns = ["Nama", "Usia", "Kota"]
        result = loader._format_row(row, columns)
        assert result == "Nama: Budi | Kota: Jakarta"


class TestExcelLoaderProcessSheet:
    """Tests for ExcelLoader._process_sheet method."""

    def test_process_sheet_row_format(self, loader, sample_excel):
        """Page content contains correctly formatted rows."""
        docs = loader.load(sample_excel)
        content = docs[0].page_content
        lines = content.split("\n")
        assert len(lines) == 2
        assert "Nama: Budi" in lines[0]
        assert "Usia: 30" in lines[0]
        assert "Kota: Jakarta" in lines[0]
        assert "Nama: Ani" in lines[1]

    def test_process_sheet_uses_first_nonempty_row_as_header(self, loader, tmp_path):
        """First non-empty row is used as column headers."""
        file_path = tmp_path / "header_test.xlsx"
        # Create DataFrame with an empty first row, then headers, then data
        df = pd.DataFrame([
            [None, None, None],
            ["Nama", "Usia", "Kota"],
            ["Budi", "30", "Jakarta"],
        ])
        df.to_excel(file_path, index=False, header=False, sheet_name="Sheet1")
        docs = loader.load(file_path)
        assert len(docs) == 1
        assert "Nama: Budi" in docs[0].page_content

    def test_process_sheet_all_nan_rows_skipped(self, loader, tmp_path):
        """Sheets where all data rows are NaN/empty produce no Document."""
        file_path = tmp_path / "nan_rows.xlsx"
        # Header row followed by rows with only NaN values
        df = pd.DataFrame([
            ["Kolom1", "Kolom2"],
            [None, None],
            [None, None],
        ])
        df.to_excel(file_path, index=False, header=False, sheet_name="Sheet1")
        docs = loader.load(file_path)
        assert docs == []
