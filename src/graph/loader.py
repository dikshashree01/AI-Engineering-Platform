"""Load GraphExport JSON into Neo4j."""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from src.graph.config import Neo4jConfig
from src.ingestion.models import GraphEdge, GraphExport, GraphNode
from src.ingestion.pipeline import DEFAULT_OUTPUT, load_graph

logger = logging.getLogger(__name__)

LABEL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
REL_TYPE_PATTERN = re.compile(r"^[A-Z_]+$")


@dataclass
class LoadResult:
    nodes_loaded: int
    edges_loaded: int
    edges_skipped: int
    graph_source: str


def _validate_label(label: str) -> str:
    if not LABEL_PATTERN.match(label):
        raise ValueError(f"Invalid node label: {label}")
    return label


def _validate_rel_type(rel_type: str) -> str:
    if not REL_TYPE_PATTERN.match(rel_type):
        raise ValueError(f"Invalid relationship type: {rel_type}")
    return rel_type


def _node_merge_cypher(label: str) -> str:
    safe_label = _validate_label(label)
    return f"""
    UNWIND $nodes AS node
    MERGE (n:EngineeringAsset:{safe_label} {{id: node.id}})
    SET n.name = node.name,
        n.type = node.type,
        n += node.properties
    """


def _edge_merge_cypher(rel_type: str) -> str:
    safe_rel = _validate_rel_type(rel_type)
    return f"""
    UNWIND $edges AS edge
    MATCH (a:EngineeringAsset {{id: edge.from_id}})
    MATCH (b:EngineeringAsset {{id: edge.to_id}})
    MERGE (a)-[r:{safe_rel}]->(b)
    SET r.id = edge.id,
        r.type = edge.type,
        r += edge.properties
    """


def _prepare_node_batch(nodes: list[GraphNode]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for node in nodes:
        grouped[node.type.value].append(
            {
                "id": node.id,
                "name": node.name,
                "type": node.type.value,
                "properties": node.properties,
            }
        )
    return grouped


def _prepare_edge_batch(edges: list[GraphEdge]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for edge in edges:
        grouped[edge.type.value].append(
            {
                "id": edge.id,
                "from_id": edge.from_id,
                "to_id": edge.to_id,
                "type": edge.type.value,
                "properties": edge.properties,
            }
        )
    return grouped


def clear_graph(session) -> None:
    """Remove all nodes and relationships."""
    session.run("MATCH (n) DETACH DELETE n")


def create_indexes(session) -> None:
    """Create indexes for fast lookups by id and name."""
    session.run(
        "CREATE INDEX engineering_asset_id IF NOT EXISTS "
        "FOR (n:EngineeringAsset) ON (n.id)"
    )
    session.run(
        "CREATE INDEX engineering_asset_name IF NOT EXISTS "
        "FOR (n:EngineeringAsset) ON (n.name)"
    )


def load_graph_export(
    graph: GraphExport,
    config: Neo4jConfig | None = None,
    *,
    clear: bool = False,
) -> LoadResult:
    """
    Load a GraphExport into Neo4j.

    Requires the official neo4j Python driver and a running Neo4j instance.
    """
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise ImportError(
            "neo4j driver not installed. Run: pip install neo4j"
        ) from exc

    cfg = config or Neo4jConfig.from_env()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))

    edges_skipped = 0
    try:
        with driver.session() as session:
            if clear:
                logger.info("Clearing existing graph...")
                clear_graph(session)

            create_indexes(session)

            node_batches = _prepare_node_batch(graph.nodes)
            for label, batch in node_batches.items():
                logger.info("Loading %d %s nodes", len(batch), label)
                session.run(_node_merge_cypher(label), nodes=batch)

            edge_batches = _prepare_edge_batch(graph.edges)
            for rel_type, batch in edge_batches.items():
                logger.info("Loading %d %s edges", len(batch), rel_type)
                result = session.run(_edge_merge_cypher(rel_type), edges=batch)
                result.consume()

            if graph.edges:
                skip_row = session.run(
                    """
                    UNWIND $edges AS edge
                    OPTIONAL MATCH (a:EngineeringAsset {id: edge.from_id})
                                   -[r {id: edge.id}]->
                                   (b:EngineeringAsset {id: edge.to_id})
                    WITH edge, r
                    WHERE r IS NULL
                    RETURN count(edge) AS skipped
                    """,
                    edges=[
                        {"id": e.id, "from_id": e.from_id, "to_id": e.to_id}
                        for e in graph.edges
                    ],
                ).single()
                edges_skipped = skip_row["skipped"] if skip_row else 0

    finally:
        driver.close()

    return LoadResult(
        nodes_loaded=len(graph.nodes),
        edges_loaded=len(graph.edges) - edges_skipped,
        edges_skipped=edges_skipped,
        graph_source=graph.source,
    )


def load_graph_file(
    input_path: Path | None = None,
    config: Neo4jConfig | None = None,
    *,
    clear: bool = False,
) -> LoadResult:
    """Load engineering_graph.json into Neo4j."""
    path = input_path or DEFAULT_OUTPUT
    graph = load_graph(path)
    return load_graph_export(graph, config=config, clear=clear)
