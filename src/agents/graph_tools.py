"""Neo4j tool functions for the Graph Agent."""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Callable, Iterator, TypeVar

from src.graph.config import Neo4jConfig
from src.graph.queries import (
    CHECKOUT_PATH,
    INCIDENTS_FOR_SERVICE,
    SERVICE_DATABASE,
    SERVICE_DEPENDENCIES,
    SERVICE_DEPENDENTS,
    SERVICE_OWNER,
    run_query,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

NEO4J_START_HINT = "./scripts/setup-neo4j.sh  (or: docker compose up -d neo4j)"


@contextmanager
def graph_session(config: Neo4jConfig | None = None) -> Iterator:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise ImportError("Install neo4j: pip install neo4j") from exc

    cfg = config or Neo4jConfig.from_env()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
    try:
        with driver.session() as session:
            yield session
    finally:
        driver.close()


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for row in rows:
        key = str(row)
        if key not in seen:
            seen.add(key)
            unique.append(row)
    return unique


def _graph_error_message(exc: Exception) -> str:
    msg = str(exc)
    if "Connection refused" in msg or "Failed to establish connection" in msg:
        return f"Neo4j is not running at localhost:7687. Start it: {NEO4J_START_HINT}"
    if "Unable to retrieve routing information" in msg:
        return f"Neo4j is unreachable. Start it: {NEO4J_START_HINT}"
    return f"Neo4j query failed: {msg}"


def _safe_graph_evidence(tool: str, fn: Callable[[], T], **meta) -> dict:
    try:
        data = fn()
        return {"source": "graph", "tool": tool, "data": data, **meta}
    except Exception as exc:
        logger.warning("Graph tool %s failed: %s", tool, exc)
        return {
            "source": "graph",
            "tool": tool,
            "data": [],
            "error": _graph_error_message(exc),
            **meta,
        }


def get_service_owner(service_name: str) -> list[dict]:
    with graph_session() as session:
        return run_query(session, SERVICE_OWNER.query, name=service_name)


def get_service_dependencies(service_name: str) -> list[dict]:
    with graph_session() as session:
        rows = run_query(session, SERVICE_DEPENDENCIES.query, name=service_name)
        return _dedupe_rows(rows)


def get_service_dependents(service_name: str) -> list[dict]:
    with graph_session() as session:
        rows = run_query(session, SERVICE_DEPENDENTS.query, name=service_name)
        return _dedupe_rows(rows)


def get_service_database(service_name: str) -> list[dict]:
    with graph_session() as session:
        return run_query(session, SERVICE_DATABASE.query, name=service_name)


def get_checkout_paths() -> list[dict]:
    with graph_session() as session:
        return run_query(session, CHECKOUT_PATH.query)


def get_database_asset(asset_name: str) -> list[dict]:
    with graph_session() as session:
        return run_query(
            session,
            """
            MATCH (asset:EngineeringAsset {name: $name})
            OPTIONAL MATCH (user:EngineeringAsset)-[:USES]->(asset)
            RETURN asset.id AS id, asset.name AS name, asset.type AS type,
                   asset.engine AS engine, collect(DISTINCT user.name) AS used_by
            """,
            name=asset_name,
        )


def get_service_catalog() -> list[dict]:
    with graph_session() as session:
        return run_query(
            session,
            """
            MATCH (s:EngineeringAsset)
            WHERE s:Service
            RETURN s.name AS name, s.type AS type
            ORDER BY s.name
            """,
        )


def get_incidents_for_service(service_name: str) -> list[dict]:
    with graph_session() as session:
        return run_query(session, INCIDENTS_FOR_SERVICE.query, name=service_name)


def gather_graph_evidence(intent: str, service_name: str | None) -> list[dict]:
    """Run graph tools based on classified intent."""
    evidence: list[dict] = []

    if intent == "ownership" and service_name:
        evidence.append(
            _safe_graph_evidence(
                "service_owner",
                lambda: get_service_owner(service_name),
                service=service_name,
            )
        )

    elif intent == "dependencies" and service_name:
        evidence.append(
            _safe_graph_evidence(
                "service_dependencies",
                lambda: get_service_dependencies(service_name),
                service=service_name,
            )
        )

    elif intent in ("dependents", "impact") and service_name:
        evidence.append(
            _safe_graph_evidence(
                "service_dependents",
                lambda: get_service_dependents(service_name),
                service=service_name,
            )
        )

    elif intent == "failure" and service_name:
        evidence.append(
            _safe_graph_evidence(
                "service_dependents",
                lambda: get_service_dependents(service_name),
                service=service_name,
            )
        )
        evidence.append(
            _safe_graph_evidence(
                "incidents",
                lambda: get_incidents_for_service(service_name),
                service=service_name,
            )
        )

    elif intent == "availability" and service_name:
        evidence.append(
            _safe_graph_evidence(
                "service_dependencies",
                lambda: get_service_dependencies("catalogue"),
                service="catalogue",
            )
        )
        evidence.append(
            _safe_graph_evidence(
                "service_dependencies",
                lambda: get_service_dependencies("front-end"),
                service="front-end",
            )
        )

    elif intent == "database" and service_name:
        if service_name in ("session-db", "catalogue-db", "carts-db", "orders-db", "user-db"):
            evidence.append(
                _safe_graph_evidence(
                    "database_asset",
                    lambda: get_database_asset(service_name),
                    service=service_name,
                )
            )
        evidence.append(
            _safe_graph_evidence(
                "service_database",
                lambda: get_service_database(service_name),
                service=service_name,
            )
        )

    elif intent == "checkout":
        evidence.append(_safe_graph_evidence("checkout_path", get_checkout_paths))
        if service_name:
            evidence.append(
                _safe_graph_evidence(
                    "service_dependencies",
                    lambda: get_service_dependencies(service_name),
                    service=service_name,
                )
            )

    elif intent == "incident" and service_name:
        evidence.append(
            _safe_graph_evidence(
                "incidents",
                lambda: get_incidents_for_service(service_name),
                service=service_name,
            )
        )

    elif intent == "explain":
        evidence.append(_safe_graph_evidence("checkout_path", get_checkout_paths))
        evidence.append(
            _safe_graph_evidence("service_catalog", get_service_catalog)
        )

    elif intent == "service_lookup" and service_name:
        evidence.extend([
            _safe_graph_evidence(
                "service_owner",
                lambda: get_service_owner(service_name),
                service=service_name,
            ),
            _safe_graph_evidence(
                "service_dependencies",
                lambda: get_service_dependencies(service_name),
                service=service_name,
            ),
            _safe_graph_evidence(
                "service_database",
                lambda: get_service_database(service_name),
                service=service_name,
            ),
        ])

    return evidence
