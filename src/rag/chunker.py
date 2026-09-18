"""Split markdown and graph nodes into searchable chunks."""

from __future__ import annotations

import re
from pathlib import Path

from src.ingestion.models import GraphExport, GraphNode, NodeType
from src.rag.models import DocumentChunk

TABLE_FIELD_RE = re.compile(
    r"\|\s*\*\*(?P<field>[^*]+)\*\*\s*\|\s*(?P<value>[^|]+?)\s*\|"
)
AFFECTED_SERVICES_RE = re.compile(r"\*\*Affected services:\*\*\s*([^\n]+)")
RELATED_SERVICES_RE = re.compile(r"\*\*Related services\*\*\s*\|\s*([^|]+?)\s*\|")
INCIDENT_ID_RE = re.compile(r"\*\*ID\*\*\s*\|\s*([^|]+?)\s*\|")


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "section"


def _parse_table_fields(content: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for match in TABLE_FIELD_RE.finditer(content):
        fields[match.group("field").strip()] = match.group("value").strip()
    return fields


def _parse_service_list(text: str | None) -> list[str]:
    if not text:
        return []
    return [s.strip() for s in text.split(",") if s.strip()]


def _split_markdown_sections(content: str) -> list[tuple[str | None, str]]:
    """Split markdown on ## and ### headings; include heading in chunk text."""
    lines = content.splitlines()
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in lines:
        if line.startswith("## "):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.removeprefix("## ").strip()
            current_lines = [line]
        elif line.startswith("### "):
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = line.removeprefix("### ").strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    result: list[tuple[str | None, str]] = []
    for heading, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if len(body) >= 40:
            result.append((heading, body))
    return result


def _chunk_id(*parts: str) -> str:
    return ":".join(_slug(p) for p in parts if p)


def chunk_runbook(path: Path, project_root: Path | None = None) -> list[DocumentChunk]:
    content = path.read_text(encoding="utf-8")
    slug = path.stem
    graph_node_id = f"runbook:{slug}"
    fields = _parse_table_fields(content)
    services = _parse_service_list(fields.get("Related services"))
    rel_path = _relative_path(path, project_root)
    title = fields.get("Trigger") or slug

    chunks: list[DocumentChunk] = []
    for idx, (section, text) in enumerate(_split_markdown_sections(content)):
        section_name = section or "overview"
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id("runbook", slug, section_name, str(idx)),
                text=text,
                doc_type="runbook",
                source_file=rel_path,
                section=section_name,
                graph_node_id=graph_node_id,
                services=services,
                title=title,
                properties={
                    "severity": fields.get("Severity"),
                    "owner": fields.get("Owner"),
                },
            )
        )
    return chunks


def chunk_incident(path: Path, project_root: Path | None = None) -> list[DocumentChunk]:
    content = path.read_text(encoding="utf-8")
    fields = _parse_table_fields(content)
    inc_key = fields.get("ID") or path.stem
    graph_node_id = f"incident:{inc_key}"
    rel_path = _relative_path(path, project_root)

    services_match = AFFECTED_SERVICES_RE.search(content)
    services_raw = services_match.group(1) if services_match else ""
    services = [
        s.split("(")[0].strip()
        for s in _parse_service_list(services_raw)
        if s.split("(")[0].strip()
    ]

    chunks: list[DocumentChunk] = []
    for idx, (section, text) in enumerate(_split_markdown_sections(content)):
        section_name = section or "overview"
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id("incident", inc_key, section_name, str(idx)),
                text=text,
                doc_type="incident",
                source_file=rel_path,
                section=section_name,
                graph_node_id=graph_node_id,
                services=services,
                title=path.stem,
                properties={
                    "severity": fields.get("Severity"),
                    "status": fields.get("Status"),
                    "started_at": fields.get("Started"),
                    "resolved_at": fields.get("Resolved"),
                },
            )
        )
    return chunks


def chunk_doc(path: Path, project_root: Path | None = None) -> list[DocumentChunk]:
    content = path.read_text(encoding="utf-8")
    rel_path = _relative_path(path, project_root)
    doc_slug = path.stem
    graph_node_id = f"document:{rel_path.replace('/', ':')}"

    chunks: list[DocumentChunk] = []
    for idx, (section, text) in enumerate(_split_markdown_sections(content)):
        section_name = section or doc_slug
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id("doc", doc_slug, section_name, str(idx)),
                text=text,
                doc_type="doc",
                source_file=rel_path,
                section=section_name,
                graph_node_id=graph_node_id,
                title=doc_slug,
                properties={"doc_name": doc_slug},
            )
        )
    return chunks


def chunk_api_nodes(graph: GraphExport) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for node in graph.nodes:
        if node.type != NodeType.API:
            continue
        service = node.properties.get("service", "")
        description = node.properties.get("description", "")
        method = node.properties.get("method", "")
        path_value = node.properties.get("path", "")
        text = (
            f"API endpoint {node.name}\n"
            f"Service: {service}\n"
            f"Method: {method}\n"
            f"Path: {path_value}\n"
            f"Description: {description}"
        ).strip()
        chunks.append(
            DocumentChunk(
                chunk_id=_chunk_id("api", node.id),
                text=text,
                doc_type="api",
                source_file=str(node.properties.get("source_file", "")),
                section=node.name,
                graph_node_id=node.id,
                services=[service] if service else [],
                title=node.name,
                properties={
                    "method": method,
                    "path": path_value,
                    "service": service,
                },
            )
        )
    return chunks


def _relative_path(path: Path, project_root: Path | None) -> str:
    if project_root:
        try:
            return str(path.resolve().relative_to(project_root.resolve()))
        except ValueError:
            pass
    return str(path)
