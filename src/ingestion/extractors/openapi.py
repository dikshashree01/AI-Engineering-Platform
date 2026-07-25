"""Parse OpenAPI (Swagger 2.0) specs into API nodes."""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.models import (
    EdgeType,
    GraphEdge,
    GraphExport,
    GraphNode,
    NodeType,
    api_id,
    edge_id,
    service_id,
)


def parse_openapi_spec(spec_path: Path) -> GraphExport:
    """Extract API endpoints and EXPOSES edges from a Swagger 2.0 file."""
    data = json.loads(spec_path.read_text())
    host = data.get("host", spec_path.parent.parent.name)
    base_path = data.get("basePath", "/").rstrip("/")
    paths: dict = data.get("paths", {})

    export = GraphExport(source=f"openapi:{spec_path.name}")

    for path, methods in paths.items():
        if not isinstance(methods, dict):
            continue
        full_path = f"{base_path}{path}" if base_path else path
        if not full_path.startswith("/"):
            full_path = f"/{full_path}"

        for method, details in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if not isinstance(details, dict):
                continue

            method_upper = method.upper()
            node_id = api_id(host, method_upper, full_path)
            description = details.get("description") or details.get("operationId") or ""

            export.nodes.append(
                GraphNode(
                    id=node_id,
                    type=NodeType.API,
                    name=f"{method_upper} {full_path}",
                    properties={
                        "service": host,
                        "method": method_upper,
                        "path": full_path,
                        "description": description,
                        "source_file": str(spec_path),
                    },
                )
            )
            export.edges.append(
                GraphEdge(
                    id=edge_id(EdgeType.EXPOSES, service_id(host), node_id),
                    type=EdgeType.EXPOSES,
                    from_id=service_id(host),
                    to_id=node_id,
                    properties={"source": "openapi"},
                )
            )

    return export


def parse_openapi_directory(services_root: Path) -> GraphExport:
    """Walk service repos and parse all api-spec/*.json files."""
    combined = GraphExport(source="openapi-all")
    if not services_root.exists():
        return combined

    for spec_path in sorted(services_root.glob("*/api-spec/*.json")):
        if spec_path.name in {"mock.json", "routes.json"}:
            continue
        combined.merge(parse_openapi_spec(spec_path))

    return combined
