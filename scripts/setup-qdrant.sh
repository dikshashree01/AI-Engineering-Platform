#!/usr/bin/env bash
# Start Qdrant for the engineering RAG vector store.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed. Install Docker Desktop, then re-run this script."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Open Docker Desktop, then re-run."
  exit 1
fi

echo "Starting Qdrant..."
docker compose up -d qdrant

echo "Waiting for Qdrant (up to ~30s)..."
for _ in $(seq 1 15); do
  if curl -sf "http://localhost:6333/healthz" >/dev/null 2>&1; then
    echo ""
    echo "Qdrant is ready."
    echo "  Dashboard: http://localhost:6333/dashboard"
    echo "  REST API:  http://localhost:6333"
    echo ""
    echo "Index documents:"
    echo "  pip install qdrant-client fastembed"
    echo "  python3 -m src.rag.run index -v"
    exit 0
  fi
  sleep 2
  printf "."
done

echo ""
echo "Qdrant started but health check failed. Logs: docker compose logs qdrant"
exit 1
