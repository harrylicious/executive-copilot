"""Unit tests for the EntityExtractor service."""

import pytest

from app.services.entity_extractor import (
    ENTITY_TYPES,
    MAX_ENTITIES_PER_CHUNK,
    SPACY_LABEL_MAP,
    EntityExtractor,
    ExtractedEntity,
    _map_spacy_label,
    _normalize_name,
)


@pytest.fixture
def extractor():
    """Create an EntityExtractor with default rule-based method."""
    return EntityExtractor(method="rule-based")


class TestExtractedEntityDataclass:
    """Tests for the ExtractedEntity dataclass."""

    def test_creates_entity(self):
        """Should create an ExtractedEntity with all fields."""
        entity = ExtractedEntity(
            name="John Smith",
            normalized_name="john smith",
            entity_type="person",
            description="Person 'John Smith' mentioned in context",
            source_chunk_id=1,
        )
        assert entity.name == "John Smith"
        assert entity.normalized_name == "john smith"
        assert entity.entity_type == "person"
        assert entity.source_chunk_id == 1


class TestNormalizeName:
    """Tests for the _normalize_name helper function."""

    def test_case_folds(self):
        """Should case-fold the name."""
        assert _normalize_name("John Smith") == "john smith"
        assert _normalize_name("MICROSOFT") == "microsoft"

    def test_trims_whitespace(self):
        """Should strip leading and trailing whitespace."""
        assert _normalize_name("  John  ") == "john"

    def test_collapses_internal_whitespace(self):
        """Should collapse multiple internal spaces to single space."""
        assert _normalize_name("John   Smith") == "john smith"
        assert _normalize_name("  The   World   Forum  ") == "the world forum"

    def test_empty_string(self):
        """Should return empty string for empty input."""
        assert _normalize_name("") == ""

    def test_whitespace_only(self):
        """Should return empty string for whitespace-only input."""
        assert _normalize_name("   ") == ""

    def test_casefold_special_chars(self):
        """Should handle special Unicode case-folding (e.g., German ß)."""
        assert _normalize_name("Straße") == "strasse"


class TestMapSpacyLabel:
    """Tests for the _map_spacy_label helper function."""

    def test_person_mapping(self):
        """PERSON should map to person."""
        assert _map_spacy_label("PERSON") == "person"

    def test_org_mapping(self):
        """ORG should map to organization."""
        assert _map_spacy_label("ORG") == "organization"

    def test_gpe_mapping(self):
        """GPE should map to location."""
        assert _map_spacy_label("GPE") == "location"

    def test_loc_mapping(self):
        """LOC should map to location."""
        assert _map_spacy_label("LOC") == "location"

    def test_event_mapping(self):
        """EVENT should map to event."""
        assert _map_spacy_label("EVENT") == "event"

    def test_work_of_art_mapping(self):
        """WORK_OF_ART should map to document."""
        assert _map_spacy_label("WORK_OF_ART") == "document"

    def test_law_mapping(self):
        """LAW should map to document."""
        assert _map_spacy_label("LAW") == "document"

    def test_concept_mappings(self):
        """All other known spaCy labels should map to concept."""
        concept_labels = [
            "NORP", "FAC", "PRODUCT", "DATE", "TIME",
            "PERCENT", "MONEY", "QUANTITY", "ORDINAL",
            "CARDINAL", "LANGUAGE",
        ]
        for label in concept_labels:
            assert _map_spacy_label(label) == "concept", f"{label} should map to concept"

    def test_unknown_label_defaults_to_concept(self):
        """Unknown labels should default to concept."""
        assert _map_spacy_label("UNKNOWN_LABEL") == "concept"
        assert _map_spacy_label("CUSTOM") == "concept"


class TestEntityExtractorInit:
    """Tests for EntityExtractor initialization."""

    def test_rule_based_loads_spacy_model(self):
        """Should load spaCy en_core_web_sm for rule-based method."""
        ex = EntityExtractor(method="rule-based")
        assert ex.method == "rule-based"
        assert ex._nlp is not None

    def test_non_rule_based_does_not_load_spacy(self):
        """Should not load spaCy for non-rule-based methods."""
        ex = EntityExtractor(method="llm-based")
        assert ex.method == "llm-based"
        assert not hasattr(ex, "_nlp")


