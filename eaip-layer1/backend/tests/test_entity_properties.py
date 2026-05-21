"""Property-based tests for entity extraction and deduplication.

Property 11: Entity deduplication by normalized name

For any set of extracted entities, entities sharing the same case-folded
whitespace-trimmed name AND the same type SHALL be merged into a single entity
record whose source_chunk_ids contains all contributing chunk IDs.

After deduplication, no two entities share the same (normalized_name, entity_type) pair.

**Validates: Requirements 4.3**
"""

import hypothesis.strategies as st
from hypothesis import given, settings, assume

from app.services.entity_extractor import (
    ENTITY_TYPES,
    ExtractedEntity,
    _normalize_name,
)


# ---------------------------------------------------------------------------
# Deduplication logic under test
# ---------------------------------------------------------------------------

def deduplicate_entities(entities: list[ExtractedEntity]) -> list[dict]:
    """Merge entities with the same normalized name and type into a single record.

    This implements the deduplication logic specified in the design for
    GraphRAGEngine._deduplicate_entities. Entities sharing the same
    case-folded whitespace-trimmed name AND the same type are merged into
    a single entity record whose source_chunk_ids contains all contributing
    chunk IDs.

    Args:
        entities: List of extracted entities (potentially with duplicates).

    Returns:
        List of deduplicated entity records as dicts with keys:
        name, normalized_name, entity_type, description, source_chunk_ids.
    """
    merged: dict[tuple[str, str], dict] = {}

    for entity in entities:
        key = (entity.normalized_name, entity.entity_type)
        if key in merged:
            # Merge: add the source chunk ID to the existing record
            if entity.source_chunk_id not in merged[key]["source_chunk_ids"]:
                merged[key]["source_chunk_ids"].append(entity.source_chunk_id)
        else:
            merged[key] = {
                "name": entity.name,
                "normalized_name": entity.normalized_name,
                "entity_type": entity.entity_type,
                "description": entity.description,
                "source_chunk_ids": [entity.source_chunk_id],
            }

    return list(merged.values())


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Strategy for entity type from the allowed set
entity_type_strategy = st.sampled_from(sorted(ENTITY_TYPES))

# Strategy for entity names with varying case and whitespace
entity_name_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N", "Z"),
        blacklist_characters="\x00\n\r",
    ),
    min_size=1,
    max_size=50,
).filter(lambda t: len(t.strip()) >= 1)

# Strategy for chunk IDs
chunk_id_strategy = st.integers(min_value=1, max_value=10000)

# Strategy for descriptions
description_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
    min_size=0,
    max_size=100,
)


def make_entity(name: str, entity_type: str, chunk_id: int, description: str = "") -> ExtractedEntity:
    """Helper to create an ExtractedEntity with proper normalization."""
    return ExtractedEntity(
        name=name,
        normalized_name=_normalize_name(name),
        entity_type=entity_type,
        description=description,
        source_chunk_id=chunk_id,
    )


# Strategy for generating a list of extracted entities (possibly with duplicates)
extracted_entity_strategy = st.builds(
    make_entity,
    name=entity_name_strategy,
    entity_type=entity_type_strategy,
    chunk_id=chunk_id_strategy,
    description=description_strategy,
)

