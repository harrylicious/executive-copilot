"""Community detection service using Leiden algorithm.

Detects hierarchical communities in the entity graph using the Leiden algorithm
via the `leidenalg` and `igraph` libraries. Generates natural language summaries
for each community and produces summary embeddings for global search comparison.
"""

import logging
from typing import TYPE_CHECKING

import igraph as ig
import leidenalg
import networkx as nx
import tiktoken

from app.config import GraphRAGSettings
from app.models.community import Community
from app.models.entity import Entity
from app.models.entity_relationship import EntityRelationship

if TYPE_CHECKING:
    from app.services.embedding_model import EmbeddingModel

logger = logging.getLogger(__name__)

# Maximum tokens allowed in a community summary
MAX_SUMMARY_TOKENS = 500

# Minimum number of entities required for community detection
MIN_ENTITIES_FOR_DETECTION = 3


class CommunityDetector:
    """Detects communities in the entity graph using Leiden algorithm.

    Uses hierarchical community detection to produce 2-5 levels of granularity.
    Generates natural language summaries (≤500 tokens) for each community and
    computes summary embeddings for global search comparison.

    Args:
        config: GraphRAG settings containing resolution and max_community_size.
        embedding_model: Optional EmbeddingModel instance for generating
            summary embeddings. If None, summaries will not have embeddings.
    """

    def __init__(
        self,
        config: GraphRAGSettings,
        embedding_model: "EmbeddingModel | None" = None,
    ):
        self.resolution = config.community_resolution
        self.max_community_size = config.max_community_size
        self.embedding_model = embedding_model
        self._tokenizer = tiktoken.get_encoding("cl100k_base")


    def detect(
        self,
        entities: list[Entity],
        relationships: list[EntityRelationship],
    ) -> list[Community]:
        """Run hierarchical community detection (2-5 levels).

        Builds a networkx graph from entities and relationships, converts it
        to igraph, and runs the Leiden algorithm at multiple resolution levels
        to produce a hierarchy of communities.

        If fewer than 3 entities exist, community detection is skipped and
        an empty list is returned.

        Args:
            entities: List of Entity model instances to cluster.
            relationships: List of EntityRelationship model instances
                representing edges between entities.

        Returns:
            List of Community model instances with level, member_entity_ids,
            summary, and summary_embedding populated.
        """
        if len(entities) < MIN_ENTITIES_FOR_DETECTION:
            logger.info(
                f"Skipping community detection: only {len(entities)} entities "
                f"(minimum {MIN_ENTITIES_FOR_DETECTION} required)"
            )
            return []

        # Build networkx graph
        nx_graph = self._build_networkx_graph(entities, relationships)

        if nx_graph.number_of_nodes() < MIN_ENTITIES_FOR_DETECTION:
            logger.info(
                f"Skipping community detection: graph has only "
                f"{nx_graph.number_of_nodes()} nodes after building"
            )
            return []

        # Convert to igraph for Leiden algorithm
        ig_graph = self._networkx_to_igraph(nx_graph)

        # Run hierarchical Leiden at multiple resolutions
        hierarchy = self._run_hierarchical_leiden(ig_graph, nx_graph)

        # Build Community objects
        communities = self._build_communities(hierarchy, entities, relationships)

        return communities

    def generate_summary(
        self,
        community: Community,
        entities: list[Entity],
        relationships: list[EntityRelationship],
    ) -> str:
        """Generate natural language summary for a community (≤500 tokens).

        Produces a summary describing the community's theme and the top 5
        relationships by strength score among its member entities.

        Args:
            community: The Community instance to summarize.
            entities: All entities in the knowledge graph.
            relationships: All relationships in the knowledge graph.

        Returns:
            A natural language summary string of at most 500 tokens.
        """
        member_ids = set(community.member_entity_ids or [])

        # Get member entities
        member_entities = [e for e in entities if e.id in member_ids]

        if not member_entities:
            return ""

        # Get relationships between member entities (internal edges)
        internal_relationships = [
            r for r in relationships
            if r.source_entity_id in member_ids and r.target_entity_id in member_ids
        ]

        # Sort by strength descending, take top 5
        top_relationships = sorted(
            internal_relationships,
            key=lambda r: r.strength if r.strength is not None else 0.0,
            reverse=True,
        )[:5]

        # Build summary text
        summary_parts = []

        # Community overview
        entity_types = {}
        for e in member_entities:
            entity_types.setdefault(e.entity_type, []).append(e.name)

        type_descriptions = []
        for etype, names in entity_types.items():
            if len(names) <= 3:
                type_descriptions.append(f"{etype}s: {', '.join(names)}")
            else:
                type_descriptions.append(
                    f"{etype}s: {', '.join(names[:3])} and {len(names) - 3} more"
                )

        summary_parts.append(
            f"This community contains {len(member_entities)} entities "
            f"including {'; '.join(type_descriptions)}."
        )

        # Top relationships
        if top_relationships:
            summary_parts.append("Key relationships:")
            # Build entity ID to name mapping
            entity_id_to_name = {e.id: e.name for e in entities}
            for rel in top_relationships:
                source_name = entity_id_to_name.get(
                    rel.source_entity_id, "Unknown"
                )
                target_name = entity_id_to_name.get(
                    rel.target_entity_id, "Unknown"
                )
                desc = rel.description or "related to"
                strength_str = f" (strength: {rel.strength:.2f})" if rel.strength else ""
                summary_parts.append(
                    f"- {source_name} → {target_name}: {desc}{strength_str}"
                )

        summary = "\n".join(summary_parts)

        # Truncate to 500 tokens if needed
        summary = self._truncate_to_token_limit(summary, MAX_SUMMARY_TOKENS)

        return summary

    def _build_networkx_graph(
        self,
        entities: list[Entity],
        relationships: list[EntityRelationship],
    ) -> nx.Graph:
        """Build a networkx graph from entities and relationships.

        Args:
            entities: List of Entity instances (nodes).
            relationships: List of EntityRelationship instances (edges).

        Returns:
            An undirected networkx Graph with entity IDs as nodes.
        """
        G = nx.Graph()

        # Add nodes
        for entity in entities:
            G.add_node(
                entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
            )

        # Add edges with weight based on strength
        for rel in relationships:
            # Only add edge if both endpoints exist in the graph
            if G.has_node(rel.source_entity_id) and G.has_node(rel.target_entity_id):
                # If edge already exists, keep the higher strength
                if G.has_edge(rel.source_entity_id, rel.target_entity_id):
                    existing_weight = G[rel.source_entity_id][rel.target_entity_id].get(
                        "weight", 0.0
                    )
                    if (rel.strength or 0.0) > existing_weight:
                        G[rel.source_entity_id][rel.target_entity_id]["weight"] = (
                            rel.strength or 0.5
                        )
                else:
                    G.add_edge(
                        rel.source_entity_id,
                        rel.target_entity_id,
                        weight=rel.strength or 0.5,
                    )

        return G

    def _networkx_to_igraph(self, nx_graph: nx.Graph) -> ig.Graph:
        """Convert a networkx graph to an igraph Graph.

        Preserves node IDs as a vertex attribute for mapping back to entities.

        Args:
            nx_graph: The networkx graph to convert.

        Returns:
            An igraph Graph with 'entity_id' vertex attribute and 'weight'
            edge attribute.
        """
        # Get ordered list of nodes
        nodes = list(nx_graph.nodes())
        node_to_idx = {node: idx for idx, node in enumerate(nodes)}

        # Create igraph graph
        ig_graph = ig.Graph(n=len(nodes), directed=False)

        # Set vertex attributes
        ig_graph.vs["entity_id"] = nodes

        # Add edges
        edges = []
        weights = []
        for u, v, data in nx_graph.edges(data=True):
            edges.append((node_to_idx[u], node_to_idx[v]))
            weights.append(data.get("weight", 0.5))

        if edges:
            ig_graph.add_edges(edges)
            ig_graph.es["weight"] = weights

        return ig_graph

    def _run_hierarchical_leiden(
        self,
        ig_graph: ig.Graph,
        nx_graph: nx.Graph,
    ) -> list[dict[int, list[int]]]:
        """Run Leiden algorithm at multiple resolutions for hierarchy.

        Produces 2-5 hierarchy levels by running Leiden at geometrically
        increasing resolution values. Level 0 is the coarsest (lowest
        resolution) and higher levels are progressively finer.

        Args:
            ig_graph: The igraph Graph to partition.
            nx_graph: The original networkx graph (for node ID mapping).

        Returns:
            List of dictionaries, one per level. Each dictionary maps
            community_id (int) to a list of entity IDs in that community.
        """
        # Determine resolution levels: produce 2-5 levels
        # Use geometric progression from base_resolution/4 to base_resolution*4
        base_resolution = self.resolution
        num_levels = min(5, max(2, ig_graph.vcount() // 5 + 1))

        # Generate resolution values from coarse to fine
        if num_levels == 2:
            resolutions = [base_resolution * 0.25, base_resolution * 2.0]
        elif num_levels == 3:
            resolutions = [
                base_resolution * 0.25,
                base_resolution,
                base_resolution * 4.0,
            ]
        elif num_levels == 4:
            resolutions = [
                base_resolution * 0.125,
                base_resolution * 0.5,
                base_resolution * 2.0,
                base_resolution * 8.0,
            ]
        else:  # 5 levels
            resolutions = [
                base_resolution * 0.0625,
                base_resolution * 0.25,
                base_resolution,
                base_resolution * 4.0,
                base_resolution * 16.0,
            ]

        hierarchy = []
        previous_partition = None

        for level_idx, resolution in enumerate(resolutions):
            partition = leidenalg.find_partition(
                ig_graph,
                leidenalg.RBConfigurationVertexPartition,
                resolution_parameter=resolution,
                weights="weight" if ig_graph.ecount() > 0 else None,
            )

            # Convert partition to community mapping
            level_communities: dict[int, list[int]] = {}
            for community_idx, members in enumerate(partition):
                entity_ids = [ig_graph.vs[m]["entity_id"] for m in members]
                if entity_ids:  # Skip empty communities
                    level_communities[community_idx] = entity_ids

            # Only add this level if it differs from the previous one
            if previous_partition is None or level_communities != previous_partition:
                hierarchy.append(level_communities)
                previous_partition = level_communities

        # Ensure we have at least 2 levels
        if len(hierarchy) < 2:
            # If all resolutions produced the same partition, create a
            # coarser level by merging all into one community
            all_entity_ids = [ig_graph.vs[v]["entity_id"] for v in range(ig_graph.vcount())]
            coarse_level = {0: all_entity_ids}
            if hierarchy and hierarchy[0] != coarse_level:
                hierarchy.insert(0, coarse_level)
            elif not hierarchy:
                hierarchy = [coarse_level, coarse_level]

        # Cap at 5 levels
        hierarchy = hierarchy[:5]

        return hierarchy

    def _build_communities(
        self,
        hierarchy: list[dict[int, list[int]]],
        entities: list[Entity],
        relationships: list[EntityRelationship],
    ) -> list[Community]:
        """Build Community model instances from the hierarchy.

        Generates summaries and summary embeddings for each community.

        Args:
            hierarchy: List of level dictionaries mapping community_id to
                entity ID lists.
            entities: All entities for summary generation.
            relationships: All relationships for summary generation.

        Returns:
            List of Community instances ready for database storage.
        """
        communities = []

        for level_idx, level_communities in enumerate(hierarchy):
            for community_id, member_entity_ids in level_communities.items():
                community = Community(
                    level=level_idx,
                    member_entity_ids=member_entity_ids,
                    summary=None,
                    summary_embedding=None,
                )

                # Generate summary
                try:
                    summary = self.generate_summary(
                        community, entities, relationships
                    )
                    community.summary = summary
                except Exception as e:
                    logger.error(
                        f"Failed to generate summary for community at level "
                        f"{level_idx}: {e}"
                    )
                    community.summary = ""

                # Generate summary embedding
                if community.summary and self.embedding_model:
                    try:
                        embedding = self.embedding_model.embed_query(
                            community.summary
                        )
                        community.summary_embedding = embedding
                    except Exception as e:
                        logger.error(
                            f"Failed to generate summary embedding for "
                            f"community at level {level_idx}: {e}"
                        )

                communities.append(community)

        return communities

    def _truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """Truncate text to fit within a token limit.

        Uses tiktoken to count tokens and truncates at token boundaries.

        Args:
            text: The text to potentially truncate.
            max_tokens: Maximum number of tokens allowed.

        Returns:
            The text, truncated if necessary to fit within max_tokens.
        """
        tokens = self._tokenizer.encode(text)
        if len(tokens) <= max_tokens:
            return text

        # Truncate tokens and decode back to text
        truncated_tokens = tokens[:max_tokens]
        return self._tokenizer.decode(truncated_tokens)

    def _count_tokens(self, text: str) -> int:
        """Count the number of tokens in a text string.

        Args:
            text: The text to count tokens for.

        Returns:
            Number of tokens.
        """
        return len(self._tokenizer.encode(text))
