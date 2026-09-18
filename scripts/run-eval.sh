#!/usr/bin/env bash
# Run the full 22-question evaluation suite and save a report.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

OUT="${1:-output/eval_report.md}"
mkdir -p "$(dirname "$OUT")"

echo "Running evaluation (requires Neo4j + Qdrant)..."
python3 -m src.agents.run eval --full --output "$OUT"
echo "Done. Report: $OUT"
