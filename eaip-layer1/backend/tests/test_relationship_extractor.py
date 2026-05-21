"""Unit tests for the RelationshipExtractor service."""

import pytest

from app.services.entity_extractor import ExtractedEntity
from app.services.relationship_extractor import (
    ExtractedRelationship,
    RelationshipExtractor,
)


@pytest.fixture
def extractor():
    """Create a RelationshipExtractor instance."""
    return RelationshipExtractor()


def _make_entity(
    name: str,
    entity_type: str = "person",
    chunk_id: int = 1,
    description: str = "",
) -> ExtractedEntity:
    """Helper to create an ExtractedEntity for testing."""
    return ExtractedEntity(
        name=name,
        normalized_name=name.lower().strip(),
        entity_type=entity_type,
        description=description,
        source_chunk_id=chunk_id,
    )


class TestExtractedRelationshipDataclass:
    """Tests for the ExtractedRelationship dataclass."""

    def test_creates_relationship(self):
        """Should create an ExtractedRelationship with all fields."""
        rel = ExtractedRelationship(
            source_entity_name="Alice",
            target_entity_name="Bob",
            description="Alice works with Bob",
            strength=0.8,
            source_chunk_id=1,
        )
        assert rel.source_entity_name == "Alice"
        assert rel.target_entity_name == "Bob"
        assert rel.description == "Alice works with Bob"
        assert rel.strength == 0.8
        assert rel.source_chunk_id == 1

    def test_strength_boundaries(self):
        """Should accept strength at boundaries 0.0 and 1.0."""
        rel_min = ExtractedRelationship(
            source_entity_name="A",
            target_entity_name="B",
            description="test",
            strength=0.0,
            source_chunk_id=1,
        )
        rel_max = ExtractedRelationship(
            source_entity_name="A",
            target_entity_name="B",
            description="test",
            strength=1.0,
            source_chunk_id=1,
        )
        assert rel_min.strength == 0.0
        assert rel_max.strength == 1.0


class TestRelationshipExtractorExtract:
    """Tests for RelationshipExtractor.extract method."""

    def test_empty_entities_returns_empty(self, extractor):
        """Should return empty list when no entities provided."""
        result = extractor.extract([], "some text", chunk_id=1)
        assert result == []

    def test_single_entity_returns_empty(self, extractor):
        """Should return empty list when only one entity provided."""
        entities = [_make_entity("Alice")]
        result = extractor.extract(entities, "Alice is here", chunk_id=1)
        assert result == []

    def test_two_entities_produces_one_relationship(self, extractor):
        """Should produce exactly one relationship for two entities."""
        entities = [_make_entity("Alice"), _make_entity("Bob")]
        text = "Alice met Bob at the conference."
        result = extractor.extract(entities, text, chunk_id=1)
        assert len(result) == 1
        assert result[0].source_entity_name == "Alice"
        assert result[0].target_entity_name == "Bob"
        assert result[0].source_chunk_id == 1

    def test_three_entities_produces_three_relationships(self, extractor):
        """Should produce C(3,2)=3 relationships for three entities."""
        entities = [
            _make_entity("Alice"),
            _make_entity("Bob"),
            _make_entity("Charlie"),
        ]
        text = "Alice, Bob, and Charlie work together on the project."
        result = extractor.extract(entities, text, chunk_id=5)
        assert len(result) == 3
        # All should reference the same chunk
        for rel in result:
            assert rel.source_chunk_id == 5

    def test_strength_in_valid_range(self, extractor):
        """Should produce strength scores between 0.0 and 1.0."""
        entities = [_make_entity("Alice"), _make_entity("Bob")]
        text = "Alice and Bob are colleagues."
        result = extractor.extract(entities, text, chunk_id=1)
        assert len(result) == 1
        assert 0.0 <= result[0].strength <= 1.0

    def test_description_max_256_chars(self, extractor):
        """Should limit description to 256 characters."""
        # Create entities with long names that appear far apart in text
        long_name_a = "A" * 100
        long_name_b = "B" * 100
        entities = [
            _make_entity(long_name_a),
            _make_entity(long_name_b),
        ]
        # Create text with entities far apart
        text = f"{long_name_a} {'x' * 200} {long_name_b}"
        result = extractor.extract(entities, text, chunk_id=1)
        assert len(result) == 1
        assert len(result[0].description) <= 256

    def test_closer_entities_have_higher_strength(self, extractor):
        """Entities closer together should have higher strength than distant ones."""
        entity_a = _make_entity("Alice")
        entity_b = _make_entity("Bob")
        entity_c = _make_entity("Charlie")

        # Text where Alice and Bob are close, Charlie is far
        text = "Alice and Bob went to the store. " + "x " * 50 + "Charlie arrived later."
        entities = [entity_a, entity_b, entity_c]
        result = extractor.extract(entities, text, chunk_id=1)

        # Find the Alice-Bob and Alice-Charlie relationships
        alice_bob = None
        alice_charlie = None
        for rel in result:
            if (
                rel.source_entity_name == "Alice"
                and rel.target_entity_name == "Bob"
            ):
                alice_bob = rel
            elif (
                rel.source_entity_name == "Alice"
                and rel.target_entity_name == "Charlie"
            ):
                alice_charlie = rel

        assert alice_bob is not None
        assert alice_charlie is not None
        assert alice_bob.strength > alice_charlie.strength

    def test_duplicate_entities_deduplicated(self, extractor):
        """Should deduplicate entities by normalized name before pairing."""
        entities = [
            _make_entity("Alice"),
            _make_entity("alice"),  # duplicate (same normalized name)
            _make_entity("Bob"),
        ]
        text = "Alice and Bob are friends."
        result = extractor.extract(entities, text, chunk_id=1)
        # Should only produce 1 relationship (Alice-Bob), not 3
        assert len(result) == 1

    def test_entities_not_in_text_get_default_strength(self, extractor):
        """Entities not found in text should get default strength of 0.5."""
        entities = [
            _make_entity("EntityX"),
            _make_entity("EntityY"),
        ]
        # Text that doesn't contain the entity names
        text = "This text has no matching entity names at all."
        result = extractor.extract(entities, text, chunk_id=1)
        assert len(result) == 1
        assert result[0].strength == 0.5

    def test_description_contains_entity_names(self, extractor):
        """Description should reference both entity names."""
        entities = [_make_entity("Alice"), _make_entity("Bob")]
        text = "Alice met Bob at the conference."
        result = extractor.extract(entities, text, chunk_id=1)
        assert "Alice" in result[0].description
        assert "Bob" in result[0].description

    def test_chunk_id_propagated(self, extractor):
        """Should propagate the chunk_id to all relationships."""
        entities = [_make_entity("Alice"), _make_entity("Bob")]
        text = "Alice and Bob."
        result = extractor.extract(entities, text, chunk_id=42)
        assert all(rel.source_chunk_id == 42 for rel in result)
