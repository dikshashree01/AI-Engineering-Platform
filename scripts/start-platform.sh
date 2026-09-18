#!/usr/bin/env bash
# Start Neo4j + Qdrant for the engineering copilot.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop first."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Open Docker Desktop."
  exit 1
fi

echo "Starting Neo4j and Qdrant..."
docker compose up -d neo4j qdrant

echo "Waiting for services..."
for i in $(seq 1 30); do
  neo4j_ok=0
  qdrant_ok=0
  curl -sf http://localhost:7474 >/dev/null 2>&1 && neo4j_ok=1
  curl -sf http://localhost:6333/healthz >/dev/null 2>&1 && qdrant_ok=1
  if [ "$neo4j_ok" -eq 1 ] && [ "$qdrant_ok" -eq 1 ]; then
    echo ""
    echo "Platform stores are ready."
    echo "  Neo4j:  http://localhost:7474  (neo4j / changeme)"
    echo "  Qdrant: http://localhost:6333/dashboard"
    echo ""
    echo "Load data (if not already):"
    echo "  python3 -m src.graph.run load --clear"
    echo "  python3 -m src.rag.run index --recreate"
    echo ""
    echo "Ask the copilot:"
    echo '  python3 -m src.agents.run "Who owns the payment service?"'
    exit 0
  fi
  sleep 2
  printf "."
done

echo ""
echo "Services started but health checks did not pass yet."
echo "Check: docker compose ps"
echo "Logs:  docker compose logs neo4j qdrant"
exit 1
