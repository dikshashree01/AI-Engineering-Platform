"""Platform health checks."""

from __future__ import annotations

import urllib.error
import urllib.request


def check_url(url: str, timeout: float = 2.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def platform_health() -> dict[str, bool]:
    return {
        "neo4j": check_url("http://localhost:7474"),
        "qdrant": check_url("http://localhost:6333/healthz"),
    }
