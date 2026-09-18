#!/usr/bin/env bash
# Start Neo4j for the engineering knowledge graph.
# Requires Docker Desktop: https://docs.docker.com/desktop/setup/install/mac-install/

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is not installed or not on PATH."
  echo ""
  echo "Install Docker Desktop (Apple Silicon Mac):"
  echo "  brew install --cask docker"
  echo ""
  echo "Then open Docker from Applications and wait until the whale icon is idle."
  echo "Re-run: ./scripts/setup-neo4j.sh"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker is installed but the daemon is not running."
  echo "Open Docker Desktop from Applications, wait until it finishes starting, then re-run this script."
  exit 1
fi

echo "Starting Neo4j..."
docker compose up -d neo4j

echo "Waiting for Neo4j to become ready (up to ~60s)..."
for i in $(seq 1 30); do
  if curl -sf "http://localhost:7474" >/dev/null 2>&1; then
    echo ""
    echo "Neo4j is ready."
    echo "  Browser:  http://localhost:7474"
    echo "  Login:    neo4j / changeme"
    echo "  Bolt:     bolt://localhost:7687"
    echo ""
    echo "Load the graph:"
    echo "  pip install neo4j"
    echo "  python3 -m src.graph.run load --clear -v"
    exit 0
  fi
  sleep 2
  printf "."
done

echo ""
echo "Neo4j container started but HTTP is not responding yet."
echo "Check logs: docker compose logs neo4j"
exit 1
