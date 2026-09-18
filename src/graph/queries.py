"""Common Cypher queries for the engineering knowledge graph."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QueryResult:
    query: str
    description: str


# Queries used by Graph Agent (and for manual exploration in Neo4j Browser)

SERVICE_DEPENDENTS = QueryResult(
    query="""
    MATCH (caller:EngineeringAsset)-[:CALLS|DEPENDS_ON]->(target:EngineeringAsset {name: $name})
    RETURN caller.id AS id, caller.name AS name, caller.type AS type
    ORDER BY caller.name
    """,
    description="Services that depend on or call the named service",
)

SERVICE_DEPENDENCIES = QueryResult(
    query="""
    MATCH (source:EngineeringAsset {name: $name})-[:CALLS|DEPENDS_ON|USES]->(dep:EngineeringAsset)
    RETURN dep.id AS id, dep.name AS name, dep.type AS type
    ORDER BY dep.name
    """,
    description="Services/databases the named service depends on",
)

CHECKOUT_PATH = QueryResult(
    query="""
    MATCH path = (fe:EngineeringAsset {name: 'front-end'})
                 -[:CALLS|DEPENDS_ON*1..4]->(downstream:EngineeringAsset)
    WHERE downstream.name IN ['orders', 'payment', 'shipping', 'carts', 'user']
    RETURN [n IN nodes(path) | n.name] AS chain
    LIMIT 20
    """,
    description="Checkout-related dependency chains from front-end",
)

SERVICE_OWNER = QueryResult(
    query="""
    MATCH (team:Team)-[:OWNS]->(asset:EngineeringAsset {name: $name})
    RETURN team.id AS team_id, team.name AS team_name, team.slack_channel AS slack
    """,
    description="Team that owns a service or asset",
)

SERVICE_DATABASE = QueryResult(
    query="""
    MATCH (svc:EngineeringAsset {name: $name})-[:USES]->(db:EngineeringAsset)
    WHERE db:Database OR db:Queue
    RETURN db.id AS id, db.name AS name, db.engine AS engine
    """,
    description="Database or queue used by a service",
)

INCIDENTS_FOR_SERVICE = QueryResult(
    query="""
    MATCH (svc:EngineeringAsset {name: $name})-[:IMPACTED_BY]->(inc:Incident)
    RETURN inc.id AS id, inc.name AS name, inc.severity AS severity, inc.status AS status
    ORDER BY inc.started_at DESC
    """,
    description="Incidents that impacted a service",
)


def run_query(session, query: str, **params) -> list[dict]:
    """Execute a Cypher query and return records as dicts."""
    result = session.run(query, **params)
    return [record.data() for record in result]
