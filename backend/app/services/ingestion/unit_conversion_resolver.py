"""Multi-level unit conversion hierarchy resolution."""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ConversionEdge:
    """A unit conversion relationship."""

    product_key: str
    from_unit: str
    to_unit: str
    conversion_factor: float  # >= 1.0


class UnitConversionResolver:
    """Resolves multi-level unit conversion hierarchies from MBarang records."""

    def resolve(
        self, product_row: dict[str, Any], product_key: str
    ) -> list[ConversionEdge]:
        """Parse SatB/Berisi1/SatT/Berisi2/SatK fields into conversion edges.

        Returns:
        - Two edges [SatB→SatT, SatT→SatK] for valid 3-level hierarchies
        - Empty list if:
          - All units are identical with factors 1 (single-unit product)
          - Unit fields are missing/empty
          - Conversion factors are zero or negative
        """
        # Extract unit fields
        sat_b = product_row.get("SatB")
        sat_t = product_row.get("SatT")
        sat_k = product_row.get("SatK")
        berisi1 = product_row.get("Berisi1")
        berisi2 = product_row.get("Berisi2")

        # Check for missing/empty unit fields
        if not sat_b or not sat_t or not sat_k:
            logger.warning(
                "Product %s: missing or empty unit fields (SatB=%r, SatT=%r, SatK=%r)",
                product_key,
                sat_b,
                sat_t,
                sat_k,
            )
            return []

        # Ensure string values are non-empty after stripping
        sat_b = str(sat_b).strip()
        sat_t = str(sat_t).strip()
        sat_k = str(sat_k).strip()

        if not sat_b or not sat_t or not sat_k:
            logger.warning(
                "Product %s: unit fields are empty after stripping whitespace",
                product_key,
            )
            return []

        # Validate conversion factors
        if not self._is_valid_factor(berisi1) or not self._is_valid_factor(berisi2):
            logger.warning(
                "Product %s: invalid conversion factors (Berisi1=%r, Berisi2=%r)",
                product_key,
                berisi1,
                berisi2,
            )
            return []

        factor1 = float(berisi1)
        factor2 = float(berisi2)

        # Check for single-unit product (all units identical, factors = 1)
        if sat_b == sat_t == sat_k and factor1 == 1 and factor2 == 1:
            logger.info(
                "Product %s: single-unit product (%s), no conversion edges created",
                product_key,
                sat_b,
            )
            return []

        # Create two conversion edges for valid 3-level hierarchy
        edges = [
            ConversionEdge(
                product_key=product_key,
                from_unit=sat_b,
                to_unit=sat_t,
                conversion_factor=factor1,
            ),
            ConversionEdge(
                product_key=product_key,
                from_unit=sat_t,
                to_unit=sat_k,
                conversion_factor=factor2,
            ),
        ]

        return edges

    def compute_equivalent(
        self,
        quantity: float,
        from_unit: str,
        to_unit: str,
        edges: list[ConversionEdge],
    ) -> float | None:
        """Compute equivalent quantity at a different unit level by traversing edges.

        Returns None if no path exists between from_unit and to_unit.
        Supports both forward (multiply) and reverse (divide) traversal.
        """
        if from_unit == to_unit:
            return quantity

        # Build adjacency graph: {unit: [(neighbor_unit, factor_to_multiply)]}
        # Forward edge: from_unit → to_unit, multiply by factor
        # Reverse edge: to_unit → from_unit, divide by factor (multiply by 1/factor)
        graph: dict[str, list[tuple[str, float]]] = {}

        for edge in edges:
            # Forward direction: from_unit → to_unit (multiply by factor)
            if edge.from_unit not in graph:
                graph[edge.from_unit] = []
            graph[edge.from_unit].append((edge.to_unit, edge.conversion_factor))

            # Reverse direction: to_unit → from_unit (divide by factor)
            if edge.to_unit not in graph:
                graph[edge.to_unit] = []
            graph[edge.to_unit].append((edge.from_unit, 1.0 / edge.conversion_factor))

        # BFS to find path from from_unit to to_unit
        if from_unit not in graph:
            return None

        visited: set[str] = {from_unit}
        # Queue of (current_unit, accumulated_quantity)
        queue: list[tuple[str, float]] = [(from_unit, quantity)]

        while queue:
            current_unit, current_qty = queue.pop(0)

            if current_unit == to_unit:
                return current_qty

            for neighbor, factor in graph.get(current_unit, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_qty * factor))

        return None

    def is_single_unit_product(
        self, product_row: dict[str, Any]
    ) -> bool:
        """Check if a product uses only one packaging level.

        Returns True if all unit names are identical and all conversion factors equal 1.
        """
        sat_b = product_row.get("SatB")
        sat_t = product_row.get("SatT")
        sat_k = product_row.get("SatK")
        berisi1 = product_row.get("Berisi1")
        berisi2 = product_row.get("Berisi2")

        # Must have all unit fields present
        if not sat_b or not sat_t or not sat_k:
            return False

        sat_b = str(sat_b).strip()
        sat_t = str(sat_t).strip()
        sat_k = str(sat_k).strip()

        if not sat_b or not sat_t or not sat_k:
            return False

        # Must have valid factors
        if not self._is_valid_factor(berisi1) or not self._is_valid_factor(berisi2):
            return False

        factor1 = float(berisi1)
        factor2 = float(berisi2)

        return sat_b == sat_t == sat_k and factor1 == 1 and factor2 == 1

    @staticmethod
    def _is_valid_factor(value: Any) -> bool:
        """Check if a conversion factor is valid (numeric, positive)."""
        if value is None:
            return False
        try:
            factor = float(value)
        except (TypeError, ValueError):
            return False
        return factor > 0