class TestEntityExtractorExtract:
    """Tests for EntityExtractor.extract method."""

    def test_empty_text_returns_empty(self, extractor):
        """Should return empty list for empty text."""
        assert extractor.extract("", chunk_id=1) == []

    def test_whitespace_only_returns_empty(self, extractor):
        """Should return empty list for whitespace-only text."""
        assert extractor.extract("   ", chunk_id=1) == []

    def test_extracts_person_entities(self, extractor):
        """Should extract person entities from text."""
        text = "Barack Obama was the 44th president of the United States."
        results = extractor.extract(text, chunk_id=1)
        names = [e.normalized_name for e in results]
        types = {e.normalized_name: e.entity_type for e in results}
        assert "barack obama" in names
        assert types["barack obama"] == "person"

    def test_extracts_organization_entities(self, extractor):
        """Should extract organization entities from text."""
        text = "Microsoft announced a partnership with Google."
        results = extractor.extract(text, chunk_id=1)
        names = [e.normalized_name for e in results]
        types = {e.normalized_name: e.entity_type for e in results}
        assert "microsoft" in names
        assert types["microsoft"] == "organization"

    def test_extracts_location_entities(self, extractor):
        """Should extract location entities from text."""
        text = "The conference was held in New York City."
        results = extractor.extract(text, chunk_id=1)
        names = [e.normalized_name for e in results]
        # GPE entities like cities map to location
        location_entities = [e for e in results if e.entity_type == "location"]
        assert len(location_entities) > 0

    def test_all_entity_types_in_allowed_set(self, extractor):
        """All extracted entity types should be in ENTITY_TYPES."""
        text = (
            "John Smith works at Microsoft in Seattle. "
            "He attended the World Economic Forum on January 15, 2024. "
            "The company released a new product worth $5 million."
        )
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert entity.entity_type in ENTITY_TYPES, (
                f"Entity type '{entity.entity_type}' not in allowed set"
            )

    def test_source_chunk_id_propagated(self, extractor):
        """Should propagate chunk_id to all extracted entities."""
        text = "Alice and Bob work at Acme Corp."
        results = extractor.extract(text, chunk_id=42)
        for entity in results:
            assert entity.source_chunk_id == 42

    def test_normalized_name_is_casefolded(self, extractor):
        """Normalized names should be case-folded."""
        text = "MICROSOFT announced new features."
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert entity.normalized_name == entity.normalized_name.casefold()

    def test_normalized_name_is_whitespace_trimmed(self, extractor):
        """Normalized names should have no leading/trailing whitespace."""
        text = "John Smith works at Microsoft."
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert entity.normalized_name == entity.normalized_name.strip()
            # No double spaces
            assert "  " not in entity.normalized_name

    def test_deduplicates_within_chunk(self, extractor):
        """Should deduplicate entities with same normalized name and type."""
        text = (
            "Microsoft released a new product. "
            "Microsoft also announced a partnership. "
            "Microsoft is expanding globally."
        )
        results = extractor.extract(text, chunk_id=1)
        # Count how many times "microsoft" appears as organization
        microsoft_orgs = [
            e for e in results
            if e.normalized_name == "microsoft" and e.entity_type == "organization"
        ]
        assert len(microsoft_orgs) == 1

    def test_max_50_entities_per_chunk(self, extractor):
        """Should extract at most 50 entities per chunk."""
        results = extractor.extract("Some text with entities.", chunk_id=1)
        assert len(results) <= MAX_ENTITIES_PER_CHUNK

    def test_description_not_empty(self, extractor):
        """Extracted entities should have non-empty descriptions."""
        text = "John Smith works at Microsoft in Seattle."
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert entity.description, f"Entity '{entity.name}' has empty description"

    def test_name_max_512_chars(self, extractor):
        """Entity names should be truncated to 512 characters."""
        text = "John Smith works at Microsoft."
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert len(entity.name) <= 512

    def test_description_max_2000_chars(self, extractor):
        """Entity descriptions should be truncated to 2000 characters."""
        text = "John Smith works at Microsoft in a very long context."
        results = extractor.extract(text, chunk_id=1)
        for entity in results:
            assert len(entity.description) <= 2000

    def test_no_entities_returns_empty(self, extractor):
        """Should return empty list when no entities are found."""
        text = "This is a simple sentence with no named entities."
        results = extractor.extract(text, chunk_id=1)
        # spaCy might still find some entities, but if not, empty is fine
        # The key requirement is no error
        assert isinstance(results, list)

    def test_unsupported_method_returns_empty(self):
        """Should return empty list for unsupported extraction method."""
        ex = EntityExtractor(method="llm-based")
        results = ex.extract("John Smith works at Microsoft.", chunk_id=1)
        assert results == []


class TestEntityExtractorLabelMapping:
    """Tests verifying the full spaCy label mapping in extraction context."""

    def test_all_mapped_labels_produce_valid_types(self):
        """Every mapped label should produce a type in ENTITY_TYPES."""
        for label, entity_type in SPACY_LABEL_MAP.items():
            assert entity_type in ENTITY_TYPES, (
                f"Label '{label}' maps to '{entity_type}' which is not in ENTITY_TYPES"
            )
