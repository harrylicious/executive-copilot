"""Schema registry for known sheet types with validation support."""

from dataclasses import dataclass, field
from typing import Any

from app.services.ingestion.structured_data_extractor import ParsedSheet


@dataclass
class ColumnDefinition:
    """Schema definition for a single column."""

    name: str
    required: bool
    data_type: str  # "string" | "numeric" | "date"


@dataclass
class SheetSchema:
    """Complete schema for a known sheet type."""

    sheet_name: str
    columns: list[ColumnDefinition]
    primary_key: str
    foreign_keys: dict[str, str] = field(default_factory=dict)  # {column_name: "target_sheet.target_column"}
    data_category: str = "master"  # "master" | "transactional"


@dataclass
class ValidationResult:
    """Result of schema validation."""

    is_valid: bool
    missing_columns: list[str] = field(default_factory=list)
    type_mismatches: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class SchemaRegistry:
    """Stores and validates schemas for known sheet types."""

    def __init__(self) -> None:
        self._schemas: dict[str, SheetSchema] = self._load_default_schemas()

    def get_schema(self, sheet_name: str) -> SheetSchema | None:
        """Look up schema by case-insensitive exact match.

        Returns the SheetSchema if found, or None if no schema matches.
        """
        return self._schemas.get(sheet_name.lower())

    def validate(self, parsed_sheet: ParsedSheet) -> ValidationResult:
        """Validate a parsed sheet against its registered schema.

        - Look up schema by sheet name (case-insensitive)
        - If no schema found, return valid result with no issues
        - Check required column presence (case-insensitive comparison)
        - Check data type conformance for each column
        - Return ValidationResult with missing columns, type mismatches, warnings
        """
        schema = self.get_schema(parsed_sheet.sheet_name)

        # Unregistered sheets pass validation without checks
        if schema is None:
            return ValidationResult(is_valid=True)

        # Build a lowercase set of headers present in the parsed sheet
        headers_lower = {h.lower() for h in parsed_sheet.headers}

        # Check required column presence (case-insensitive)
        missing_columns: list[str] = []
        for col_def in schema.columns:
            if col_def.required and col_def.name.lower() not in headers_lower:
                missing_columns.append(col_def.name)

        # Check data type conformance for columns that are present
        type_mismatches: list[dict[str, Any]] = []
        warnings: list[str] = []

        # Build a mapping from lowercase header to actual header for lookup
        header_lower_to_actual: dict[str, str] = {}
        for h in parsed_sheet.headers:
            header_lower_to_actual[h.lower()] = h

        for col_def in schema.columns:
            actual_header = header_lower_to_actual.get(col_def.name.lower())
            if actual_header is None:
                # Column not present, skip type check
                continue

            # Get the inferred data type for this column
            actual_type = parsed_sheet.data_types.get(actual_header)
            if actual_type is None:
                continue

            if actual_type != col_def.data_type:
                type_mismatches.append({
                    "column": col_def.name,
                    "expected": col_def.data_type,
                    "actual": actual_type,
                })
                warnings.append(
                    f"Column '{col_def.name}' expected type '{col_def.data_type}' "
                    f"but found '{actual_type}'"
                )

        # Add warnings for missing required columns
        for col_name in missing_columns:
            warnings.append(f"Required column '{col_name}' is missing")

        # is_valid is True only if no required columns are missing
        is_valid = len(missing_columns) == 0

        return ValidationResult(
            is_valid=is_valid,
            missing_columns=missing_columns,
            type_mismatches=type_mismatches,
            warnings=warnings,
        )

    def _load_default_schemas(self) -> dict[str, SheetSchema]:
        """Load built-in schemas for MBarang, MPD, MOutlet, SO, Jual, Beli, Stok."""
        return {
            "mbarang": SheetSchema(
                sheet_name="MBarang",
                columns=[
                    ColumnDefinition("ID", required=True, data_type="string"),
                    ColumnDefinition("Nama", required=True, data_type="string"),
                    ColumnDefinition("HargaJual", required=False, data_type="numeric"),
                    ColumnDefinition("VendorCode", required=False, data_type="string"),
                    ColumnDefinition("SatB", required=False, data_type="string"),
                    ColumnDefinition("Berisi1", required=False, data_type="numeric"),
                    ColumnDefinition("SatT", required=False, data_type="string"),
                    ColumnDefinition("Berisi2", required=False, data_type="numeric"),
                    ColumnDefinition("SatK", required=False, data_type="string"),
                    ColumnDefinition("Lebar", required=False, data_type="numeric"),
                    ColumnDefinition("Tinggi", required=False, data_type="numeric"),
                    ColumnDefinition("Berat", required=False, data_type="numeric"),
                    ColumnDefinition("Panjang", required=False, data_type="numeric"),
                    ColumnDefinition("Company", required=False, data_type="string"),
                ],
                primary_key="ID",
                foreign_keys={},
                data_category="master",
            ),
            "mpd": SheetSchema(
                sheet_name="MPD",
                columns=[
                    ColumnDefinition("suplcode", required=True, data_type="string"),
                    ColumnDefinition("suplname", required=True, data_type="string"),
                    ColumnDefinition("address", required=False, data_type="string"),
                    ColumnDefinition("city", required=False, data_type="string"),
                    ColumnDefinition("email", required=False, data_type="string"),
                    ColumnDefinition("blocked", required=False, data_type="string"),
                ],
                primary_key="suplcode",
                foreign_keys={},
                data_category="master",
            ),
            "moutlet": SheetSchema(
                sheet_name="MOutlet",
                columns=[
                    ColumnDefinition("custcode", required=True, data_type="string"),
                    ColumnDefinition("custname", required=True, data_type="string"),
                    ColumnDefinition("outlettype", required=False, data_type="string"),
                    ColumnDefinition("address", required=False, data_type="string"),
                    ColumnDefinition("area", required=False, data_type="string"),
                    ColumnDefinition("contactperson", required=False, data_type="string"),
                ],
                primary_key="custcode",
                foreign_keys={},
                data_category="master",
            ),
            "so": SheetSchema(
                sheet_name="SO",
                columns=[
                    ColumnDefinition("SO_No", required=True, data_type="string"),
                    ColumnDefinition("Outlet_ID", required=True, data_type="string"),
                    ColumnDefinition("SKU_ID", required=True, data_type="string"),
                    ColumnDefinition("PraSO_Code", required=False, data_type="string"),
                    ColumnDefinition("PraSO_Date", required=False, data_type="date"),
                    ColumnDefinition("SO_Date", required=False, data_type="date"),
                    ColumnDefinition("Status", required=False, data_type="string"),
                ],
                primary_key="SO_No",
                foreign_keys={"Outlet_ID": "MOutlet.custcode", "SKU_ID": "MBarang.ID"},
                data_category="transactional",
            ),
            "jual": SheetSchema(
                sheet_name="Jual",
                columns=[
                    ColumnDefinition("Invoice_No", required=True, data_type="string"),
                    ColumnDefinition("Outlet_ID", required=True, data_type="string"),
                    ColumnDefinition("SKU", required=True, data_type="string"),
                    ColumnDefinition("Sales_ID", required=False, data_type="string"),
                    ColumnDefinition("PrincID", required=False, data_type="string"),
                    ColumnDefinition("PraSO_Ref", required=False, data_type="string"),
                    ColumnDefinition("Qty", required=False, data_type="numeric"),
                    ColumnDefinition("Amount", required=False, data_type="numeric"),
                ],
                primary_key="Invoice_No",
                foreign_keys={
                    "Outlet_ID": "MOutlet.custcode",
                    "SKU": "MBarang.ID",
                    "Sales_ID": "Salesman.id",
                    "PrincID": "MPD.suplcode",
                },
                data_category="transactional",
            ),
            "beli": SheetSchema(
                sheet_name="Beli",
                columns=[
                    ColumnDefinition("PO_No", required=True, data_type="string"),
                    ColumnDefinition("Principal", required=True, data_type="string"),
                    ColumnDefinition("SKU", required=True, data_type="string"),
                    ColumnDefinition("Qty", required=False, data_type="numeric"),
                    ColumnDefinition("Amount", required=False, data_type="numeric"),
                ],
                primary_key="PO_No",
                foreign_keys={"Principal": "MPD.suplcode", "SKU": "MBarang.ID"},
                data_category="transactional",
            ),
            "stok": SheetSchema(
                sheet_name="Stok",
                columns=[
                    ColumnDefinition("Itemcode", required=True, data_type="string"),
                    ColumnDefinition("Qty", required=False, data_type="numeric"),
                    ColumnDefinition("Timestamp", required=False, data_type="date"),
                ],
                primary_key="Itemcode",
                foreign_keys={"Itemcode": "MBarang.ID"},
                data_category="transactional",
            ),
        }
