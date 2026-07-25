"""Pydantic models for the engineering knowledge graph export."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    SERVICE = "Service"
    DATABASE = "Database"
    QUEUE = "Queue"
    API = "API"
    REPOSITORY = "Repository"
    TEAM = "Team"
    INCIDENT = "Incident"
    RUNBOOK = "Runbook"
    DOCUMENT = "Document"


class EdgeType(str, Enum):
    CALLS = "CALLS"
    USES = "USES"
    DEPENDS_ON = "DEPENDS_ON"
    EXPOSES = "EXPOSES"
    OWNS = "OWNS"
    HOSTS = "HOSTS"
    CONTAINS = "CONTAINS"
    IMPACTED_BY = "IMPACTED_BY"
    REFERENCES = "REFERENCES"
    DOCUMENTED_IN = "DOCUMENTED_IN"


class GraphNode(BaseModel):
    id: str
    type: NodeType
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    id: str
    type: EdgeType
    from_id: str
    to_id: str
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphExport(BaseModel):
    version: str = "0.1"
    source: str = "sock-shop"
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)

    def merge(self, other: GraphExport) -> None:
        existing_nodes = {n.id for n in self.nodes}
        existing_edges = {e.id for e in self.edges}
        for node in other.nodes:
            if node.id not in existing_nodes:
                self.nodes.append(node)
                existing_nodes.add(node.id)
        for edge in other.edges:
            if edge.id not in existing_edges:
                self.edges.append(edge)
                existing_edges.add(edge.id)

    def stats(self) -> dict[str, int]:
        node_counts: dict[str, int] = {}
        edge_counts: dict[str, int] = {}
        for node in self.nodes:
            node_counts[node.type.value] = node_counts.get(node.type.value, 0) + 1
        for edge in self.edges:
            edge_counts[edge.type.value] = edge_counts.get(edge.type.value, 0) + 1
        return {
            "nodes_total": len(self.nodes),
            "edges_total": len(self.edges),
            **{f"nodes_{k}": v for k, v in node_counts.items()},
            **{f"edges_{k}": v for k, v in edge_counts.items()},
        }


def repository_id(name: str) -> str:
    return f"repo:{name}"


def service_id(name: str) -> str:
    return f"service:{name}"


def db_id(name: str) -> str:
    return f"db:{name}"


def queue_id(name: str) -> str:
    return f"queue:{name}"


def api_id(service: str, method: str, path: str) -> str:
    normalized = path.replace("/", "_").strip("_") or "root"
    return f"api:{service}:{method.upper()}:{normalized}"


def edge_id(edge_type: EdgeType, from_id: str, to_id: str, suffix: str = "") -> str:
    base = f"{edge_type.value}:{from_id}->{to_id}"
    return f"{base}:{suffix}" if suffix else base
