"""CLI — ask the engineering copilot."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request


def _check_url(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500, f"HTTP {resp.status}"
    except urllib.error.URLError as exc:
        return False, str(exc.reason)


def _cmd_status() -> int:
    neo4j_ok, neo4j_msg = _check_url("http://localhost:7474")
    qdrant_ok, qdrant_msg = _check_url("http://localhost:6333/healthz")

    print("Platform status:")
    print(f"  Neo4j  (7474/7687): {'✅ up' if neo4j_ok else '❌ down'} — {neo4j_msg}")
    print(f"  Qdrant (6333):      {'✅ up' if qdrant_ok else '❌ down'} — {qdrant_msg}")

    if not neo4j_ok or not qdrant_ok:
        print("\nStart stores:")
        print("  ./scripts/start-platform.sh")
        print("  # or: docker compose up -d neo4j qdrant")
        return 1

    print("\nLoad data (if needed):")
    print("  python3 -m src.graph.run load --clear")
    print("  python3 -m src.rag.run index --recreate")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])

    if argv == ["--eval"]:
        argv = ["eval"]

    # Backward compatible: `python -m src.agents.run "your question"`
    if argv and argv[0] not in {"status", "eval", "ask"} and not argv[0].startswith("-"):
        argv = ["ask", *argv]

    parser = argparse.ArgumentParser(description="AI Engineering Copilot (LangGraph)")
    sub = parser.add_subparsers(dest="command")

    ask = sub.add_parser("ask", help="Ask a question (default command)")
    ask.add_argument("query", help="Question to ask")
    ask.add_argument("--json", action="store_true", help="Output full result as JSON")

    sub.add_parser("status", help="Check Neo4j and Qdrant connectivity")

    eval_parser = sub.add_parser("eval", help="Run evaluation questions")
    eval_parser.add_argument(
        "--full",
        action="store_true",
        help="Run all 22 questions from docs/evaluation_questions.md",
    )
    eval_parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON report (use with --full)",
    )
    eval_parser.add_argument(
        "--output",
        metavar="PATH",
        help="Write markdown report to file (use with --full)",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "status":
        return _cmd_status()

    if args.command == "eval":
        if getattr(args, "full", False):
            from pathlib import Path

            from src.agents.eval import format_report, results_to_json, run_evaluation

            results, summary = run_evaluation()
            if args.json:
                print(results_to_json(results, summary))
            else:
                report = format_report(results, summary)
                if args.output:
                    Path(args.output).write_text(report, encoding="utf-8")
                    print(f"Report written to {args.output}")
                print(report)
            return 0 if summary["met_target"] else 1

        from src.agents.workflow import run_copilot

        samples = [
            "Who owns the payment service?",
            "What services depend on orders?",
            "What database does carts use?",
            "Explain the checkout flow",
            "Checkout latency increased — what runbook should I follow?",
        ]
        for q in samples:
            print(f"\n{'=' * 60}\n")
            result = run_copilot(q)
            print(result["answer"])
        return 0

    from src.agents.workflow import run_copilot

    result = run_copilot(args.query)
    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(result["answer"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
