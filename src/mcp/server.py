"""MCP server — expose graph, RAG, and copilot tools to Cursor."""

from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from src.agents.graph_tools import (
    get_checkout_paths,
    get_service_database,
    get_service_dependencies,
    get_service_dependents,
    get_service_owner,
)
from src.agents.workflow import run_copilot
from src.rag.search import search_chunks

mcp = FastMCP(
    "engineering-platform",
    instructions=(
        "Engineering intelligence for Sock Shop microservices. "
        "Use graph_* tools for ownership, dependencies, and databases. "
        "Use rag_search for runbooks, incidents, and docs. "
        "Use copilot_ask for complex multi-step questions."
    ),
)


def _json(data) -> str:
    return json.dumps(data, indent=2, default=str)


@mcp.tool()
def copilot_ask(query: str) -> str:
    """Ask the full engineering copilot (graph + RAG + synthesis)."""
    result = run_copilot(query)
    return _json(result)


@mcp.tool()
def graph_service_owner(service_name: str) -> str:
    """Return the team that owns a service (Neo4j OWNS relationship)."""
    return _json(get_service_owner(service_name))


@mcp.tool()
def graph_service_dependencies(service_name: str) -> str:
    """Return services/databases a service depends on."""
    return _json(get_service_dependencies(service_name))


@mcp.tool()
def graph_service_dependents(service_name: str) -> str:
    """Return services that call or depend on the named service."""
    return _json(get_service_dependents(service_name))


@mcp.tool()
def graph_service_database(service_name: str) -> str:
    """Return database or queue used by a service."""
    return _json(get_service_database(service_name))


@mcp.tool()
def graph_checkout_paths() -> str:
    """Return checkout-related dependency chains from front-end."""
    return _json(get_checkout_paths())


@mcp.tool()
def rag_search(
    query: str,
    doc_type: str | None = None,
    service: str | None = None,
    limit: int = 5,
) -> str:
    """
    Semantic search over runbooks, incidents, docs, and API descriptions.

    doc_type: runbook | incident | doc | api
    service: optional filter, e.g. payment, orders, carts
    """
    services = [service] if service else None
    hits = search_chunks(query, doc_type=doc_type, services=services, limit=limit)
    payload = [
        {
            "score": round(hit.score, 4),
            "doc_type": hit.chunk.doc_type,
            "section": hit.chunk.section,
            "graph_node_id": hit.chunk.graph_node_id,
            "source_file": hit.chunk.source_file,
            "text": hit.chunk.text[:1000],
        }
        for hit in hits
    ]
    return _json(payload)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
