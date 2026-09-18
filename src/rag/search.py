"""Semantic search over indexed engineering documents."""

from __future__ import annotations

import logging
from typing import Any

from src.rag.config import RagConfig
from src.rag.embedder import Embedder, create_embedder
from src.rag.indexer import get_qdrant_client
from src.rag.models import DocumentChunk, SearchHit

logger = logging.getLogger(__name__)


def _build_filter(
    doc_type: str | None,
    services: list[str] | None,
):
    from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

    must: list = []
    if doc_type:
        must.append(
            FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
        )
    if services:
        must.append(
            FieldCondition(key="services", match=MatchAny(any=services))
        )
    return Filter(must=must) if must else None


def _vector_search(
    client: Any,
    *,
    collection_name: str,
    query_vector: list[float],
    query_filter,
    limit: int,
) -> list[Any]:
    """
    Run a vector similarity search across qdrant-client versions.

    qdrant-client >=1.12 uses query_points(); older versions use search().
    """
    if hasattr(client, "query_points"):
        response = client.query_points(
            collection_name=collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
        )
        return list(response.points)

    return client.search(
        collection_name=collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )


def search_chunks(
    query: str,
    config: RagConfig | None = None,
    embedder: Embedder | None = None,
    *,
    doc_type: str | None = None,
    services: list[str] | None = None,
    limit: int = 5,
) -> list[SearchHit]:
    """Vector search with optional doc_type and service filters."""
    cfg = config or RagConfig.from_env()
    emb = embedder or create_embedder(cfg)
    client = get_qdrant_client(cfg)

    query_vector = emb.embed([query])[0]
    query_filter = _build_filter(doc_type, services)

    results = _vector_search(
        client,
        collection_name=cfg.collection_name,
        query_vector=query_vector,
        query_filter=query_filter,
        limit=limit,
    )

    hits: list[SearchHit] = []
    for point in results:
        payload = point.payload or {}
        chunk = DocumentChunk(
            chunk_id=str(payload.get("chunk_id", "")),
            text=str(payload.get("text", "")),
            doc_type=str(payload.get("doc_type", "")),
            source_file=str(payload.get("source_file", "")),
            section=payload.get("section"),
            graph_node_id=payload.get("graph_node_id"),
            services=list(payload.get("services") or []),
            title=payload.get("title"),
            properties={
                k: v
                for k, v in payload.items()
                if k
                not in {
                    "chunk_id",
                    "text",
                    "doc_type",
                    "source_file",
                    "section",
                    "graph_node_id",
                    "services",
                    "title",
                }
            },
        )
        hits.append(SearchHit(score=point.score or 0.0, chunk=chunk))

    return hits
