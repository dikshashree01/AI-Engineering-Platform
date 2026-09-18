"""Tests for Neo4j loader (unit tests — no Neo4j required)."""

import pytest

from src.ingestion.models import EdgeType, GraphEdge, GraphNode, NodeType, service_id
from src.graph.loader import (
    REL_TYPE_PATTERN,
    _prepare_edge_batch,
    _prepare_node_batch,
    _validate_label,
    _validate_rel_type,
)


def test_validate_label_accepts_node_types() -> None:
    assert _validate_label("Service") == "Service"
    assert _validate_label("Database") == "Database"


def test_validate_label_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        _validate_label("Service; DROP")


def test_validate_rel_type() -> None:
    assert _validate_rel_type("CALLS") == "CALLS"
    with pytest.raises(ValueError):
        _validate_rel_type("calls")


def test_prepare_node_batch_groups_by_label() -> None:
    nodes = [
        GraphNode(id=service_id("orders"), type=NodeType.SERVICE, name="orders"),
        GraphNode(id="db:orders-db", type=NodeType.DATABASE, name="orders-db"),
    ]
    batches = _prepare_node_batch(nodes)
    assert len(batches["Service"]) == 1
    assert len(batches["Database"]) == 1
    assert batches["Service"][0]["id"] == "service:orders"


def test_prepare_edge_batch_groups_by_type() -> None:
    edges = [
        GraphEdge(
            id="CALLS:a->b",
            type=EdgeType.CALLS,
            from_id="service:orders",
            to_id="service:payment",
        ),
        GraphEdge(
            id="USES:a->b",
            type=EdgeType.USES,
            from_id="service:orders",
            to_id="db:orders-db",
        ),
    ]
    batches = _prepare_edge_batch(edges)
    assert len(batches["CALLS"]) == 1
    assert len(batches["USES"]) == 1


def test_rel_type_pattern_matches_edge_types() -> None:
    for rel in EdgeType:
        assert REL_TYPE_PATTERN.match(rel.value)