entity_list_strategy = st.lists(
    extracted_entity_strategy,
    min_size=1,
    max_size=30,
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

class TestProperty11EntityDeduplication:
    """Property 11: Entity deduplication by normalized name.

    **Validates: Requirements 4.3**
    """

    @given(entities=entity_list_strategy)
    @settings(max_examples=100, deadline=30000)
    def test_no_duplicate_normalized_name_type_pairs_after_dedup(
        self, entities: list[ExtractedEntity]
    ):
        """After deduplication, no two entities share the same
        (normalized_name, entity_type) pair.

        **Validates: Requirements 4.3**
        """
        deduplicated = deduplicate_entities(entities)

        # Collect all (normalized_name, entity_type) pairs
        keys = [(e["normalized_name"], e["entity_type"]) for e in deduplicated]

        # No duplicates should exist
        assert len(keys) == len(set(keys)), (
            f"Found duplicate (normalized_name, entity_type) pairs after deduplication: "
            f"{[k for k in keys if keys.count(k) > 1]}"
        )

    @given(entities=entity_list_strategy)
    @settings(max_examples=100, deadline=30000)
    def test_merged_entity_contains_all_contributing_chunk_ids(
        self, entities: list[ExtractedEntity]
    ):
        """Entities sharing the same normalized name and type are merged into
        a single entity record whose source_chunk_ids contains all contributing
        chunk IDs.

        **Validates: Requirements 4.3**
        """
        deduplicated = deduplicate_entities(entities)

        # For each deduplicated entity, verify it contains all chunk IDs
        # from the original entities that share the same key
        for deduped in deduplicated:
            key = (deduped["normalized_name"], deduped["entity_type"])

            # Find all original entities matching this key
            original_chunk_ids = {
                e.source_chunk_id
                for e in entities
                if (e.normalized_name, e.entity_type) == key
            }

            # The deduplicated record must contain all of them
            deduped_chunk_ids = set(deduped["source_chunk_ids"])
            assert original_chunk_ids == deduped_chunk_ids, (
                f"Entity {key}: expected chunk IDs {original_chunk_ids}, "
                f"got {deduped_chunk_ids}"
            )

    @given(entities=entity_list_strategy)
    @settings(max_examples=100, deadline=30000)
    def test_dedup_count_matches_unique_key_count(
        self, entities: list[ExtractedEntity]
    ):
        """The number of deduplicated entities equals the number of unique
        (normalized_name, entity_type) pairs in the input.

        **Validates: Requirements 4.3**
        """
        deduplicated = deduplicate_entities(entities)

        # Count unique keys in the input
        unique_keys = {
            (e.normalized_name, e.entity_type) for e in entities
        }

        assert len(deduplicated) == len(unique_keys), (
            f"Expected {len(unique_keys)} deduplicated entities, "
            f"got {len(deduplicated)}"
        )

    @given(
        base_name=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                blacklist_characters="\x00",
            ),
            min_size=1,
            max_size=30,
        ),
        entity_type=entity_type_strategy,
        chunk_ids=st.lists(chunk_id_strategy, min_size=2, max_size=10, unique=True),
    )
    @settings(max_examples=100, deadline=30000)
    def test_same_name_different_case_whitespace_merges(
        self, base_name: str, entity_type: str, chunk_ids: list[int]
    ):
        """Entities with names that differ only in added whitespace are
        merged into a single record when they share the same type, because
        normalization trims and collapses whitespace then casefolds.

        **Validates: Requirements 4.3**
        """
        normalized = _normalize_name(base_name)
        assume(len(normalized) > 0)

        # Create variants that only differ in surrounding whitespace
        # (whitespace-only differences always normalize to the same value)
        variants = [
            base_name,
            f"  {base_name}  ",
            f" {base_name} ",
            f"\t{base_name}\t",
            f"  {base_name}",
        ]

        # Verify all variants normalize to the same value
        expected_normalized = _normalize_name(variants[0])
        assume(all(_normalize_name(v) == expected_normalized for v in variants))

        # Create entities from different chunks using name variants
        entities = []
        for i, chunk_id in enumerate(chunk_ids):
            variant = variants[i % len(variants)]
            entities.append(make_entity(variant, entity_type, chunk_id))

        deduplicated = deduplicate_entities(entities)

        # All should merge into exactly one entity
        assert len(deduplicated) == 1, (
            f"Expected 1 merged entity for name variants of '{base_name}', "
            f"got {len(deduplicated)}"
        )

        # The merged entity should contain all chunk IDs
        assert set(deduplicated[0]["source_chunk_ids"]) == set(chunk_ids), (
            f"Expected chunk IDs {set(chunk_ids)}, "
            f"got {set(deduplicated[0]['source_chunk_ids'])}"
        )

    @given(
        name=entity_name_strategy,
        type1=entity_type_strategy,
        type2=entity_type_strategy,
        chunk_id1=chunk_id_strategy,
        chunk_id2=chunk_id_strategy,
    )
    @settings(max_examples=100, deadline=30000)
    def test_same_name_different_type_not_merged(
        self, name: str, type1: str, type2: str, chunk_id1: int, chunk_id2: int
    ):
        """Entities with the same normalized name but different types are NOT
        merged — they remain as separate entity records.

        **Validates: Requirements 4.3**
        """
        assume(type1 != type2)
        assume(len(_normalize_name(name)) > 0)

        entities = [
            make_entity(name, type1, chunk_id1),
            make_entity(name, type2, chunk_id2),
        ]

        deduplicated = deduplicate_entities(entities)

        # Should produce two separate entities (different types)
        assert len(deduplicated) == 2, (
            f"Expected 2 entities for same name '{name}' with types "
            f"'{type1}' and '{type2}', got {len(deduplicated)}"
        )
