"""Classification of parsed sheets as master, transactional, or unregistered."""

from dataclasses import dataclass

from app.services.ingestion.schema_registry import SchemaRegistry, SheetSchema
from app.services.ingestion.structured_data_extractor import ParsedSheet


@dataclass
class ClassificationResult:
    """Classification output for a parsed sheet."""

    sheet_name: str
    category: str  # "master" | "transactional" | "unregistered"
    schema: SheetSchema | None


class MasterDataClassifier:
    """Classifies parsed sheets by their data category."""

    def __init__(self, schema_registry: SchemaRegistry) -> None:
        self._registry = schema_registry

    def classify(self, parsed_sheet: ParsedSheet) -> ClassificationResult:
        """Classify a sheet based on its schema registry entry.

        - Look up schema by sheet name (case-insensitive)
        - If found, return the data_category from the schema ("master" or "transactional")
        - If not found, return "unregistered"
        - Attach the schema (or None) to the result
        """
        schema = self._registry.get_schema(parsed_sheet.sheet_name)
        if schema is None:
            return ClassificationResult(
                sheet_name=parsed_sheet.sheet_name,
                category="unregistered",
                schema=None,
            )
        return ClassificationResult(
            sheet_name=parsed_sheet.sheet_name,
            category=schema.data_category,
            schema=schema,
        )
