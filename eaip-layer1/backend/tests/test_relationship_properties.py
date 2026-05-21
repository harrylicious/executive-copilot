"""Property-based tests for relationship extraction constraints.

Property 12: Relationships connect co-occurring entities with valid fields

For any extracted relationship, both the source and target entities SHALL have been
extracted from the same chunk, the description SHALL be at most 256 characters, and
the strength score SHALL be in the range [0.0, 1.0].

**Validates: Requirements 5.1, 5.2**
"""

import hypothesis.strategies as st
from hypothesis import given, settings, assume

from app.services.entity_extractor import ExtractedEntity, EntityExtractor
from app.services.relationship_extractor import RelationshipExtractor


# Load the entity extractor once at module level to avoid repeated model loading
_ENTITY_EXTRACTOR = EntityExtractor(method="rule-based")
_RELATIONSHIP_EXTRACTOR = RelationshipExtractor()


# Strategy for generating chunk IDs
chunk_ids = st.integers(min_value=1, max_value=100000)

# Strategy for generating realistic text chunks that are likely to contain
# multiple named entities (people, organizations, locations) for relationship extraction
_ENTITY_RICH_SENTENCES = [
    "Alice Johnson met Bob Smith at the Microsoft headquarters in Seattle.",
    "The United Nations held a conference in New York with representatives from Google and Amazon.",
    "Dr. Sarah Chen published a paper with Professor James Wilson at Stanford University.",
    "Apple CEO Tim Cook announced a partnership with IBM in San Francisco.",
    "Barack Obama visited Angela Merkel in Berlin to discuss NATO policies.",
    "Tesla and SpaceX founder Elon Musk spoke at the World Economic Forum in Davos.",
    "The European Union signed a trade agreement with Japan in Brussels.",
    "Mark Zuckerberg and Sheryl Sandberg presented Meta's new strategy in Menlo Park.",
    "Amazon Web Services expanded operations in London and Tokyo last quarter.",
    "The World Health Organization collaborated with Pfizer and Moderna on vaccine distribution.",
    "John Smith from Goldman Sachs met with Jane Doe from JPMorgan in Chicago.",
    "Netflix CEO Reed Hastings discussed content strategy with Disney executives in Los Angeles.",
    "The Federal Reserve chairman Jerome Powell addressed Congress in Washington.",
    "Samsung and LG competed for market share in South Korea and China.",
    "Professor Maria Garcia from MIT collaborated with Oxford University researchers.",
]

entity_rich_text = st.sampled_from(_ENTITY_RICH_SENTENCES)

# Strategy for combining multiple sentences to create richer chunks
multi_sentence_text = st.lists(
    entity_rich_text,
    min_size=1,
    max_size=4,
).map(lambda sentences: " ".join(sentences))


