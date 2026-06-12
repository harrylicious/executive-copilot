"""Unit tests for SchemaRegistry.validate() method."""

import pytest

from app.services.ingestion.schema_registry import SchemaRegistry, ValidationResult
from app.services.ingestion.structured_data_extractor import ParsedSheet


@pytest.fixture
def registry():
    """Create a fresh SchemaRegistry instance."""
    return SchemaRegistry()


class TestSchemaRegistryValidate:
    """Tests for SchemaRegistry.validate()."""

    def test_unregistered_sheet_passes_validation(self, registry):
        """Unregistered sheet names should return valid result with no issues."""
        sheet = ParsedSheet(
            sheet_name="UnknownSheet",
            headers=["A", "B", "C"],
            rows=[{"A": "x", "B": "y", "C": "z"}],
            row_count=1,
            data_types={"A": "string", "B": "string", "C": "string"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is True
        assert result.missing_columns == []
        assert result.type_mismatches == []
        assert result.warnings == []

    def test_all_required_columns_present(self, registry):
        """Sheet with all required columns present should be valid."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["ID", "Nama", "HargaJual"],
            rows=[{"ID": "P001", "Nama": "Product", "HargaJual": 100}],
            row_count=1,
            data_types={"ID": "string", "Nama": "string", "HargaJual": "numeric"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is True
        assert result.missing_columns == []

    def test_missing_required_column(self, registry):
        """Sheet missing a required column should be invalid."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["Nama", "HargaJual"],
            rows=[{"Nama": "Product", "HargaJual": 100}],
            row_count=1,
            data_types={"Nama": "string", "HargaJual": "numeric"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is False
        assert "ID" in result.missing_columns

    def test_missing_multiple_required_columns(self, registry):
        """Sheet missing multiple required columns lists all of them."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["HargaJual"],
            rows=[{"HargaJual": 100}],
            row_count=1,
            data_types={"HargaJual": "numeric"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is False
        assert "ID" in result.missing_columns
        assert "Nama" in result.missing_columns
        assert len(result.missing_columns) == 2

    def test_case_insensitive_column_matching(self, registry):
        """Column presence check should be case-insensitive."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["id", "nama", "hargajual"],
            rows=[{"id": "P001", "nama": "Product", "hargajual": 100}],
            row_count=1,
            data_types={"id": "string", "nama": "string", "hargajual": "numeric"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is True
        assert result.missing_columns == []

    def test_case_insensitive_sheet_name_lookup(self, registry):
        """Schema lookup should be case-insensitive for sheet names."""
        sheet = ParsedSheet(
            sheet_name="MBARANG",
            headers=["ID", "Nama"],
            rows=[{"ID": "P001", "Nama": "Product"}],
            row_count=1,
            data_types={"ID": "string", "Nama": "string"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is True

    def test_type_mismatch_detected(self, registry):
        """Type mismatches should be reported in validation result."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["ID", "Nama", "HargaJual"],
            rows=[{"ID": "P001", "Nama": "Product", "HargaJual": "not_a_number"}],
            row_count=1,
            data_types={"ID": "string", "Nama": "string", "HargaJual": "string"},
        )
        result = registry.validate(sheet)
        # HargaJual expected numeric but got string
        assert len(result.type_mismatches) == 1
        assert result.type_mismatches[0]["column"] == "HargaJual"
        assert result.type_mismatches[0]["expected"] == "numeric"
        assert result.type_mismatches[0]["actual"] == "string"

    def test_type_mismatch_preserves_raw_values(self, registry):
        """Type mismatches should not modify the parsed sheet data."""
        original_rows = [{"ID": "P001", "Nama": "Product", "HargaJual": "not_a_number"}]
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["ID", "Nama", "HargaJual"],
            rows=original_rows,
            row_count=1,
            data_types={"ID": "string", "Nama": "string", "HargaJual": "string"},
        )
        registry.validate(sheet)
        # Raw values should be preserved unchanged
        assert sheet.rows[0]["HargaJual"] == "not_a_number"

    def test_type_mismatch_does_not_affect_validity(self, registry):
        """Type mismatches alone should not make the result invalid."""
        sheet = ParsedSheet(
            sheet_name="MBarang",
            headers=["ID", "Nama", "HargaJual"],
            rows=[{"ID": "P001", "Nama": "Product", "HargaJual": "text"}],
            row_count=1,
            data_types={"ID": "string", "Nama": "string", "HargaJual": "string"},
        )
        result = registry.validate(sheet)
        # All required columns present, so valid despite type mismatch
        assert result.is_valid is True
        assert len(result.type_mismatches) == 1

    def test_warnings_for_missing_columns(self, registry):
        """Missing required columns should generate warnings."""
        sheet = ParsedSheet(
            sheet_name="MPD",
            headers=["suplname"],
            rows=[{"suplname": "Supplier A"}],
            row_count=1,
            data_types={"suplname": "string"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is False
        assert "suplcode" in result.missing_columns
        # Should have a warning about the missing column
        assert any("suplcode" in w for w in result.warnings)

    def test_partial_ingestion_with_missing_columns(self, registry):
        """Validation should support partial ingestion when required columns are missing."""
        sheet = ParsedSheet(
            sheet_name="SO",
            headers=["SO_No", "Outlet_ID"],  # Missing SKU_ID
            rows=[{"SO_No": "SO001", "Outlet_ID": "OUT001"}],
            row_count=1,
            data_types={"SO_No": "string", "Outlet_ID": "string"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is False
        assert "SKU_ID" in result.missing_columns
        # The result still contains type_mismatches list (empty) - partial ingestion proceeds
        assert isinstance(result.type_mismatches, list)

    def test_all_schemas_validate_correctly(self, registry):
        """All registered schemas should validate correctly with proper data."""
        test_cases = [
            ("MBarang", ["ID", "Nama"], {"ID": "string", "Nama": "string"}),
            ("MPD", ["suplcode", "suplname"], {"suplcode": "string", "suplname": "string"}),
            ("MOutlet", ["custcode", "custname"], {"custcode": "string", "custname": "string"}),
            ("SO", ["SO_No", "Outlet_ID", "SKU_ID"], {"SO_No": "string", "Outlet_ID": "string", "SKU_ID": "string"}),
            ("Jual", ["Invoice_No", "Outlet_ID", "SKU"], {"Invoice_No": "string", "Outlet_ID": "string", "SKU": "string"}),
            ("Beli", ["PO_No", "Principal", "SKU"], {"PO_No": "string", "Principal": "string", "SKU": "string"}),
            ("Stok", ["Itemcode"], {"Itemcode": "string"}),
        ]
        for sheet_name, headers, data_types in test_cases:
            rows = [{h: f"val_{h}" for h in headers}]
            sheet = ParsedSheet(
                sheet_name=sheet_name,
                headers=headers,
                rows=rows,
                row_count=1,
                data_types=data_types,
            )
            result = registry.validate(sheet)
            assert result.is_valid is True, f"Failed for {sheet_name}"

    def test_mixed_case_headers_match(self, registry):
        """Headers with mixed case should still match schema columns."""
        sheet = ParsedSheet(
            sheet_name="Jual",
            headers=["INVOICE_NO", "outlet_id", "Sku"],
            rows=[{"INVOICE_NO": "INV001", "outlet_id": "OUT001", "Sku": "SKU001"}],
            row_count=1,
            data_types={"INVOICE_NO": "string", "outlet_id": "string", "Sku": "string"},
        )
        result = registry.validate(sheet)
        assert result.is_valid is True
        assert result.missing_columns == []
