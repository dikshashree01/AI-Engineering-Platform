"""Discover files and graph exports for RAG indexing."""

from __future__ import annotations

import logging
from pathlib import Path

from src.ingestion.pipeline import load_graph
from src.rag.chunker import chunk_api_nodes, chunk_doc, chunk_incident, chunk_runbook
from src.rag.models import DocumentChunk

logger = logging.getLogger(__name__)


def collect_chunks(
    project_root: Path,
    engineering_data_path: Path,
    docs_path: Path,
    graph_json_path: Path | None = None,
    *,
    include_apis: bool = True,
) -> tuple[list[DocumentChunk], list[str]]:
    """
    Gather all document chunks from engineering-data, docs, and optional graph APIs.
    Returns (chunks, source_labels).
    """
    root = project_root.resolve()
    chunks: list[DocumentChunk] = []
    sources: list[str] = []

    eng_root = engineering_data_path if engineering_data_path.is_absolute() else root / engineering_data_path
    docs_root = docs_path if docs_path.is_absolute() else root / docs_path

    runbooks_dir = eng_root / "runbooks"
    if runbooks_dir.exists():
        for path in sorted(runbooks_dir.glob("*.md")):
            file_chunks = chunk_runbook(path, project_root=root)
            chunks.extend(file_chunks)
            sources.append(f"runbook:{path.name} ({len(file_chunks)} chunks)")

    incidents_dir = eng_root / "incidents"
    if incidents_dir.exists():
        for path in sorted(incidents_dir.glob("*.md")):
            file_chunks = chunk_incident(path, project_root=root)
            chunks.extend(file_chunks)
            sources.append(f"incident:{path.name} ({len(file_chunks)} chunks)")

    if docs_root.exists():
        for path in sorted(docs_root.glob("*.md")):
            file_chunks = chunk_doc(path, project_root=root)
            chunks.extend(file_chunks)
            sources.append(f"doc:{path.name} ({len(file_chunks)} chunks)")

    if include_apis and graph_json_path:
        graph_path = graph_json_path if graph_json_path.is_absolute() else root / graph_json_path
        if graph_path.exists():
            graph = load_graph(graph_path)
            api_chunks = chunk_api_nodes(graph)
            chunks.extend(api_chunks)
            sources.append(f"graph-apis ({len(api_chunks)} chunks)")
        else:
            logger.warning("Graph JSON not found for API chunks: %s", graph_path)

    return chunks, sources
