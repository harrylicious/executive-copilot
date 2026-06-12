"""Business glossary annotation for coded field values."""

from dataclasses import dataclass
from typing import Any


@dataclass
class GlossaryEntry:
    """A business glossary definition."""

    code: str
    full_name: str
    language: str  # "id" (Indonesian) or "en" (English)


class BusinessGlossaryAnnotator:
    """Annotates entities and relationships with business glossary definitions."""

    GLOSSARY: dict[str, GlossaryEntry] = {
        "PraSO": GlossaryEntry("PraSO", "Pre-Sales Order", "en"),
        "SO": GlossaryEntry("SO", "Sales Order", "en"),
        "J": GlossaryEntry("J", "Jual (Sales)", "id"),
        "RJ": GlossaryEntry("RJ", "Retur Jual (Sales Return)", "id"),
        "NO-SO": GlossaryEntry("NO-SO", "Pre-Sales Order not converted to Sales Order", "en"),
        "SatB": GlossaryEntry("SatB", "Satuan Besar (Big Unit)", "id"),
        "SatT": GlossaryEntry("SatT", "Satuan Tengah (Medium Unit)", "id"),
        "SatK": GlossaryEntry("SatK", "Satuan Kecil (Small Unit)", "id"),
        "CS": GlossaryEntry("CS", "Case", "en"),
        "BTL": GlossaryEntry("BTL", "Bottle", "en"),
        "PPN": GlossaryEntry("PPN", "Pajak Pertambahan Nilai (Value Added Tax)", "id"),
        "DPP": GlossaryEntry("DPP", "Dasar Pengenaan Pajak (Tax Base)", "id"),
    }

    def annotate(self, record: dict[str, Any]) -> dict[str, dict]:
        """Return glossary annotations for all matching field values in a record.

        For each field in the record:
        - If the field value (as string) exactly matches a glossary key → include annotation
        - Annotation format: {field_name: {"code": ..., "full_name": ..., "language": ...}}
        - Non-matching values get no entry in the result dict

        Returns:
            dict mapping field names to their glossary annotation dicts
        """
        annotations: dict[str, dict] = {}
        for field_name, value in record.items():
            str_value = str(value) if value is not None else ""
            entry = self.GLOSSARY.get(str_value)
            if entry is not None:
                annotations[field_name] = {
                    "code": entry.code,
                    "full_name": entry.full_name,
                    "language": entry.language,
                }
        return annotations
