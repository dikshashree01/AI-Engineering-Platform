"""Ingestion extractors — each returns GraphExport."""

from src.ingestion.extractors.call_graph import parse_call_graph
from src.ingestion.extractors.docker_compose import parse_docker_compose
from src.ingestion.extractors.openapi import parse_openapi_directory, parse_openapi_spec
from src.ingestion.extractors.repository import parse_repositories

__all__ = [
    "parse_call_graph",
    "parse_docker_compose",
    "parse_openapi_directory",
    "parse_openapi_spec",
    "parse_repositories",
]
