"""CLI entry point for the ingestion pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from src.ingestion.pipeline import DEFAULT_OUTPUT, IngestionConfig, run_ingestion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run engineering graph ingestion pipeline",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output JSON path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    config = IngestionConfig(
        project_root=args.project_root,
        output_path=args.output,
    )
    result = run_ingestion(config)

    stats = result.graph.stats()
    print(f"Extractors run: {', '.join(result.extractors_run)}")
    print(f"Nodes: {stats['nodes_total']} | Edges: {stats['edges_total']}")
    print(f"Output: {result.output_path}")

    if result.warnings:
        print("\nWarnings:")
        for warning in result.warnings:
            print(f"  - {warning}")

    for key, value in sorted(stats.items()):
        if key not in ("nodes_total", "edges_total"):
            print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
