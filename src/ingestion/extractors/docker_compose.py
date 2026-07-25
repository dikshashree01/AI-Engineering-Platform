"""Parse docker-compose.yml into service, database, and queue nodes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

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
    service_id,
)

# Known service -> datastore mappings from Sock Shop deploy configs
SERVICE_USES: dict[str, str] = {
    "catalogue": "catalogue-db",
    "carts": "carts-db",
    "orders": "orders-db",
    "user": "user-db",
    "shipping": "rabbitmq",
    "queue-master": "rabbitmq",
}


def _infer_engine(image: str, env: list[str] | dict[str, str] | None) -> str | None:
    image_lower = image.lower()
    if "mongo" in image_lower or "user-db" in image_lower:
        return "mongodb"
    if "mysql" in image_lower or "catalogue-db" in image_lower:
        return "mysql"
    if "redis" in image_lower:
        return "redis"
    if "rabbitmq" in image_lower:
        return "rabbitmq"
    return None


def _is_datastore(name: str, image: str) -> bool:
    if name.endswith("-db") or name == "rabbitmq":
        return True
    engine = _infer_engine(image, None)
    return engine in ("mongodb", "mysql", "redis", "rabbitmq") and (
        name.endswith("-db") or name == "rabbitmq"
    )


def _normalize_env(env: Any) -> dict[str, str]:
    if env is None:
        return {}
    if isinstance(env, dict):
        return {str(k): str(v) for k, v in env.items()}
    result: dict[str, str] = {}
    if isinstance(env, list):
        for item in env:
            if isinstance(item, str) and "=" in item:
                key, _, value = item.partition("=")
                result[key] = value
    return result


def parse_docker_compose(compose_path: Path) -> GraphExport:
    """Extract services, databases, queues, and USES edges from docker-compose."""
    data = yaml.safe_load(compose_path.read_text())
    services: dict[str, Any] = data.get("services", {})
    export = GraphExport(source=f"docker-compose:{compose_path.name}")

    for name, config in services.items():
        if not isinstance(config, dict):
            continue
        image = str(config.get("image", ""))
        hostname = str(config.get("hostname", name))
        env = _normalize_env(config.get("environment"))

        if _is_datastore(name, image):
            engine = _infer_engine(image, env) or "unknown"
            node_type = NodeType.QUEUE if engine == "rabbitmq" else NodeType.DATABASE
            node_id = queue_id(name) if node_type == NodeType.QUEUE else db_id(name)
            props: dict[str, Any] = {
                "hostname": hostname,
                "image": image,
                "engine": engine,
                "source_file": str(compose_path),
            }
            if env.get("MYSQL_DATABASE"):
                props["database_name"] = env["MYSQL_DATABASE"]
            export.nodes.append(
                GraphNode(id=node_id, type=node_type, name=name, properties=props)
            )
        else:
            export.nodes.append(
                GraphNode(
                    id=service_id(name),
                    type=NodeType.SERVICE,
                    name=name,
                    properties={
                        "hostname": hostname,
                        "image": image,
                        "source_file": str(compose_path),
                    },
                )
            )

    for service_name, target in SERVICE_USES.items():
        if service_name not in services or target not in services:
            continue
        target_config = services[target]
        target_image = str(target_config.get("image", ""))
        engine = _infer_engine(target_image, None)
        if engine == "rabbitmq":
            to_id = queue_id(target)
        else:
            to_id = db_id(target)
        export.edges.append(
            GraphEdge(
                id=edge_id(EdgeType.USES, service_id(service_name), to_id),
                type=EdgeType.USES,
                from_id=service_id(service_name),
                to_id=to_id,
                properties={"source": "docker-compose-mapping"},
            )
        )

    return export
