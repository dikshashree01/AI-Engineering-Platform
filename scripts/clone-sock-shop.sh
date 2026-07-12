#!/usr/bin/env bash
# Clone Sock Shop repositories into source-repo/ for local ingestion.
# These repos are gitignored — each developer clones them locally.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INFRA_DIR="$ROOT/source-repo/infrastructure"
SERVICES_DIR="$ROOT/source-repo/services"

mkdir -p "$INFRA_DIR" "$SERVICES_DIR"

clone_if_missing() {
  local url="$1"
  local dest="$2"
  if [ -d "$dest/.git" ]; then
    echo "✓ Already cloned: $dest"
  else
    echo "→ Cloning $url → $dest"
    git clone --depth 1 "$url" "$dest"
  fi
}

echo "=== Infrastructure ==="
clone_if_missing "https://github.com/microservices-demo/microservices-demo.git" \
  "$INFRA_DIR/microservices-demo"

echo ""
echo "=== Services ==="
clone_if_missing "https://github.com/microservices-demo/front-end.git" \
  "$SERVICES_DIR/front-end"
clone_if_missing "https://github.com/microservices-demo/catalogue.git" \
  "$SERVICES_DIR/catalogue"
clone_if_missing "https://github.com/microservices-demo/carts.git" \
  "$SERVICES_DIR/carts"
clone_if_missing "https://github.com/microservices-demo/orders.git" \
  "$SERVICES_DIR/orders"
clone_if_missing "https://github.com/microservices-demo/payment.git" \
  "$SERVICES_DIR/payment"
clone_if_missing "https://github.com/microservices-demo/user.git" \
  "$SERVICES_DIR/user"
clone_if_missing "https://github.com/microservices-demo/shipping.git" \
  "$SERVICES_DIR/shipping"

echo ""
echo "Done. Sock Shop repos are in source-repo/"
