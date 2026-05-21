"""GraphRAG Engine service for building and querying the semantic knowledge graph.

Manages entity extraction, relationship extraction, deduplication, graph merging,
file re-processing, and graph neighborhood retrieval. Coordinates with
EntityExtractor and RelationshipExtractor to process document chunks and maintain
the entity-relationship graph in the database.
"""

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.config import GraphRAGSettings
from app.models.chunk import Chunk
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship
from app.services.entity_extractor import EntityExtractor, ExtractedEntity
from app.services.relationship_extractor import (
    ExtractedRelationship,
    RelationshipExtractor,
)

logger = logging.getLogger(__name__)


class GraphRAGEngine:
    """Builds and queries the semantic knowledge graph.

    Orchestrates entity and relationship extraction from document chunks,
    deduplicates entities, merges results into the file-level graph, and
    provides graph neighborhood queries for retrieval enrichment.

    Args:
        db: SQLAlchemy database session.
        config: GraphRAG configuration settings.
    """

    def __init__(self, db: Session, config: GraphRAGSettings):
        self.db = db
        self.config = config
        self.entity_extractor = EntityExtractor(config.entity_extraction_method)
        self.relationship_extractor = RelationshipExtractor()

    def extract_entities_and_relationships(
        self, chunks: list[Chunk], file_id: int
    ) -> None:
        """Extract entities and relationships from chunks, merge into graph.

        For file re-processing, removes all previously extracted entities and
        relationships for the file before performing new extraction.

        Processes each chunk through entity extraction and relationship extraction,
        deduplicates entities across all chunks, then merges the results into the
        database graph.

        Args:
            chunks: List of Chunk model instances to process.
            file_id: The database ID of the file being processed.
        """
        # Step 1: Remove previously extracted entities and relationships for this file
        self._remove_file_extractions(file_id)

        # Step 2: Extract entities and relationships from each chunk
        all_extracted_entities: list[ExtractedEntity] = []
        all_extracted_relationships: list[ExtractedRelationship] = []

        for chunk in chunks:
            try:
                # Extract entities from chunk text
                entities = self.entity_extractor.extract(chunk.text, chunk.id)
                all_extracted_entities.extend(entities)

                # Extract relationships between entities in this chunk
                if entities:
                    relationships = self.relationship_extractor.extract(
                        entities, chunk.text, chunk.id
                    )
                    all_extracted_relationships.extend(relationships)

            except Exception as e:
                logger.error(
                    f"Entity/relationship extraction failed for chunk {chunk.id} "
                    f"(file_id={file_id}): {e}"
                )
                continue

        # Step 3: Deduplicate entities across all chunks
        deduplicated_entities = self._deduplicate_entities(all_extracted_entities)

        # Step 4: Create entity records in the database
        entity_map = self._persist_entities(deduplicated_entities)

        # Step 5: Create relationship records in the database
        persisted_relationships = self._persist_relationships(
            all_extracted_relationships, entity_map
        )

        # Step 6: Merge into file graph (adds entity nodes and semantic edges)
        self._merge_into_file_graph(file_id, deduplicated_entities, persisted_relationships)

        logger.info(
            f"Extracted {len(deduplicated_entities)} entities and "
            f"{len(persisted_relationships)} relationships for file_id={file_id}"
        )

    def _deduplicate_entities(
        self, entities: list[ExtractedEntity]
    ) -> list[dict[str, Any]]:
        """Merge entities with same normalized name and type.

        Entities sharing the same case-folded whitespace-trimmed name AND the
        same type are merged into a single entity record whose source_chunk_ids
        contains all contributing chunk IDs.

        Args:
            entities: List of extracted entities from all chunks.

        Returns:
            List of deduplicated entity dicts with keys: name, normalized_name,
            entity_type, description, source_chunk_ids.
        """
        # Key: (normalized_name, entity_type) -> merged entity data
        merged: dict[tuple[str, str], dict[str, Any]] = {}

        for entity in entities:
            key = (entity.normalized_name, entity.entity_type)

            if key in merged:
                # Merge: add chunk ID to source list
                existing = merged[key]
                if entity.source_chunk_id not in existing["source_chunk_ids"]:
                    existing["source_chunk_ids"].append(entity.source_chunk_id)
                # Keep the longer description
                if len(entity.description) > len(existing["description"]):
                    existing["description"] = entity.description
            else:
                merged[key] = {
                    "name": entity.name,
                    "normalized_name": entity.normalized_name,
                    "entity_type": entity.entity_type,
                    "description": entity.description,
                    "source_chunk_ids": [entity.source_chunk_id],
                }

        return list(merged.values())

    def _persist_entities(
        self, deduplicated_entities: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Persist deduplicated entities to the database.

        Creates Entity records for each deduplicated entity. If an entity with
        the same normalized_name and entity_type already exists (from another
        file), merges the source_chunk_ids.

        Args:
            deduplicated_entities: List of deduplicated entity dicts.

        Returns:
            Mapping of normalized_name to entity database ID.
        """
        entity_map: dict[str, int] = {}

        for entity_data in deduplicated_entities:
            # Check if entity already exists in the database
            existing = (
                self.db.query(Entity)
                .filter(
                    Entity.normalized_name == entity_data["normalized_name"],
                    Entity.entity_type == entity_data["entity_type"],
                )
                .first()
            )

            if existing:
                # Merge source_chunk_ids
                current_chunks = existing.source_chunk_ids or []
                new_chunks = entity_data["source_chunk_ids"]
                merged_chunks = list(
                    set(current_chunks) | set(new_chunks)
                )
                existing.source_chunk_ids = merged_chunks
                # Update description if new one is longer
                if entity_data["description"] and (
                    not existing.description
                    or len(entity_data["description"]) > len(existing.description)
                ):
                    existing.description = entity_data["description"]
                entity_map[entity_data["normalized_name"]] = existing.id
            else:
                # Create new entity
                new_entity = Entity(
                    name=entity_data["name"][:512],
                    normalized_name=entity_data["normalized_name"][:512],
                    entity_type=entity_data["entity_type"][:128],
                    description=(entity_data["description"] or "")[:2000],
                    source_chunk_ids=entity_data["source_chunk_ids"],
                )
                self.db.add(new_entity)
                self.db.flush()  # Get the ID
                entity_map[entity_data["normalized_name"]] = new_entity.id

        self.db.commit()
        return entity_map

    def _persist_relationships(
        self,
        extracted_relationships: list[ExtractedRelationship],
        entity_map: dict[str, int],
    ) -> list[EntityRelationship]:
        """Persist extracted relationships to the database.

        Maps entity names to their database IDs and creates EntityRelationship
        records. Skips relationships where either entity is not found in the map.

        Args:
            extracted_relationships: List of extracted relationships.
            entity_map: Mapping of normalized entity names to database IDs.

        Returns:
            List of persisted EntityRelationship model instances.
        """
        persisted: list[EntityRelationship] = []

        for rel in extracted_relationships:
            # Normalize names to look up in entity_map
            source_norm = " ".join(rel.source_entity_name.split()).casefold()
            target_norm = " ".join(rel.target_entity_name.split()).casefold()

            source_id = entity_map.get(source_norm)
            target_id = entity_map.get(target_norm)

            if source_id is None or target_id is None:
                logger.debug(
                    f"Skipping relationship '{rel.source_entity_name}' -> "
                    f"'{rel.target_entity_name}': entity not found in map"
                )
                continue

            # Skip self-relationships
            if source_id == target_id:
                continue

            # Clamp strength to [0.0, 1.0]
            strength = max(0.0, min(1.0, rel.strength))

            entity_rel = EntityRelationship(
                source_entity_id=source_id,
                target_entity_id=target_id,
                description=(rel.description or "")[:2000],
                strength=strength,
                source_chunk_id=rel.source_chunk_id,
            )
            self.db.add(entity_rel)
            persisted.append(entity_rel)

        self.db.commit()
        return persisted

    def _merge_into_file_graph(
        self,
        file_id: int,
        entities: list[dict[str, Any]],
        relationships: list[EntityRelationship],
    ) -> None:
        """Add entity nodes and semantic edges without removing manual relationships.

        This method ensures that manually created relationships (from the
        Relationship model/engine) are never modified or removed. It only
        adds/updates entity nodes and semantic edges (EntityRelationship records)
        for the given file.

        The actual persistence of entities and relationships is handled by
        _persist_entities and _persist_relationships. This method serves as
        the integration point that confirms the merge is complete and logs
        the result.

        Args:
            file_id: The file ID being processed.
            entities: List of deduplicated entity dicts that were persisted.
            relationships: List of EntityRelationship instances that were persisted.
        """
        # Manual relationships (from the Relationship model) are stored in a
        # separate table ("relationships") and are never touched by this method.
        # Entity nodes and semantic edges (EntityRelationship) are in their own
        # tables and do not interfere with the manual relationship table.
        logger.debug(
            f"Merged {len(entities)} entities and {len(relationships)} semantic "
            f"edges into graph for file_id={file_id}. Manual relationships preserved."
        )

    def _remove_file_extractions(self, file_id: int) -> None:
        """Remove all previously extracted entities and relationships for a file.

        For file re-processing, this removes:
        1. All EntityRelationship records whose source_chunk belongs to this file
        2. All Entity records that only reference chunks from this file
        3. Updates Entity records that reference chunks from multiple files
           (removes this file's chunk IDs from source_chunk_ids)

        Manual relationships (Relationship model) are never touched.

        Args:
            file_id: The file ID to clean up extractions for.
        """
        # Get all chunk IDs for this file
        file_chunks = (
            self.db.query(Chunk.id).filter(Chunk.file_id == file_id).all()
        )
        file_chunk_ids = {chunk_id for (chunk_id,) in file_chunks}

        if not file_chunk_ids:
            return

        # Step 1: Remove EntityRelationships that reference this file's chunks
        self.db.query(EntityRelationship).filter(
            EntityRelationship.source_chunk_id.in_(file_chunk_ids)
        ).delete(synchronize_session="fetch")

        # Step 2: Handle entities - remove or update based on chunk references
        entities = self.db.query(Entity).all()
        entities_to_delete: list[int] = []

        for entity in entities:
            current_chunks = set(entity.source_chunk_ids or [])
            remaining_chunks = current_chunks - file_chunk_ids

            if not remaining_chunks:
                # Entity only referenced chunks from this file - delete it
                entities_to_delete.append(entity.id)
            elif remaining_chunks != current_chunks:
                # Entity references chunks from other files too - update
                entity.source_chunk_ids = list(remaining_chunks)

        if entities_to_delete:
            # Also remove any relationships referencing entities being deleted
            self.db.query(EntityRelationship).filter(
                (EntityRelationship.source_entity_id.in_(entities_to_delete))
                | (EntityRelationship.target_entity_id.in_(entities_to_delete))
            ).delete(synchronize_session="fetch")

            self.db.query(Entity).filter(
                Entity.id.in_(entities_to_delete)
            ).delete(synchronize_session="fetch")

        self.db.commit()

        logger.info(
            f"Removed extractions for file_id={file_id}: "
            f"{len(entities_to_delete)} entities deleted, "
            f"relationships cleaned from {len(file_chunk_ids)} chunks"
        )

    def get_graph_neighborhood(
        self, chunk_id: int, hops: int = 1
    ) -> dict[str, Any]:
        """Get entities and relationships within N hops of a chunk.

        Retrieves the graph neighborhood starting from entities referenced by
        the given chunk, expanding outward by the specified number of hops.

        For hops=1 (default):
        - Finds all entities directly associated with the chunk
        - Finds all relationships where those entities are source or target
        - Includes the connected entities (1-hop neighbors)

        Args:
            chunk_id: The database ID of the chunk to get neighborhood for.
            hops: Number of hops to expand (default 1).

        Returns:
            Dict with keys:
            - "entities": list of entity dicts (id, name, type, description)
            - "relationships": list of relationship dicts (source, target, description, strength)
        """
        # Find entities that reference this chunk
        all_entities = self.db.query(Entity).all()
        seed_entity_ids: set[int] = set()

        for entity in all_entities:
            chunk_ids = entity.source_chunk_ids or []
            if chunk_id in chunk_ids:
                seed_entity_ids.add(entity.id)

        if not seed_entity_ids:
            return {"entities": [], "relationships": []}

        # Expand by hops
        current_entity_ids = set(seed_entity_ids)
        all_relationship_ids: set[int] = set()

        for _ in range(hops):
            # Find relationships connected to current entities
            relationships = (
                self.db.query(EntityRelationship)
                .filter(
                    (EntityRelationship.source_entity_id.in_(current_entity_ids))
                    | (EntityRelationship.target_entity_id.in_(current_entity_ids))
                )
                .all()
            )

            new_entity_ids: set[int] = set()
            for rel in relationships:
                all_relationship_ids.add(rel.id)
                new_entity_ids.add(rel.source_entity_id)
                new_entity_ids.add(rel.target_entity_id)

            # Expand to include newly discovered entities
            current_entity_ids = current_entity_ids | new_entity_ids

        # Fetch all entities in the neighborhood
        neighborhood_entities = (
            self.db.query(Entity)
            .filter(Entity.id.in_(current_entity_ids))
            .all()
        )

        # Fetch all relationships in the neighborhood
        neighborhood_relationships = (
            self.db.query(EntityRelationship)
            .filter(EntityRelationship.id.in_(all_relationship_ids))
            .all()
        )

        # Format results
        entities_result = [
            {
                "id": e.id,
                "name": e.name,
                "type": e.entity_type,
                "description": e.description,
            }
            for e in neighborhood_entities
        ]

        relationships_result = [
            {
                "id": r.id,
                "source_entity_id": r.source_entity_id,
                "target_entity_id": r.target_entity_id,
                "description": r.description,
                "strength": r.strength,
            }
            for r in neighborhood_relationships
        ]

        return {
            "entities": entities_result,
            "relationships": relationships_result,
        }
