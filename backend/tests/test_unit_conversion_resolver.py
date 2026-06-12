"""Unit tests for UnitConversionResolver implementation."""

import pytest

from app.services.ingestion.unit_conversion_resolver import (
    ConversionEdge,
    UnitConversionResolver,
)


class TestResolveValidHierarchy:
    """Tests for resolve() with valid 3-level unit hierarchies."""

    def test_creates_two_edges_for_valid_hierarchy(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD001")
        assert len(edges) == 2

    def test_first_edge_is_satb_to_satt(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD001")
        assert edges[0].from_unit == "CS"
        assert edges[0].to_unit == "PAK"
        assert edges[0].conversion_factor == 12

    def test_second_edge_is_satt_to_satk(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD001")
        assert edges[1].from_unit == "PAK"
        assert edges[1].to_unit == "BTL"
        assert edges[1].conversion_factor == 6

    def test_edges_have_correct_product_key(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD001")
        assert all(e.product_key == "PRD001" for e in edges)

    def test_float_conversion_factors(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 2.5,
            "SatT": "PAK",
            "Berisi2": 3.0,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD002")
        assert edges[0].conversion_factor == 2.5
        assert edges[1].conversion_factor == 3.0


class TestResolveSingleUnitProduct:
    """Tests for resolve() with single-unit products."""

    def test_all_units_identical_factors_one_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 1,
            "SatT": "CS",
            "Berisi2": 1,
            "SatK": "CS",
        }
        edges = resolver.resolve(row, "PRD003")
        assert edges == []

    def test_all_units_identical_factor_not_one_creates_edges(self):
        """If units are identical but factors != 1, still create edges."""
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 2,
            "SatT": "CS",
            "Berisi2": 1,
            "SatK": "CS",
        }
        edges = resolver.resolve(row, "PRD004")
        assert len(edges) == 2

    def test_is_single_unit_product_true(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "BTL",
            "Berisi1": 1,
            "SatT": "BTL",
            "Berisi2": 1,
            "SatK": "BTL",
        }
        assert resolver.is_single_unit_product(row) is True

    def test_is_single_unit_product_false_different_units(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        assert resolver.is_single_unit_product(row) is False


class TestResolveMissingFields:
    """Tests for resolve() with missing/empty unit fields."""

    def test_missing_satb_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD005")
        assert edges == []

    def test_missing_satt_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD006")
        assert edges == []

    def test_missing_satk_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
        }
        edges = resolver.resolve(row, "PRD007")
        assert edges == []

    def test_none_satb_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": None,
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD008")
        assert edges == []

    def test_empty_string_satb_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD009")
        assert edges == []

    def test_whitespace_only_unit_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "  ",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD010")
        assert edges == []


class TestResolveInvalidFactors:
    """Tests for resolve() with invalid conversion factors."""

    def test_zero_berisi1_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 0,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD011")
        assert edges == []

    def test_negative_berisi1_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": -5,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD012")
        assert edges == []

    def test_zero_berisi2_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": 0,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD013")
        assert edges == []

    def test_negative_berisi2_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": -3,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD014")
        assert edges == []

    def test_none_berisi1_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": None,
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD015")
        assert edges == []

    def test_none_berisi2_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": 12,
            "SatT": "PAK",
            "Berisi2": None,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD016")
        assert edges == []

    def test_non_numeric_berisi1_returns_empty(self):
        resolver = UnitConversionResolver()
        row = {
            "SatB": "CS",
            "Berisi1": "abc",
            "SatT": "PAK",
            "Berisi2": 6,
            "SatK": "BTL",
        }
        edges = resolver.resolve(row, "PRD017")
        assert edges == []


class TestComputeEquivalent:
    """Tests for compute_equivalent() quantity conversion."""

    def setup_method(self):
        self.resolver = UnitConversionResolver()
        self.edges = [
            ConversionEdge("PRD001", "CS", "PAK", 12),
            ConversionEdge("PRD001", "PAK", "BTL", 6),
        ]

    def test_same_unit_returns_quantity(self):
        result = self.resolver.compute_equivalent(5.0, "CS", "CS", self.edges)
        assert result == 5.0

    def test_forward_one_level(self):
        """1 CS = 12 PAK"""
        result = self.resolver.compute_equivalent(1.0, "CS", "PAK", self.edges)
        assert result == 12.0

    def test_forward_two_levels(self):
        """1 CS = 12 PAK = 72 BTL"""
        result = self.resolver.compute_equivalent(1.0, "CS", "BTL", self.edges)
        assert result == 72.0

    def test_reverse_one_level(self):
        """12 PAK = 1 CS"""
        result = self.resolver.compute_equivalent(12.0, "PAK", "CS", self.edges)
        assert result == 1.0

    def test_reverse_two_levels(self):
        """72 BTL = 1 CS"""
        result = self.resolver.compute_equivalent(72.0, "BTL", "CS", self.edges)
        assert result == 1.0

    def test_middle_to_small(self):
        """1 PAK = 6 BTL"""
        result = self.resolver.compute_equivalent(1.0, "PAK", "BTL", self.edges)
        assert result == 6.0

    def test_small_to_middle(self):
        """6 BTL = 1 PAK"""
        result = self.resolver.compute_equivalent(6.0, "BTL", "PAK", self.edges)
        assert result == 1.0

    def test_no_path_returns_none(self):
        result = self.resolver.compute_equivalent(1.0, "CS", "KG", self.edges)
        assert result is None

    def test_empty_edges_returns_none(self):
        result = self.resolver.compute_equivalent(1.0, "CS", "PAK", [])
        assert result is None

    def test_round_trip_forward_and_back(self):
        """Converting forward then back should return original quantity."""
        forward = self.resolver.compute_equivalent(5.0, "CS", "BTL", self.edges)
        back = self.resolver.compute_equivalent(forward, "BTL", "CS", self.edges)
        assert abs(back - 5.0) < 1e-9

    def test_fractional_quantity(self):
        """2.5 CS = 30 PAK"""
        result = self.resolver.compute_equivalent(2.5, "CS", "PAK", self.edges)
        assert result == 30.0
