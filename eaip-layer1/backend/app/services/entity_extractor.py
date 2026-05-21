"""Entity extraction service using spaCy NER.

Extracts named entities from text chunks using rule-based NER (spaCy
en_core_web_sm model) and maps them to the allowed entity type set.
Normalizes entity names using case-folding and whitespace trimming.
"""

import logging
from dataclasses import dataclass

import spacy

logger = logging.getLogger(__name__)

# Allowed entity types for the knowledge graph
ENTITY_TYPES = {"person", "organization", "concept", "location", "event", "document"}

# Maximum number of entities to extract per chunk
MAX_ENTITIES_PER_CHUNK = 50

# Mapping from spaCy NER labels to our entity type set
SPACY_LABEL_MAP: dict[str, str] = {
    "PERSON": "person",
    "ORG": "organization",
    "GPE": "location",
    "LOC": "location",
    "EVENT": "event",
    "WORK_OF_ART": "document",
    "LAW": "document",
    "NORP": "concept",
    "FAC": "concept",
    "PRODUCT": "concept",
    "DATE": "concept",
    "TIME": "concept",
    "PERCENT": "concept",
    "MONEY": "concept",
    "QUANTITY": "concept",
    "ORDINAL": "concept",
    "CARDINAL": "concept",
    "LANGUAGE": "concept",
}


@dataclass
class ExtractedEntity:
    """An entity extracted from a text chunk.

    Attributes:
        name: The original entity name as found in text.
        normalized_name: Case-folded, whitespace-trimmed name for deduplication.
        entity_type: One of the allowed ENTITY_TYPES.
        description: Brief description of the entity in context.
        source_chunk_id: ID of the chunk this entity was extracted from.
    """

    name: str
    normalized_name: str
    entity_type: str
    description: str
    source_chunk_id: int


def _normalize_name(name: str) -> str:
    """Normalize an entity name using case-folding and whitespace trimming.

    Applies str.casefold() for locale-independent lowercase conversion
    and collapses/strips whitespace.

    Args:
        name: The raw entity name.

    Returns:
        Normalized name suitable for deduplication.
    """
    normalized = " ".join(name.split())
    return normalized.casefold()


def _map_spacy_label(label: str) -> str:
    """Map a spaCy NER label to our allowed entity type set.

    Args:
        label: The spaCy entity label (e.g., "PERSON", "ORG").

    Returns:
        One of the allowed ENTITY_TYPES. Defaults to "concept" for
        unmapped labels.
    """
    return SPACY_LABEL_MAP.get(label, "concept")



class EntityExtractor:
    """Extracts entities from text using rule-based or LLM-based methods.

    Currently supports rule-based extraction using spaCy's en_core_web_sm
    model. Entities are mapped to the allowed type set and normalized
    for deduplication.

    Args:
        method: Extraction method to use. Currently only "rule-based" is
            implemented.
    """

    def __init__(self, method: str = "rule-based"):
        self.method = method
        if method == "rule-based":
            try:
                self._nlp = spacy.load("en_core_web_sm")
            except OSError as e:
                logger.error(
                    f"Failed to load spaCy model 'en_core_web_sm': {e}. "
                    "Install it with: python -m spacy download en_core_web_sm"
                )
                raise

    def extract(self, chunk_text: str, chunk_id: int) -> list[ExtractedEntity]:
        """Extract entities from a text chunk.

        Extracts up to MAX_ENTITIES_PER_CHUNK (50) entities from the given
        text. Entities are deduplicated within the chunk by normalized name
        and type before the limit is applied.

        Args:
            chunk_text: The text content of the chunk to process.
            chunk_id: The database ID of the source chunk.

        Returns:
            List of ExtractedEntity instances, at most 50 per chunk.
            Returns an empty list if extraction fails or no entities found.
        """
        if not chunk_text or not chunk_text.strip():
            return []

        if self.method == "rule-based":
            return self._extract_rule_based(chunk_text, chunk_id)

        logger.warning(
            f"Unsupported extraction method '{self.method}', returning empty list"
        )
        return []


    def _extract_rule_based(
        self, chunk_text: str, chunk_id: int
    ) -> list[ExtractedEntity]:
        """Extract entities using spaCy NER pipeline.

        Processes the text through spaCy's NER, maps labels to our type set,
        normalizes names, and deduplicates within the chunk.

        Args:
            chunk_text: The text to extract entities from.
            chunk_id: The source chunk ID.

        Returns:
            List of deduplicated ExtractedEntity instances, limited to 50.
        """
        try:
            doc = self._nlp(chunk_text)
        except Exception as e:
            logger.error(f"spaCy NER failed for chunk {chunk_id}: {e}")
            return []

        # Track seen entities for within-chunk deduplication
        seen: dict[tuple[str, str], ExtractedEntity] = {}

        for ent in doc.ents:
            name = ent.text.strip()
            if not name:
                continue

            normalized_name = _normalize_name(name)
            if not normalized_name:
                continue

            entity_type = _map_spacy_label(ent.label_)

            # Deduplicate by (normalized_name, entity_type) within the chunk
            dedup_key = (normalized_name, entity_type)
            if dedup_key in seen:
                continue

            # Generate a contextual description
            description = self._generate_description(ent, entity_type)

            # Truncate name and description to schema limits
            truncated_name = name[:512]
            truncated_description = description[:2000]

            entity = ExtractedEntity(
                name=truncated_name,
                normalized_name=normalized_name[:512],
                entity_type=entity_type,
                description=truncated_description,
                source_chunk_id=chunk_id,
            )

            seen[dedup_key] = entity

            # Enforce the 50-entity limit
            if len(seen) >= MAX_ENTITIES_PER_CHUNK:
                break

        return list(seen.values())

    def _generate_description(self, ent, entity_type: str) -> str:
        """Generate a brief description for an extracted entity.

        Uses the sentence context around the entity to produce a description.

        Args:
            ent: The spaCy entity span.
            entity_type: The mapped entity type.

        Returns:
            A brief description string.
        """
        sent = ent.sent
        if sent:
            context = sent.text.strip()
            if len(context) > 200:
                context = context[:200] + "..."
            return f"{entity_type.capitalize()} '{ent.text}' mentioned in: {context}"

        return f"{entity_type.capitalize()} '{ent.text}'"
