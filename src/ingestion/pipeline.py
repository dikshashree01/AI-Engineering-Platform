"""Orchestrate all extractors and produce a merged engineering graph."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.ingestion.extractors.call_graph import parse_call_graph
from src.ingestion.extractors.docker_compose import parse_docker_compose
from src.ingestion.extractors.engineering_data import parse_engineering_data
from src.ingestion.extractors.openapi import parse_openapi_directory
from src.ingestion.extractors.repository import parse_repositories
from src.ingestion.models import GraphExport

logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path("output/engineering_graph.json")
DEFAULT_COMPOSE = Path(
    "source-repo/infrastructure/microservices-demo/deploy/docker-compose/docker-compose.yml"
)
DEFAULT_SERVICES = Path("source-repo/services")
DEFAULT_ENGINEERING_DATA = Path("engineering-data")


@dataclass
class IngestionConfig:
    """Configurable paths — all relative to project_root by default."""

    project_root: Path = field(default_factory=Path.cwd)
    docker_compose_path: Path = DEFAULT_COMPOSE
    services_root: Path = DEFAULT_SERVICES
    engineering_data_root: Path = DEFAULT_ENGINEERING_DATA
    output_path: Path = DEFAULT_OUTPUT

    def resolve(self, path: Path) -> Path:
        if path.is_absolute():
            return path
        return self.project_root / path


@dataclass
class IngestionResult:
    graph: GraphExport
    output_path: Path
    extractors_run: list[str]
    warnings: list[str]


def run_ingestion(config: IngestionConfig | None = None) -> IngestionResult:
    """
    Run all ingestion extractors and merge into a single GraphExport.

    Each extractor is independent — failures on optional inputs produce warnings
    but do not stop the pipeline.
    """
    cfg = config or IngestionConfig()
    root = cfg.project_root.resolve()

    compose_path = cfg.resolve(cfg.docker_compose_path)
    services_path = cfg.resolve(cfg.services_root)
    data_path = cfg.resolve(cfg.engineering_data_root)
    output_path = cfg.resolve(cfg.output_path)

    graph = GraphExport(version="0.1", source="engineering-intelligence")
    extractors_run: list[str] = []
    warnings: list[str] = []

    if compose_path.exists():
        logger.info("Running docker-compose extractor: %s", compose_path)
        graph.merge(parse_docker_compose(compose_path))
        extractors_run.append("docker_compose")
    else:
        msg = f"Docker compose file not found: {compose_path}"
        logger.warning(msg)
        warnings.append(msg)

    if services_path.exists():
        logger.info("Running repository extractor: %s", services_path)
        graph.merge(parse_repositories(services_path, project_root=root))
        extractors_run.append("repository")

        logger.info("Running openapi extractor: %s", services_path)
        graph.merge(parse_openapi_directory(services_path))
        extractors_run.append("openapi")

        logger.info("Running call-graph extractor: %s", services_path)
        graph.merge(parse_call_graph(services_path))
        extractors_run.append("call_graph")
    else:
        msg = f"Services root not found: {services_path}"
        logger.warning(msg)
        warnings.append(msg)

    if data_path.exists():
        logger.info("Running engineering-data extractor: %s", data_path)
        graph.merge(parse_engineering_data(data_path, project_root=root))
        extractors_run.append("engineering_data")
    else:
        msg = f"Engineering data root not found: {data_path}"
        logger.warning(msg)
        warnings.append(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_graph(graph, output_path)

    stats = graph.stats()
    logger.info(
        "Ingestion complete: %d nodes, %d edges -> %s",
        stats["nodes_total"],
        stats["edges_total"],
        output_path,
    )

    return IngestionResult(
        graph=graph,
        output_path=output_path,
        extractors_run=extractors_run,
        warnings=warnings,
    )


def write_graph(graph: GraphExport, output_path: Path) -> None:
    """Serialize GraphExport to JSON."""
    payload = graph.model_dump(mode="json")
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_graph(input_path: Path) -> GraphExport:
    """Load a previously exported graph from JSON."""
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return GraphExport.model_validate(data)
