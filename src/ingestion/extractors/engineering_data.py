"""Parse engineering-data/ ownership, incidents, and runbooks."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import yaml

from src.ingestion.models import (
    EdgeType,
    GraphEdge,
    GraphExport,
    GraphNode,
    NodeType,
    db_id,
    edge_id,
    queue_id,
    repository_id,
    service_id,
)

logger = logging.getLogger(__name__)

DEFAULT_ENGINEERING_DATA_ROOT = Path("engineering-data")


def incident_id(incident_key: str) -> str:
    return f"incident:{incident_key}"


def runbook_id(slug: str) -> str:
    return f"runbook:{slug}"


def _resolve_entity_id(ref: str) -> str:
    """Map yaml references like service:orders or service:catalogue-db to graph ids."""
    if ref.startswith("service:"):
        name = ref.removeprefix("service:")
        if name.endswith("-db") or name == "rabbitmq":
            if name == "rabbitmq":
                return queue_id(name)
            return db_id(name)
        return service_id(name)
    if ref.startswith("repo:"):
        return repository_id(ref.removeprefix("repo:"))
    return ref


def _parse_markdown_field(content: str, field: str) -> str | None:
    match = re.search(rf"\|\s*\*\*{re.escape(field)}\*\*\s*\|\s*([^|]+?)\s*\|", content)
    return match.group(1).strip() if match else None


def _parse_service_list(text: str) -> list[str]:
    return [s.strip() for s in text.split(",") if s.strip()]


def _parse_incident_file(path: Path) -> GraphExport:
    content = path.read_text(encoding="utf-8")
    export = GraphExport(source=f"incident:{path.name}")

    inc_key = _parse_markdown_field(content, "ID") or path.stem
    node_id = incident_id(inc_key)

    export.nodes.append(
        GraphNode(
            id=node_id,
            type=NodeType.INCIDENT,
            name=inc_key,
            properties={
                "severity": _parse_markdown_field(content, "Severity"),
                "status": _parse_markdown_field(content, "Status"),
                "started_at": _parse_markdown_field(content, "Started"),
                "resolved_at": _parse_markdown_field(content, "Resolved"),
                "source_file": str(path),
                "title": path.stem,
            },
        )
    )

    impact_match = re.search(r"\*\*Affected services:\*\*\s*([^\n]+)", content)
    if impact_match:
        for svc in _parse_service_list(impact_match.group(1)):
            target = service_id(svc)
            export.edges.append(
                GraphEdge(
                    id=edge_id(EdgeType.IMPACTED_BY, target, node_id),
                    type=EdgeType.IMPACTED_BY,
                    from_id=target,
                    to_id=node_id,
                    properties={"source": str(path)},
                )
            )

    runbook_match = re.search(r"runbooks/([^\s\)]+)\.md", content)
    if runbook_match:
        rb_id = runbook_id(runbook_match.group(1))
        export.edges.append(
            GraphEdge(
                id=edge_id(EdgeType.REFERENCES, node_id, rb_id),
                type=EdgeType.REFERENCES,
                from_id=node_id,
                to_id=rb_id,
                properties={"source": str(path)},
            )
        )

    return export


def _parse_runbook_file(path: Path) -> GraphExport:
    content = path.read_text(encoding="utf-8")
    export = GraphExport(source=f"runbook:{path.name}")
    slug = path.stem
    node_id = runbook_id(slug)

    export.nodes.append(
        GraphNode(
            id=node_id,
            type=NodeType.RUNBOOK,
            name=slug,
            properties={
                "trigger": _parse_markdown_field(content, "Trigger"),
                "severity": _parse_markdown_field(content, "Severity"),
                "owner": _parse_markdown_field(content, "Owner"),
                "source_file": str(path),
            },
        )
    )

    related = _parse_markdown_field(content, "Related services")
    if related:
        for svc in _parse_service_list(related):
            target = service_id(svc)
            export.edges.append(
                GraphEdge(
                    id=edge_id(EdgeType.REFERENCES, node_id, target),
                    type=EdgeType.REFERENCES,
                    from_id=node_id,
                    to_id=target,
                    properties={"source": str(path)},
                )
            )

    return export


def _parse_teams_yaml(path: Path) -> GraphExport:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    export = GraphExport(source=f"teams:{path.name}")

    for team in data.get("teams", []):
        team_node_id = team["id"]
        export.nodes.append(
            GraphNode(
                id=team_node_id,
                type=NodeType.TEAM,
                name=team.get("name", team_node_id),
                properties={
                    "slack_channel": team.get("slack_channel"),
                    "oncall_rotation": team.get("oncall_rotation"),
                    "source_file": str(path),
                },
            )
        )
        for owned in team.get("owns", []):
            target_id = _resolve_entity_id(owned)
            export.edges.append(
                GraphEdge(
                    id=edge_id(EdgeType.OWNS, team_node_id, target_id),
                    type=EdgeType.OWNS,
                    from_id=team_node_id,
                    to_id=target_id,
                    properties={"source": str(path)},
                )
            )

    for repo in data.get("repositories", []):
        repo_name = repo.get("repo")
        team_ref = repo.get("team")
        if repo_name and team_ref:
            export.edges.append(
                GraphEdge(
                    id=edge_id(EdgeType.OWNS, team_ref, repository_id(repo_name)),
                    type=EdgeType.OWNS,
                    from_id=team_ref,
                    to_id=repository_id(repo_name),
                    properties={"source": str(path), "path": repo.get("path")},
                )
            )

    return export


def parse_engineering_data(
    data_root: Path | None = None,
    project_root: Path | None = None,
) -> GraphExport:
    """Load teams, incidents, and runbooks from engineering-data/."""
    root = project_root or Path.cwd()
    data_path = data_root or (root / DEFAULT_ENGINEERING_DATA_ROOT)
    combined = GraphExport(source="engineering-data-all")

    if not data_path.exists():
        logger.warning("Engineering data root not found: %s", data_path)
        return combined

    teams_file = data_path / "ownership" / "teams.yaml"
    if teams_file.exists():
        combined.merge(_parse_teams_yaml(teams_file))

    incidents_dir = data_path / "incidents"
    if incidents_dir.exists():
        for inc_path in sorted(incidents_dir.glob("*.md")):
            combined.merge(_parse_incident_file(inc_path))

    runbooks_dir = data_path / "runbooks"
    if runbooks_dir.exists():
        for rb_path in sorted(runbooks_dir.glob("*.md")):
            combined.merge(_parse_runbook_file(rb_path))

    return combined