class TestProperty12RelationshipConstraints:
    """Property 12: Relationships connect co-occurring entities with valid fields.

    **Validates: Requirements 5.1, 5.2**
    """

    @given(text=multi_sentence_text, chunk_id=chunk_ids)
    @settings(max_examples=50, deadline=60000)
    def test_relationships_connect_entities_from_same_chunk(
        self, text: str, chunk_id: int
    ):
        """Both source and target entities of any relationship SHALL have been
        extracted from the same chunk.

        **Validates: Requirements 5.1**
        """
        # Extract entities from the chunk
        entities = _ENTITY_EXTRACTOR.extract(text, chunk_id)
        assume(len(entities) >= 2)

        # Extract relationships from the same entities and chunk
        relationships = _RELATIONSHIP_EXTRACTOR.extract(entities, text, chunk_id)
        assume(len(relationships) > 0)

        # Collect all entity names extracted from this chunk
        entity_names_in_chunk = {e.name for e in entities}
        entity_normalized_names_in_chunk = {e.normalized_name for e in entities}

        for rel in relationships:
            # Both source and target must be entities from the same chunk
            source_found = (
                rel.source_entity_name in entity_names_in_chunk
                or rel.source_entity_name.lower().strip() in entity_normalized_names_in_chunk
            )
            target_found = (
                rel.target_entity_name in entity_names_in_chunk
                or rel.target_entity_name.lower().strip() in entity_normalized_names_in_chunk
            )
            assert source_found, (
                f"Relationship source entity '{rel.source_entity_name}' was not "
                f"extracted from chunk {chunk_id}. "
                f"Entities in chunk: {entity_names_in_chunk}"
            )
            assert target_found, (
                f"Relationship target entity '{rel.target_entity_name}' was not "
                f"extracted from chunk {chunk_id}. "
                f"Entities in chunk: {entity_names_in_chunk}"
            )

            # Both source and target should reference the same chunk
            assert rel.source_chunk_id == chunk_id, (
                f"Relationship source_chunk_id {rel.source_chunk_id} does not "
                f"match the chunk {chunk_id} from which entities were extracted"
            )

    @given(text=multi_sentence_text, chunk_id=chunk_ids)
    @settings(max_examples=50, deadline=60000)
    def test_relationship_description_at_most_256_characters(
        self, text: str, chunk_id: int
    ):
        """The relationship description SHALL be at most 256 characters.

        **Validates: Requirements 5.2**
        """
        entities = _ENTITY_EXTRACTOR.extract(text, chunk_id)
        assume(len(entities) >= 2)

        relationships = _RELATIONSHIP_EXTRACTOR.extract(entities, text, chunk_id)
        assume(len(relationships) > 0)

        for rel in relationships:
            assert len(rel.description) <= 256, (
                f"Relationship description exceeds 256 characters "
                f"(length={len(rel.description)}): '{rel.description[:100]}...'"
            )

    @given(text=multi_sentence_text, chunk_id=chunk_ids)
    @settings(max_examples=50, deadline=60000)
    def test_relationship_strength_in_valid_range(
        self, text: str, chunk_id: int
    ):
        """The strength score SHALL be in the range [0.0, 1.0].

        **Validates: Requirements 5.2**
        """
        entities = _ENTITY_EXTRACTOR.extract(text, chunk_id)
        assume(len(entities) >= 2)

        relationships = _RELATIONSHIP_EXTRACTOR.extract(entities, text, chunk_id)
        assume(len(relationships) > 0)

        for rel in relationships:
            assert 0.0 <= rel.strength <= 1.0, (
                f"Relationship strength {rel.strength} is outside valid range "
                f"[0.0, 1.0] for relationship between "
                f"'{rel.source_entity_name}' and '{rel.target_entity_name}'"
            )

    @given(text=multi_sentence_text, chunk_id=chunk_ids)
    @settings(max_examples=50, deadline=60000)
    def test_all_relationship_constraints_hold_together(
        self, text: str, chunk_id: int
    ):
        """Combined property: all relationship constraints hold simultaneously.

        For any extracted relationship:
        - Both source and target entities were extracted from the same chunk
        - Description is at most 256 characters
        - Strength score is in [0.0, 1.0]

        **Validates: Requirements 5.1, 5.2**
        """
        entities = _ENTITY_EXTRACTOR.extract(text, chunk_id)
        assume(len(entities) >= 2)

        relationships = _RELATIONSHIP_EXTRACTOR.extract(entities, text, chunk_id)
        assume(len(relationships) > 0)

        entity_names_in_chunk = {e.name for e in entities}

        for rel in relationships:
            # Co-occurrence constraint
            assert rel.source_entity_name in entity_names_in_chunk, (
                f"Source entity '{rel.source_entity_name}' not in chunk entities"
            )
            assert rel.target_entity_name in entity_names_in_chunk, (
                f"Target entity '{rel.target_entity_name}' not in chunk entities"
            )

            # Description length constraint
            assert len(rel.description) <= 256, (
                f"Description length {len(rel.description)} exceeds 256 chars"
            )

            # Strength range constraint
            assert 0.0 <= rel.strength <= 1.0, (
                f"Strength {rel.strength} outside [0.0, 1.0]"
            )

            # Chunk ID consistency
            assert rel.source_chunk_id == chunk_id, (
                f"source_chunk_id {rel.source_chunk_id} != expected {chunk_id}"
            )
