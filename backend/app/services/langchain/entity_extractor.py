"""LLM-based entity extraction using LangChain structured output.

Extracts named entities from text chunks using an LLM via LangChain,
producing ExtractedEntity objects.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)

# Entity type constants
ENTITY_TYPES = {"person", "organization", "concept", "location", "event", "document"}
MAX_ENTITIES_PER_CHUNK = 50


@dataclass
class ExtractedEntity:
    """Represents an entity extracted from a text chunk."""

    name: str
    normalized_name: str
    entity_type: str
    description: str
    source_chunk_id: int


def _normalize_name(name: str) -> str:
    """Normalize entity name for deduplication."""
    return name.strip().lower()

_SYSTEM_PROMPT = """You are an entity extraction system. Extract named entities from the provided text.

Return a JSON array of entities. Each entity must have these fields:
- "name": The entity name as it appears in the text
- "entity_type": One of: person, organization, concept, location, event, document
- "description": A brief description of the entity based on the text context

Return ONLY a valid JSON array. Do not include any other text, markdown formatting, or explanation.

Example output:
[{"name": "John Smith", "entity_type": "person", "description": "CEO mentioned in quarterly report"}, {"name": "Acme Corp", "entity_type": "organization", "description": "Parent company discussed in merger context"}]

If no entities are found, return an empty array: []"""

_USER_PROMPT_TEMPLATE = """Extract all named entities from the following text:

{chunk_text}"""


class LLMEntityExtractor:
    """LLM-based entity extraction using LangChain structured output.

    Uses a configured LLM to extract entities from text chunks, producing
    ExtractedEntity objects compatible with the existing EntityExtractor
    interface.

    Args:
        llm: A LangChain BaseChatModel instance for entity extraction.
    """

    def __init__(self, llm: BaseChatModel) -> None:
        self.llm = llm

    def extract(self, chunk_text: str, chunk_id: int) -> list[ExtractedEntity]:
        """Extract entities from a text chunk using the LLM.

        Args:
            chunk_text: The text content of the chunk to process.
            chunk_id: The database ID of the source chunk.

        Returns:
            List of ExtractedEntity instances, at most 50 per chunk.
            Returns an empty list if chunk is empty, extraction fails,
            or no valid entities are found.
        """
        if not chunk_text or not chunk_text.strip():
            return []

        try:
            messages = [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(
                    content=_USER_PROMPT_TEMPLATE.format(chunk_text=chunk_text)
                ),
            ]
            response = self.llm.invoke(messages)
            return self._parse_llm_response(response.content, chunk_id)
        except Exception as e:
            logger.error(f"LLM entity extraction failed for chunk {chunk_id}: {e}")
            return []

    async def aextract(self, chunk_text: str, chunk_id: int) -> list[ExtractedEntity]:
        """Async extract entities from a text chunk using the LLM.

        Args:
            chunk_text: The text content of the chunk to process.
            chunk_id: The database ID of the source chunk.

        Returns:
            List of ExtractedEntity instances, at most 50 per chunk.
            Returns an empty list if chunk is empty, extraction fails,
            or no valid entities are found.
        """
        if not chunk_text or not chunk_text.strip():
            return []

        try:
            messages = [
                SystemMessage(content=_SYSTEM_PROMPT),
                HumanMessage(
                    content=_USER_PROMPT_TEMPLATE.format(chunk_text=chunk_text)
                ),
            ]
            response = await self.llm.ainvoke(messages)
            return self._parse_llm_response(response.content, chunk_id)
        except Exception as e:
            logger.error(f"LLM entity extraction failed for chunk {chunk_id}: {e}")
            return []

    def _parse_llm_response(
        self, response_content: Any, chunk_id: int
    ) -> list[ExtractedEntity]:
        """Parse LLM response into ExtractedEntity objects.

        Validates entity types, normalizes names, deduplicates, truncates
        fields, and caps at MAX_ENTITIES_PER_CHUNK.

        Args:
            response_content: The raw LLM response content (string).
            chunk_id: The source chunk ID.

        Returns:
            List of validated, deduplicated ExtractedEntity instances.
        """
        try:
            # Handle response content that may be wrapped in markdown code blocks
            content = str(response_content).strip()
            if content.startswith("```"):
                # Strip markdown code block markers
                lines = content.split("\n")
                # Remove first line (```json or ```) and last line (```)
                lines = [
                    line
                    for line in lines
                    if not line.strip().startswith("```")
                ]
                content = "\n".join(lines).strip()

            raw_entities = json.loads(content)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.error(
                f"Failed to parse LLM entity extraction response for chunk "
                f"{chunk_id}: {e}"
            )
            return []

        if not isinstance(raw_entities, list):
            logger.error(
                f"LLM entity extraction response for chunk {chunk_id} is not a list"
            )
            return []

        # Cap at MAX_ENTITIES_PER_CHUNK before processing
        raw_entities = raw_entities[:MAX_ENTITIES_PER_CHUNK]

        entities: list[ExtractedEntity] = []
        seen: set[tuple[str, str]] = set()

        for raw in raw_entities:
            if not isinstance(raw, dict):
                continue

            name = raw.get("name")
            entity_type = raw.get("entity_type")
            description = raw.get("description", "")

            # Skip entries with missing required fields
            if not name or not entity_type:
                continue

            # Ensure string types
            name = str(name).strip()
            entity_type = str(entity_type).strip().lower()
            description = str(description).strip() if description else ""

            # Validate entity type against allowed set
            if entity_type not in ENTITY_TYPES:
                continue

            # Skip empty names
            if not name:
                continue

            # Normalize name for deduplication
            normalized_name = _normalize_name(name)
            if not normalized_name:
                continue

            # Deduplicate by (normalized_name, entity_type)
            dedup_key = (normalized_name, entity_type)
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Truncate to schema limits
            truncated_name = name[:512]
            truncated_description = description[:2000]

            entity = ExtractedEntity(
                name=truncated_name,
                normalized_name=normalized_name[:512],
                entity_type=entity_type,
                description=truncated_description,
                source_chunk_id=chunk_id,
            )
            entities.append(entity)

            # Enforce entity limit (already capped raw_entities, but
            # deduplication may reduce count so this is a safety check)
            if len(entities) >= MAX_ENTITIES_PER_CHUNK:
                break

        return entities
