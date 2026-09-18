"""Index document chunks into Qdrant."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from src.rag.config import RagConfig
from src.rag.embedder import Embedder, create_embedder
from src.rag.models import DocumentChunk, IndexResult
from src.rag.sources import collect_chunks

logger = logging.getLogger(__name__)

BATCH_SIZE = 32


def _point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def get_qdrant_client(config: RagConfig):
    try:
        from qdrant_client import QdrantClient
    except ImportError as exc:
        raise ImportError(
            "qdrant-client not installed. Run: pip install qdrant-client"
        ) from exc

    kwargs: dict = {"url": config.qdrant_url, "check_compatibility": False}
    if config.qdrant_api_key:
        kwargs["api_key"] = config.qdrant_api_key
    return QdrantClient(**kwargs)


def ensure_collection(client, collection_name: str, vector_size: int, *, recreate: bool) -> None:
    from qdrant_client.models import Distance, VectorParams

    exists = client.collection_exists(collection_name)
    if recreate and exists:
        logger.info("Recreating collection %s", collection_name)
        client.delete_collection(collection_name)
        exists = False

    if not exists:
        logger.info("Creating collection %s (vector_size=%d)", collection_name, vector_size)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def index_chunks(
    chunks: list[DocumentChunk],
    config: RagConfig | None = None,
    embedder: Embedder | None = None,
    *,
    recreate: bool = False,
) -> IndexResult:
    """Embed and upsert chunks into Qdrant."""
    cfg = config or RagConfig.from_env()
    emb = embedder or create_embedder(cfg)
    client = get_qdrant_client(cfg)

    ensure_collection(client, cfg.collection_name, emb.vector_size, recreate=recreate)

    from qdrant_client.models import PointStruct

    sources = sorted({chunk.source_file for chunk in chunks})
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        vectors = emb.embed([chunk.text for chunk in batch])
        points = [
            PointStruct(
                id=_point_id(chunk.chunk_id),
                vector=vector,
                payload=chunk.to_payload(),
            )
            for chunk, vector in zip(batch, vectors, strict=True)
        ]
        client.upsert(collection_name=cfg.collection_name, points=points)
        logger.info("Upserted batch %d-%d", start + 1, start + len(batch))

    return IndexResult(
        chunks_indexed=len(chunks),
        collection=cfg.collection_name,
        sources=sources,
        embedding_provider=cfg.embedding_provider,
        vector_size=emb.vector_size,
    )


def index_project(
    project_root: Path | None = None,
    config: RagConfig | None = None,
    embedder: Embedder | None = None,
    *,
    recreate: bool = False,
    include_apis: bool = True,
) -> IndexResult:
    """Discover sources, chunk, and index into Qdrant."""
    cfg = config or RagConfig.from_env()
    root = (project_root or Path.cwd()).resolve()

    chunks, source_labels = collect_chunks(
        project_root=root,
        engineering_data_path=Path(cfg.engineering_data_path),
        docs_path=Path(cfg.docs_path),
        graph_json_path=Path(cfg.graph_json_path),
        include_apis=include_apis,
    )
    logger.info("Collected %d chunks from %d sources", len(chunks), len(source_labels))
    for label in source_labels:
        logger.info("  %s", label)

    result = index_chunks(chunks, config=cfg, embedder=embedder, recreate=recreate)
    return result
