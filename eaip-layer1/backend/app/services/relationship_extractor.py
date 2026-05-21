"""Relationship extraction service for identifying relationships between entities.

Extracts relationships between entity pairs that co-occur within the same text chunk.
Generates relationship descriptions based on textual context and computes strength
scores based on entity proximity within the chunk text.
"""

import logging
from dataclasses import dataclass
from itertools import combinations

from app.services.entity_extractor import ExtractedEntity

logger = logging.getLogger(__name__)


@dataclass
class ExtractedRelationship:
    """A relationship extracted between two co-occurring entities.

    Attributes:
        source_entity_name: The name of the source entity.
        target_entity_name: The name of the target entity.
        description: A description of how the entities relate (max 256 chars).
        strength: Relationship strength score from 0.0 to 1.0.
        source_chunk_id: The chunk ID from which this relationship was extracted.
    """

    source_entity_name: str
    target_entity_name: str
    description: str
    strength: float  # 0.0 to 1.0
    source_chunk_id: int


class RelationshipExtractor:
    """Extracts relationships between entity pairs within text chunks.

    For each pair of entities co-occurring in the same chunk, generates a
    relationship with a description derived from the surrounding text context
    and a strength score based on proximity within the chunk.
    """

    def extract(
        self,
        entities: list[ExtractedEntity],
        chunk_text: str,
        chunk_id: int,
    ) -> list[ExtractedRelationship]:
        """Extract relationships between all entity pairs in a chunk.

        Generates one relationship per unique entity pair found in the chunk.
        Strength is computed based on proximity of entity mentions in the text.
        Descriptions are generated from the textual context between or around
        the entity mentions.

        Args:
            entities: List of entities extracted from this chunk.
            chunk_text: The full text of the chunk.
            chunk_id: The database ID of the chunk.

        Returns:
            List of extracted relationships between entity pairs.
        """
        if len(entities) < 2:
            return []

        # Deduplicate entities by normalized name to avoid duplicate pairs
        unique_entities = self._deduplicate_entities(entities)

        if len(unique_entities) < 2:
            return []

        relationships: list[ExtractedRelationship] = []
        chunk_text_lower = chunk_text.lower()

        for entity_a, entity_b in combinations(unique_entities, 2):
            strength = self._compute_strength(
                entity_a, entity_b, chunk_text_lower
            )
            description = self._generate_description(
                entity_a, entity_b, chunk_text
            )

            relationships.append(
                ExtractedRelationship(
                    source_entity_name=entity_a.name,
                    target_entity_name=entity_b.name,
                    description=description,
                    strength=strength,
                    source_chunk_id=chunk_id,
                )
            )

        return relationships

    def _deduplicate_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[ExtractedEntity]:
        """Remove duplicate entities by normalized name.

        Keeps the first occurrence of each unique normalized name.

        Args:
            entities: List of entities potentially containing duplicates.

        Returns:
            List of unique entities by normalized name.
        """
        seen: set[str] = set()
        unique: list[ExtractedEntity] = []
        for entity in entities:
            if entity.normalized_name not in seen:
                seen.add(entity.normalized_name)
                unique.append(entity)
        return unique

    def _compute_strength(
        self,
        entity_a: ExtractedEntity,
        entity_b: ExtractedEntity,
        chunk_text_lower: str,
    ) -> float:
        """Compute relationship strength based on entity proximity in text.

        Strength is inversely proportional to the distance between entity
        mentions in the chunk text. Closer entities get higher strength scores.
        If either entity is not found in the text, a default mid-range score
        is returned.

        Args:
            entity_a: First entity in the pair.
            entity_b: Second entity in the pair.
            chunk_text_lower: Lowercased chunk text for case-insensitive search.

        Returns:
            Strength score between 0.0 and 1.0.
        """
        pos_a = chunk_text_lower.find(entity_a.normalized_name)
        pos_b = chunk_text_lower.find(entity_b.normalized_name)

        # If either entity name is not found in text, return default strength
        if pos_a == -1 or pos_b == -1:
            return 0.5

        # Compute distance between entity mentions
        distance = abs(pos_a - pos_b)
        text_length = len(chunk_text_lower)

        if text_length == 0:
            return 0.5

        # Normalize distance to 0-1 range (closer = higher strength)
        # Use inverse proportion: strength = 1 - (distance / text_length)
        # Clamp to [0.1, 1.0] to ensure minimum strength for co-occurrence
        normalized_distance = distance / text_length
        strength = 1.0 - normalized_distance
        strength = max(0.1, min(1.0, strength))

        return round(strength, 3)

    def _generate_description(
        self,
        entity_a: ExtractedEntity,
        entity_b: ExtractedEntity,
        chunk_text: str,
    ) -> str:
        """Generate a relationship description from textual context.

        Extracts the text between or around the two entity mentions to form
        a concise description of their relationship. Falls back to a generic
        co-occurrence description if entities are not found in text.

        The description is limited to 256 characters.

        Args:
            entity_a: First entity in the pair.
            entity_b: Second entity in the pair.
            chunk_text: The original chunk text.

        Returns:
            Relationship description, at most 256 characters.
        """
        chunk_lower = chunk_text.lower()
        pos_a = chunk_lower.find(entity_a.normalized_name)
        pos_b = chunk_lower.find(entity_b.normalized_name)

        if pos_a == -1 or pos_b == -1:
            # Fallback: generic co-occurrence description
            description = (
                f"{entity_a.name} and {entity_b.name} co-occur in the same context"
            )
            return description[:256]

        # Extract text between the two entity mentions
        start = min(pos_a, pos_b)
        end = max(
            pos_a + len(entity_a.normalized_name),
            pos_b + len(entity_b.normalized_name),
        )

        # Include a small window around the mentions for context
        context_start = max(0, start - 20)
        context_end = min(len(chunk_text), end + 20)
        context_snippet = chunk_text[context_start:context_end].strip()

        if context_snippet:
            # Clean up the snippet: replace newlines with spaces
            context_snippet = " ".join(context_snippet.split())
            description = (
                f"{entity_a.name} and {entity_b.name} are related: "
                f"{context_snippet}"
            )
        else:
            description = (
                f"{entity_a.name} and {entity_b.name} co-occur in the same context"
            )

        # Enforce 256 character limit
        if len(description) > 256:
            description = description[:253] + "..."

        return description
