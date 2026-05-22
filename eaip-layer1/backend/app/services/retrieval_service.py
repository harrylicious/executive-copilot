"""Retrieval service for local, global, and combined search queries.

Handles search queries against the vector store and knowledge graph,
assembling context for downstream LLM consumption.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import tiktoken
from sqlalchemy.orm import Session

from app.config import GraphRAGSettings
from app.models.chunk import Chunk
from app.models.community import Community
from app.models.entity import Entity
from app.models.file import File
from app.services.embedding_model import EmbeddingModel
from app.services.graphrag_engine import GraphRAGEngine
from app.services.vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured search result containing all retrieval components."""

    chunks: list[dict] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    community_summaries: list[dict] = field(default_factory=list)
    source_attributions: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


class RetrievalService:
    """Handles local, global, and combined search queries.

    Provides three retrieval modes:
    - local_search: Vector similarity search enriched with graph neighborhood
    - global_search: Community-summary-based thematic search
    - combined_search: Merged local and global results within token budget

    Args:
        db: SQLAlchemy database session.
        config: GraphRAG settings for retrieval parameters.
    """

    def __init__(self, db: Session, config: GraphRAGSettings):
        self.db = db
        self.config = config
        self.model = EmbeddingModel(config.embedding_model)
        self.vector_store = ChromaVectorStore(config)
        self.graphrag = GraphRAGEngine(db, config)

    def local_search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.3,
        similarity_weight: float = 0.7,
    ) -> SearchResult:
        """Vector similarity search enriched with graph neighborhood.

        Generates a query embedding, performs similarity search against the
        vector store, enriches each result with its 1-hop graph neighborhood,
        computes a combined score, and returns results ranked by that score.

        Args:
            query: The search query text (1-1000 characters).
            top_k: Maximum number of results to return (1-50, default 5).
            min_score: Minimum similarity score threshold (0.0-1.0, default 0.5).
            similarity_weight: Weight for vector similarity in combined score
                (0.0-1.0, default 0.7). Graph weight = 1 - similarity_weight.

        Returns:
            SearchResult with ranked chunks, entities, relationships, and metadata.

        Raises:
            ValueError: If query is empty or exceeds 1000 characters.
        """
        start_time = time.time()

        # Validate query
        if not query or not query.strip():
            raise ValueError(
                "Query text must not be empty. Please provide a query between "
                "1 and 1000 characters."
            )
        if len(query) > 1000:
            raise ValueError(
                "Query text exceeds 1000 characters. Please shorten your query "
                "to at most 1000 characters."
            )

        graph_weight = 1.0 - similarity_weight

        # Step 1: Generate query embedding
        query_embedding = self.model.embed_query(query)

        # Step 2: Perform similarity search against vector store
        vector_results = self.vector_store.similarity_search(
            query_embedding=query_embedding,
            top_k=top_k,
            min_score=min_score,
        )

        # Step 3: Return empty result if no chunks meet threshold
        if not vector_results:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return SearchResult(
                metadata={
                    "query_time_ms": elapsed_ms,
                    "total_chunks_searched": 0,
                    "retrieval_mode": "local",
                }
            )

        # Step 4: Enrich each result with graph neighborhood and file metadata
        enriched_chunks: list[dict[str, Any]] = []
        all_entities: list[dict[str, Any]] = []
        all_relationships: list[dict[str, Any]] = []
        source_attributions: list[dict[str, Any]] = []
        seen_entity_ids: set[int] = set()
        seen_relationship_ids: set[int] = set()
        seen_file_ids: set[int] = set()

        for result in vector_results:
            file_id = result.get("file_id")
            chunk_index = result.get("chunk_index")
            vector_similarity = result.get("score", 0.0)

            # Get the chunk record from the database for graph neighborhood lookup
            chunk_record = (
                self.db.query(Chunk)
                .filter(
                    Chunk.file_id == file_id,
                    Chunk.chunk_index == chunk_index,
                )
                .first()
            )

            # Get graph neighborhood (1-hop) for this chunk
            neighborhood: dict[str, Any] = {"entities": [], "relationships": []}
            graph_connection_count = 0.0

            if chunk_record:
                neighborhood = self.graphrag.get_graph_neighborhood(
                    chunk_id=chunk_record.id, hops=1
                )
                # Compute graph relevance based on connection count
                graph_connection_count = float(
                    len(neighborhood.get("entities", []))
                    + len(neighborhood.get("relationships", []))
                )

            # Get source file metadata
            file_metadata = self._get_file_metadata(file_id)

            # Build enriched chunk result
            chunk_data: dict[str, Any] = {
                "text": result.get("text", ""),
                "score": vector_similarity,
                "file_id": file_id,
                "file_name": file_metadata.get("name", ""),
                "department": file_metadata.get("department", ""),
                "file_path": file_metadata.get("path", ""),
                "chunk_index": chunk_index,
                "entities": neighborhood.get("entities", []),
                "relationships": neighborhood.get("relationships", []),
                "_vector_similarity": vector_similarity,
                "_graph_connection_count": graph_connection_count,
            }
            enriched_chunks.append(chunk_data)

            # Collect unique entities
            for entity in neighborhood.get("entities", []):
                entity_id = entity.get("id")
                if entity_id and entity_id not in seen_entity_ids:
                    seen_entity_ids.add(entity_id)
                    all_entities.append(entity)

            # Collect unique relationships
            for rel in neighborhood.get("relationships", []):
                rel_id = rel.get("id")
                if rel_id and rel_id not in seen_relationship_ids:
                    seen_relationship_ids.add(rel_id)
                    all_relationships.append(rel)

            # Collect source attributions
            if file_id and file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                source_attributions.append(
                    {
                        "file_id": file_id,
                        "file_name": file_metadata.get("name", ""),
                        "department": file_metadata.get("department", ""),
                        "file_path": file_metadata.get("path", ""),
                    }
                )

        # Step 5: Normalize graph relevance and compute combined scores
        max_connections = max(
            (c["_graph_connection_count"] for c in enriched_chunks), default=0.0
        )

        for chunk_data in enriched_chunks:
            normalized_graph_relevance = self._normalize_graph_relevance(
                connection_count=int(chunk_data["_graph_connection_count"]),
                max_connections=int(max_connections),
            )
            combined_score = self._compute_combined_score(
                similarity=chunk_data["_vector_similarity"],
                graph_relevance=normalized_graph_relevance,
                sim_weight=similarity_weight,
            )
            chunk_data["score"] = combined_score

        # Step 6: Rank results by combined score in descending order
        enriched_chunks.sort(key=lambda x: x["score"], reverse=True)

        # Clean up internal fields from the output
        for chunk_data in enriched_chunks:
            chunk_data.pop("_vector_similarity", None)
            chunk_data.pop("_graph_connection_count", None)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return SearchResult(
            chunks=enriched_chunks,
            entities=all_entities,
            relationships=all_relationships,
            community_summaries=[],
            source_attributions=source_attributions,
            metadata={
                "query_time_ms": elapsed_ms,
                "total_chunks_searched": len(vector_results),
                "retrieval_mode": "local",
            },
        )

    def global_search(
        self,
        query: str,
        num_communities: int = 3,
        min_relevance: float = 0.1,
    ) -> SearchResult:
        """Community-summary-based thematic search.

        Generates an embedding for the query text and compares it against
        all stored community summary embeddings using cosine similarity.
        Returns ranked community summaries with member entities and up to
        3 document references per community.

        Args:
            query: The search query text (1-1000 characters).
            num_communities: Number of communities to return (1-20, default 3).
            min_relevance: Minimum cosine similarity threshold (0.0-1.0, default 0.1).

        Returns:
            SearchResult with community_summaries, entities, source_attributions,
            and metadata populated.
        """
        start_time = time.time()

        # Clamp num_communities to valid range
        num_communities = max(1, min(20, num_communities))

        # Fetch all communities from the database
        communities = self.db.query(Community).all()

        # If no communities exist, return empty results with metadata
        if not communities:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return SearchResult(
                chunks=[],
                entities=[],
                relationships=[],
                community_summaries=[],
                source_attributions=[],
                metadata={
                    "query_time_ms": elapsed_ms,
                    "total_chunks_searched": 0,
                    "retrieval_mode": "global",
                    "message": "Community detection has not been performed",
                },
            )

        # Generate query embedding
        query_embedding = self.model.embed_query(query)

        # Score each community by cosine similarity between query and summary embedding
        scored_communities: list[tuple[Community, float]] = []

        for community in communities:
            if not community.summary_embedding:
                continue

            score = self._cosine_similarity(
                query_embedding, community.summary_embedding
            )

            if score >= min_relevance:
                scored_communities.append((community, score))

        # If no communities meet the threshold, return empty results
        if not scored_communities:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return SearchResult(
                chunks=[],
                entities=[],
                relationships=[],
                community_summaries=[],
                source_attributions=[],
                metadata={
                    "query_time_ms": elapsed_ms,
                    "total_chunks_searched": 0,
                    "retrieval_mode": "global",
                },
            )

        # Sort by relevance score descending and take top num_communities
        scored_communities.sort(key=lambda x: x[1], reverse=True)
        top_communities = scored_communities[:num_communities]

        # Build result structures
        community_summaries = []
        all_entities: list[dict] = []
        all_source_attributions: list[dict] = []
        seen_entity_ids: set[int] = set()
        seen_file_ids: set[int] = set()

        for community, score in top_communities:
            member_entity_ids = community.member_entity_ids or []

            # Fetch member entities
            member_entities = (
                self.db.query(Entity)
                .filter(Entity.id.in_(member_entity_ids))
                .all()
                if member_entity_ids
                else []
            )

            # Build member entity dicts
            member_entity_dicts = [
                {
                    "id": e.id,
                    "name": e.name,
                    "type": e.entity_type,
                    "description": e.description,
                }
                for e in member_entities
            ]

            # Collect unique entities for the top-level entities list
            for e in member_entities:
                if e.id not in seen_entity_ids:
                    seen_entity_ids.add(e.id)
                    all_entities.append(
                        {
                            "id": e.id,
                            "name": e.name,
                            "type": e.entity_type,
                            "description": e.description,
                        }
                    )

            # Get up to 3 document references per community
            # Selected by highest entity co-occurrence count within the community
            document_references = self._get_document_references(
                member_entities, max_docs=3
            )

            # Collect source attributions
            for doc_ref in document_references:
                file_id = doc_ref.get("file_id")
                if file_id and file_id not in seen_file_ids:
                    seen_file_ids.add(file_id)
                    all_source_attributions.append(doc_ref)

            community_summaries.append(
                {
                    "community_id": community.id,
                    "level": community.level,
                    "summary": community.summary or "",
                    "relevance_score": round(score, 6),
                    "member_entities": member_entity_dicts,
                    "document_references": document_references,
                }
            )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return SearchResult(
            chunks=[],
            entities=all_entities,
            relationships=[],
            community_summaries=community_summaries,
            source_attributions=all_source_attributions,
            metadata={
                "query_time_ms": elapsed_ms,
                "total_chunks_searched": 0,
                "retrieval_mode": "global",
            },
        )

    def _cosine_similarity(
        self, vec_a: list[float], vec_b: list[float]
    ) -> float:
        """Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector.
            vec_b: Second vector.

        Returns:
            Cosine similarity score in range [0.0, 1.0].
            Returns 0.0 if either vector has zero magnitude.
        """
        a = np.array(vec_a, dtype=np.float64)
        b = np.array(vec_b, dtype=np.float64)

        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)

        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0

        similarity = float(dot_product / (norm_a * norm_b))

        # Clamp to [0.0, 1.0] to handle floating-point edge cases
        return max(0.0, min(1.0, similarity))

    def _get_document_references(
        self, entities: list[Entity], max_docs: int = 3
    ) -> list[dict]:
        """Get document references for a community by entity co-occurrence.

        Selects documents (files) that have the highest number of entity
        co-occurrences within the community. An entity co-occurs in a file
        if any of its source chunks belong to that file.

        Args:
            entities: List of member entities in the community.
            max_docs: Maximum number of document references to return.

        Returns:
            List of document reference dicts with file_id, name, department,
            and path, sorted by co-occurrence count descending.
        """
        if not entities:
            return []

        # Collect all chunk IDs from member entities
        all_chunk_ids: set[int] = set()
        for entity in entities:
            chunk_ids = entity.source_chunk_ids or []
            all_chunk_ids.update(chunk_ids)

        if not all_chunk_ids:
            return []

        # Find which files these chunks belong to
        chunks = (
            self.db.query(Chunk)
            .filter(Chunk.id.in_(all_chunk_ids))
            .all()
        )

        # Count entity co-occurrences per file
        file_entity_count: dict[int, int] = {}
        for chunk in chunks:
            file_id = chunk.file_id
            file_entity_count[file_id] = file_entity_count.get(file_id, 0) + 1

        # Sort files by co-occurrence count descending
        sorted_file_ids = sorted(
            file_entity_count.keys(),
            key=lambda fid: file_entity_count[fid],
            reverse=True,
        )[:max_docs]

        # Fetch file metadata
        files = (
            self.db.query(File)
            .filter(File.id.in_(sorted_file_ids))
            .all()
        )

        # Build file lookup for ordering
        file_map = {f.id: f for f in files}

        document_references = []
        for file_id in sorted_file_ids:
            file_obj = file_map.get(file_id)
            if file_obj:
                document_references.append(
                    {
                        "file_id": file_obj.id,
                        "name": file_obj.name,
                        "department": file_obj.department,
                        "path": file_obj.path,
                    }
                )

        return document_references

    def _compute_combined_score(
        self,
        similarity: float,
        graph_relevance: float,
        sim_weight: float = 0.7,
    ) -> float:
        """Compute weighted combination of similarity and graph relevance.

        Args:
            similarity: Vector similarity score (0.0-1.0).
            graph_relevance: Normalized graph relevance score (0.0-1.0).
            sim_weight: Weight for similarity component (0.0-1.0).
                Graph weight is computed as (1 - sim_weight).

        Returns:
            Combined score as weighted sum.
        """
        graph_weight = 1.0 - sim_weight
        return sim_weight * similarity + graph_weight * graph_relevance

    def _normalize_graph_relevance(
        self, connection_count: int, max_connections: int
    ) -> float:
        """Normalize graph connection count to 0-1 scale.

        Uses simple ratio normalization: connection_count / max_connections.
        Returns 0.0 when max_connections is 0 (no graph data available).

        Args:
            connection_count: Number of graph connections for a chunk.
            max_connections: Maximum connection count across all results.

        Returns:
            Normalized relevance score between 0.0 and 1.0.
        """
        if max_connections <= 0:
            return 0.0
        return min(1.0, connection_count / max_connections)

    def combined_search(
        self,
        query: str,
        max_tokens: int = 4000,
        top_k: int = 5,
        num_communities: int = 3,
        min_score: float = 0.3,
        min_relevance: float = 0.1,
        similarity_weight: float = 0.7,
    ) -> SearchResult:
        """Merge local and global results within token budget.

        Performs both local and global search, then merges results by
        interleaving in descending order of relevance score. Local results
        take precedence when scores are equal. The assembled context is
        truncated to fit within the configured token limit by removing
        lowest-relevance items first.

        Args:
            query: The search query text (1-1000 characters).
            max_tokens: Maximum context token limit (1000-16000, default 4000).
            top_k: Maximum number of local results (1-50, default 5).
            num_communities: Number of communities for global search (1-20, default 3).
            min_score: Minimum similarity score for local search (0.0-1.0, default 0.5).
            min_relevance: Minimum relevance for global search (0.0-1.0, default 0.1).
            similarity_weight: Weight for vector similarity in local search
                (0.0-1.0, default 0.7).

        Returns:
            SearchResult with merged chunks, entities, relationships,
            community_summaries, source_attributions, and metadata.

        Raises:
            ValueError: If query is empty or exceeds 1000 characters.
        """
        start_time = time.time()

        # Validate and clamp max_tokens
        max_tokens = max(1000, min(16000, max_tokens))

        # Perform both searches
        local_result = self.local_search(
            query=query,
            top_k=top_k,
            min_score=min_score,
            similarity_weight=similarity_weight,
        )
        global_result = self.global_search(
            query=query,
            num_communities=num_communities,
            min_relevance=min_relevance,
        )

        # Merge chunks and community summaries by relevance score
        # Create tagged items for interleaving: (score, source_priority, item_type, item)
        # source_priority: 0 = local (higher precedence), 1 = global
        merged_items: list[tuple[float, int, str, dict]] = []

        for chunk in local_result.chunks:
            score = chunk.get("score", 0.0)
            merged_items.append((score, 0, "chunk", chunk))

        for community_summary in global_result.community_summaries:
            score = community_summary.get("relevance_score", 0.0)
            merged_items.append((score, 1, "community_summary", community_summary))

        # Sort by score descending, then by source_priority ascending (local first on ties)
        merged_items.sort(key=lambda x: (-x[0], x[1]))

        # Separate back into ordered lists
        merged_chunks: list[dict] = []
        merged_community_summaries: list[dict] = []

        for _score, _priority, item_type, item in merged_items:
            if item_type == "chunk":
                merged_chunks.append(item)
            else:
                merged_community_summaries.append(item)

        # Merge entities (deduplicate by id)
        seen_entity_ids: set[int] = set()
        merged_entities: list[dict] = []
        for entity in local_result.entities + global_result.entities:
            entity_id = entity.get("id")
            if entity_id is not None and entity_id not in seen_entity_ids:
                seen_entity_ids.add(entity_id)
                merged_entities.append(entity)

        # Merge relationships (deduplicate by id)
        seen_rel_ids: set[int] = set()
        merged_relationships: list[dict] = []
        for rel in local_result.relationships + global_result.relationships:
            rel_id = rel.get("id")
            if rel_id is not None and rel_id not in seen_rel_ids:
                seen_rel_ids.add(rel_id)
                merged_relationships.append(rel)

        # Merge source attributions (deduplicate by file_id)
        seen_file_ids: set[int] = set()
        merged_source_attributions: list[dict] = []
        for attr in local_result.source_attributions + global_result.source_attributions:
            file_id = attr.get("file_id")
            if file_id is not None and file_id not in seen_file_ids:
                seen_file_ids.add(file_id)
                merged_source_attributions.append(attr)

        # Compute total chunks searched
        total_chunks_searched = (
            local_result.metadata.get("total_chunks_searched", 0)
            + global_result.metadata.get("total_chunks_searched", 0)
        )

        # Assemble the result
        result = SearchResult(
            chunks=merged_chunks,
            entities=merged_entities,
            relationships=merged_relationships,
            community_summaries=merged_community_summaries,
            source_attributions=merged_source_attributions,
            metadata={
                "query_time_ms": 0,  # Will be updated below
                "total_chunks_searched": total_chunks_searched,
                "retrieval_mode": "combined",
            },
        )

        # Truncate to token limit
        result = self._truncate_to_token_limit(result, max_tokens)

        # Update timing metadata
        elapsed_ms = int((time.time() - start_time) * 1000)
        result.metadata["query_time_ms"] = elapsed_ms

        return result

    def _truncate_to_token_limit(
        self, results: SearchResult, max_tokens: int
    ) -> SearchResult:
        """Remove lowest-relevance items until within token budget.

        Counts tokens across all text content in the result (chunk texts,
        community summaries, entity descriptions, relationship descriptions).
        If the total exceeds max_tokens, removes items with the lowest
        relevance scores first (chunks by score, community summaries by
        relevance_score).

        Args:
            results: The SearchResult to potentially truncate.
            max_tokens: Maximum allowed token count for the assembled context.

        Returns:
            A new SearchResult truncated to fit within the token budget.
        """
        tokenizer = tiktoken.get_encoding("cl100k_base")

        def count_tokens(text: str) -> int:
            """Count tokens in a text string."""
            if not text:
                return 0
            return len(tokenizer.encode(text))

        def compute_result_tokens(result: SearchResult) -> int:
            """Compute total token count for a SearchResult."""
            total = 0
            for chunk in result.chunks:
                total += count_tokens(chunk.get("text", ""))
            for summary in result.community_summaries:
                total += count_tokens(summary.get("summary", ""))
            return total

        current_tokens = compute_result_tokens(results)

        if current_tokens <= max_tokens:
            return results

        # Build a list of removable items with their scores and token costs
        # Each item: (score, source_priority, item_type, index, token_cost)
        # source_priority: 0 = local (chunk), 1 = global (community_summary)
        removable_items: list[tuple[float, int, str, int, int]] = []

        for i, chunk in enumerate(results.chunks):
            score = chunk.get("score", 0.0)
            token_cost = count_tokens(chunk.get("text", ""))
            removable_items.append((score, 0, "chunk", i, token_cost))

        for i, summary in enumerate(results.community_summaries):
            score = summary.get("relevance_score", 0.0)
            token_cost = count_tokens(summary.get("summary", ""))
            removable_items.append((score, 1, "community_summary", i, token_cost))

        # Sort by score ascending (lowest relevance first for removal)
        # On ties, global items (priority=1) are removed before local (priority=0)
        removable_items.sort(key=lambda x: (x[0], -x[1]))

        # Remove items until we're within budget
        chunks_to_remove: set[int] = set()
        summaries_to_remove: set[int] = set()

        for score, priority, item_type, index, token_cost in removable_items:
            if current_tokens <= max_tokens:
                break
            if item_type == "chunk":
                chunks_to_remove.add(index)
            else:
                summaries_to_remove.add(index)
            current_tokens -= token_cost

        # Build truncated result
        truncated_chunks = [
            chunk
            for i, chunk in enumerate(results.chunks)
            if i not in chunks_to_remove
        ]
        truncated_summaries = [
            summary
            for i, summary in enumerate(results.community_summaries)
            if i not in summaries_to_remove
        ]

        # Rebuild entities and relationships based on remaining chunks
        # Keep entities and relationships that are referenced by remaining chunks
        remaining_entity_ids: set[int] = set()
        remaining_rel_ids: set[int] = set()

        for chunk in truncated_chunks:
            for entity in chunk.get("entities", []):
                entity_id = entity.get("id")
                if entity_id is not None:
                    remaining_entity_ids.add(entity_id)
            for rel in chunk.get("relationships", []):
                rel_id = rel.get("id")
                if rel_id is not None:
                    remaining_rel_ids.add(rel_id)

        # Also keep entities from remaining community summaries
        for summary in truncated_summaries:
            for entity in summary.get("member_entities", []):
                entity_id = entity.get("id")
                if entity_id is not None:
                    remaining_entity_ids.add(entity_id)

        truncated_entities = [
            e for e in results.entities
            if e.get("id") in remaining_entity_ids
        ]
        truncated_relationships = [
            r for r in results.relationships
            if r.get("id") in remaining_rel_ids
        ]

        # Rebuild source attributions based on remaining chunks
        remaining_file_ids: set[int] = set()
        for chunk in truncated_chunks:
            file_id = chunk.get("file_id")
            if file_id is not None:
                remaining_file_ids.add(file_id)
        for summary in truncated_summaries:
            for doc_ref in summary.get("document_references", []):
                file_id = doc_ref.get("file_id")
                if file_id is not None:
                    remaining_file_ids.add(file_id)

        truncated_attributions = [
            attr for attr in results.source_attributions
            if attr.get("file_id") in remaining_file_ids
        ]

        return SearchResult(
            chunks=truncated_chunks,
            entities=truncated_entities,
            relationships=truncated_relationships,
            community_summaries=truncated_summaries,
            source_attributions=truncated_attributions,
            metadata=results.metadata,
        )

    def _get_file_metadata(self, file_id: int | None) -> dict[str, Any]:
        """Retrieve file metadata (name, department, path) from the database.

        Args:
            file_id: The database ID of the file.

        Returns:
            Dict with name, department, and path keys. Returns empty strings
            if file is not found.
        """
        if file_id is None:
            return {"name": "", "department": "", "path": ""}

        file_record = self.db.query(File).filter(File.id == file_id).first()
        if not file_record:
            return {"name": "", "department": "", "path": ""}

        return {
            "name": file_record.name,
            "department": file_record.department,
            "path": file_record.path,
        }
