"""Unit tests for SchemaRegistry implementation."""

import pytest

from app.services.ingestion.schema_registry import (
    ColumnDefinition,
    SchemaRegistry,
    SheetSchema,
)


class TestSchemaRegistryInit:
    """Tests for SchemaRegistry initialization and schema loading."""

    def test_registry_loads_all_seven_schemas(self):
        registry = SchemaRegistry()
        expected_keys = {"mbarang", "mpd", "moutlet", "so", "jual", "beli", "stok"}
        assert set(registry._schemas.keys()) == expected_keys

    def test_all_schemas_are_sheet_schema_instances(self):
        registry = SchemaRegistry()
        for schema in registry._schemas.values():
            assert isinstance(schema, SheetSchema)

    def test_master_schemas_have_correct_category(self):
        registry = SchemaRegistry()
        for name in ("mbarang", "mpd", "moutlet"):
            assert registry._schemas[name].data_category == "master"

    def test_transactional_schemas_have_correct_category(self):
        registry = SchemaRegistry()
        for name in ("so", "jual", "beli", "stok"):
            assert registry._schemas[name].data_category == "transactional"


class TestSchemaRegistryGetSchema:
    """Tests for get_schema() case-insensitive exact matching."""

    def test_exact_lowercase_match(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("mbarang")
        assert schema is not None
        assert schema.sheet_name == "MBarang"

    def test_exact_uppercase_match(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBARANG")
        assert schema is not None
        assert schema.sheet_name == "MBarang"

    def test_mixed_case_match(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBarang")
        assert schema is not None
        assert schema.sheet_name == "MBarang"

    def test_unregistered_sheet_returns_none(self):
        registry = SchemaRegistry()
        assert registry.get_schema("UnknownSheet") is None

    def test_empty_string_returns_none(self):
        registry = SchemaRegistry()
        assert registry.get_schema("") is None

    def test_partial_match_returns_none(self):
        registry = SchemaRegistry()
        # "mbar" is not an exact match for "mbarang"
        assert registry.get_schema("mbar") is None

    def test_all_registered_names_resolve(self):
        registry = SchemaRegistry()
        names = ["MBarang", "MPD", "MOutlet", "SO", "Jual", "Beli", "Stok"]
        for name in names:
            schema = registry.get_schema(name)
            assert schema is not None, f"Expected schema for '{name}' but got None"
            assert schema.sheet_name == name


class TestMBarangSchema:
    """Tests for MBarang schema definition."""

    def test_primary_key(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBarang")
        assert schema.primary_key == "ID"

    def test_required_columns(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBarang")
        required = [c.name for c in schema.columns if c.required]
        assert required == ["ID", "Nama"]

    def test_column_count(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBarang")
        assert len(schema.columns) == 14

    def test_no_foreign_keys(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("MBarang")
        assert schema.foreign_keys == {}


class TestSOSchema:
    """Tests for SO schema definition with foreign keys."""

    def test_primary_key(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("SO")
        assert schema.primary_key == "SO_No"

    def test_foreign_keys(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("SO")
        assert schema.foreign_keys == {
            "Outlet_ID": "MOutlet.custcode",
            "SKU_ID": "MBarang.ID",
        }

    def test_has_date_columns(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("SO")
        date_cols = [c.name for c in schema.columns if c.data_type == "date"]
        assert "PraSO_Date" in date_cols
        assert "SO_Date" in date_cols


class TestJualSchema:
    """Tests for Jual schema with multiple foreign keys."""

    def test_foreign_key_count(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("Jual")
        assert len(schema.foreign_keys) == 4

    def test_foreign_keys_targets(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("Jual")
        assert schema.foreign_keys["Outlet_ID"] == "MOutlet.custcode"
        assert schema.foreign_keys["SKU"] == "MBarang.ID"
        assert schema.foreign_keys["Sales_ID"] == "Salesman.id"
        assert schema.foreign_keys["PrincID"] == "MPD.suplcode"


class TestStokSchema:
    """Tests for Stok schema with self-referencing foreign key."""

    def test_foreign_key_references_mbarang(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("Stok")
        assert schema.foreign_keys == {"Itemcode": "MBarang.ID"}

    def test_primary_key_is_also_foreign_key(self):
        registry = SchemaRegistry()
        schema = registry.get_schema("Stok")
        assert schema.primary_key == "Itemcode"
        assert "Itemcode" in schema.foreign_keys
