"""CLI — load engineering_graph.json into Neo4j."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.graph.config import Neo4jConfig
from src.graph.loader import load_graph_file
from src.graph.queries import (
    CHECKOUT_PATH,
    SERVICE_DEPENDENCIES,
    SERVICE_DEPENDENTS,
    run_query,
)
from src.ingestion.pipeline import DEFAULT_OUTPUT


def _cmd_load(args: argparse.Namespace) -> int:
    result = load_graph_file(
        input_path=args.input,
        config=Neo4jConfig.from_env(),
        clear=args.clear,
    )
    print(f"Loaded graph source: {result.graph_source}")
    print(f"Nodes: {result.nodes_loaded}")
    print(f"Edges: {result.edges_loaded} (skipped {result.edges_skipped} orphan refs)")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        from neo4j import GraphDatabase
    except ImportError:
        print("Install neo4j driver: pip install neo4j", file=sys.stderr)
        return 1

    cfg = Neo4jConfig.from_env()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
    try:
        with driver.session() as session:
            counts = session.run(
                "MATCH (n:EngineeringAsset) RETURN count(n) AS nodes"
            ).single()
            rels = session.run(
                "MATCH ()-[r]->() RETURN count(r) AS edges"
            ).single()
            print(f"Neo4j connected: {cfg.uri}")
            print(f"Nodes in graph: {counts['nodes']}")
            print(f"Relationships: {rels['edges']}")

            if args.sample:
                print("\n--- Who depends on orders? ---")
                for row in run_query(session, SERVICE_DEPENDENTS.query, name="orders"):
                    print(f"  {row['name']} ({row['type']})")

                print("\n--- What does orders depend on? ---")
                for row in run_query(session, SERVICE_DEPENDENCIES.query, name="orders"):
                    print(f"  {row['name']} ({row['type']})")

                print("\n--- Checkout paths from front-end ---")
                for row in run_query(session, CHECKOUT_PATH.query):
                    print(f"  {' -> '.join(row['chain'])}")
    finally:
        driver.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        description="Neo4j graph loader",
        parents=[shared],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    load_parser = sub.add_parser(
        "load",
        parents=[shared],
        help="Load engineering_graph.json into Neo4j",
    )
    load_parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Input JSON (default: {DEFAULT_OUTPUT})",
    )
    load_parser.add_argument(
        "--clear",
        action="store_true",
        help="Delete existing graph before loading",
    )

    verify_parser = sub.add_parser(
        "verify",
        parents=[shared],
        help="Check Neo4j connection and graph stats",
    )
    verify_parser.add_argument(
        "--sample",
        action="store_true",
        help="Run sample dependency queries",
    )

    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "load":
        return _cmd_load(args)
    if args.command == "verify":
        return _cmd_verify(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
