"""CLI — index and search engineering documents in Qdrant."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.rag.config import RagConfig
from src.rag.indexer import get_qdrant_client, index_project
from src.rag.search import search_chunks
from src.rag.sources import collect_chunks


def _cmd_index(args: argparse.Namespace) -> int:
    cfg = RagConfig.from_env()
    result = index_project(
        project_root=args.project_root,
        config=cfg,
        recreate=args.recreate,
        include_apis=not args.skip_apis,
    )
    print(f"Indexed {result.chunks_indexed} chunks into '{result.collection}'")
    print(f"Embedding provider: {result.embedding_provider} (dim={result.vector_size})")
    print(f"Sources: {len(result.sources)} files/paths")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    services = args.service.split(",") if args.service else None
    hits = search_chunks(
        args.query,
        doc_type=args.doc_type,
        services=services,
        limit=args.limit,
    )
    if not hits:
        print("No results.")
        return 0

    for rank, hit in enumerate(hits, start=1):
        chunk = hit.chunk
        print(f"\n[{rank}] score={hit.score:.4f}  {chunk.doc_type}  {chunk.section}")
        print(f"    graph: {chunk.graph_node_id}")
        print(f"    file:  {chunk.source_file}")
        preview = chunk.text.replace("\n", " ")[:200]
        print(f"    {preview}...")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    cfg = RagConfig.from_env()
    try:
        client = get_qdrant_client(cfg)
    except ImportError:
        print("Install qdrant-client: pip install qdrant-client", file=sys.stderr)
        return 1

    if not client.collection_exists(cfg.collection_name):
        print(f"Collection '{cfg.collection_name}' does not exist. Run: index")
        return 1

    info = client.get_collection(cfg.collection_name)
    print(f"Qdrant connected: {cfg.qdrant_url}")
    print(f"Collection: {cfg.collection_name}")
    print(f"Points: {info.points_count}")
    print(f"Vector size: {info.config.params.vectors.size}")

    if args.sample:
        print("\n--- Sample: checkout latency runbook ---")
        hits = search_chunks(
            "checkout latency investigation steps",
            doc_type="runbook",
            limit=2,
        )
        for hit in hits:
            print(f"  [{hit.score:.3f}] {hit.chunk.section} ({hit.chunk.graph_node_id})")

        print("\n--- Sample: orders dependencies (docs) ---")
        hits = search_chunks(
            "what database does carts use",
            doc_type="doc",
            limit=2,
        )
        for hit in hits:
            print(f"  [{hit.score:.3f}] {hit.chunk.section}")

    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    root = args.project_root.resolve()
    cfg = RagConfig.from_env()
    chunks, labels = collect_chunks(
        project_root=root,
        engineering_data_path=Path(cfg.engineering_data_path),
        docs_path=Path(cfg.docs_path),
        graph_json_path=Path(cfg.graph_json_path),
        include_apis=not args.skip_apis,
    )
    by_type: dict[str, int] = {}
    for chunk in chunks:
        by_type[chunk.doc_type] = by_type.get(chunk.doc_type, 0) + 1

    print(f"Chunks to index: {len(chunks)}")
    for doc_type, count in sorted(by_type.items()):
        print(f"  {doc_type}: {count}")
    print("Sources:")
    for label in labels:
        print(f"  - {label}")
    return 0


def main(argv: list[str] | None = None) -> int:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        description="Engineering RAG — Qdrant indexer and search",
        parents=[shared],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    index_parser = sub.add_parser("index", parents=[shared], help="Index documents into Qdrant")
    index_parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root (default: cwd)",
    )
    index_parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop and recreate the Qdrant collection",
    )
    index_parser.add_argument(
        "--skip-apis",
        action="store_true",
        help="Skip API chunks from engineering_graph.json",
    )

    search_parser = sub.add_parser("search", parents=[shared], help="Semantic search")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("--doc-type", choices=["runbook", "incident", "doc", "api"])
    search_parser.add_argument("--service", help="Comma-separated service filter")
    search_parser.add_argument("--limit", type=int, default=5)

    verify_parser = sub.add_parser("verify", parents=[shared], help="Check Qdrant collection")
    verify_parser.add_argument("--sample", action="store_true", help="Run sample searches")

    stats_parser = sub.add_parser("stats", parents=[shared], help="Show chunk counts without indexing")
    stats_parser.add_argument("--project-root", type=Path, default=Path.cwd())
    stats_parser.add_argument("--skip-apis", action="store_true")

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    if not args.verbose:
        for name in ("httpx", "httpcore", "huggingface_hub", "fastembed"):
            logging.getLogger(name).setLevel(logging.WARNING)

    if args.command == "index":
        return _cmd_index(args)
    if args.command == "search":
        return _cmd_search(args)
    if args.command == "verify":
        return _cmd_verify(args)
    if args.command == "stats":
        return _cmd_stats(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
