"""Qdrant tool functions for Docs and Incident agents."""

from __future__ import annotations

import logging

from src.agents.intent import ParsedQuery
from src.rag.search import search_chunks

logger = logging.getLogger(__name__)

QDRANT_START_HINT = "./scripts/setup-qdrant.sh  (or: docker compose up -d qdrant)"


def _rag_error_message(exc: Exception) -> str:
    msg = str(exc)
    if "Connection refused" in msg or "ConnectError" in msg:
        return f"Qdrant is not running at localhost:6333. Start it: {QDRANT_START_HINT}"
    if "does not exist" in msg.lower():
        return "Qdrant collection missing. Run: python3 -m src.rag.run index --recreate"
    return f"RAG search failed: {msg}"


def _hits_to_evidence(tool: str, hits) -> dict:
    return {
        "source": "rag",
        "tool": tool,
        "data": [
            {
                "score": round(hit.score, 4),
                "doc_type": hit.chunk.doc_type,
                "section": hit.chunk.section,
                "graph_node_id": hit.chunk.graph_node_id,
                "source_file": hit.chunk.source_file,
                "text": hit.chunk.text[:800],
            }
            for hit in hits
        ],
    }


def _safe_rag_search(tool: str, **search_kwargs) -> dict:
    try:
        hits = search_chunks(**search_kwargs)
        return _hits_to_evidence(tool, hits)
    except Exception as exc:
        logger.warning("RAG tool %s failed: %s", tool, exc)
        return {
            "source": "rag",
            "tool": tool,
            "data": [],
            "error": _rag_error_message(exc),
        }


def gather_rag_evidence(parsed: ParsedQuery, query: str) -> list[dict]:
    """Run vector search based on classified intent."""
    evidence: list[dict] = []
    service_filter = [parsed.service_name] if parsed.service_name else None

    if parsed.intent == "incident":
        evidence.append(
            _safe_rag_search(
                "search_incidents",
                query=query,
                doc_type="incident",
                services=service_filter,
                limit=3,
            )
        )
        evidence.append(
            _safe_rag_search(
                "search_runbooks",
                query=query,
                doc_type="runbook",
                services=service_filter,
                limit=2,
            )
        )

    elif parsed.intent == "failure":
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=query,
                doc_type="doc",
                services=service_filter,
                limit=3,
            )
        )
        evidence.append(
            _safe_rag_search(
                "search_incidents",
                query=query,
                doc_type="incident",
                services=service_filter,
                limit=2,
            )
        )

    elif parsed.intent == "availability":
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=f"browse catalogue user service unavailable {query}",
                doc_type="doc",
                limit=4,
            )
        )

    elif parsed.intent == "repository":
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=query,
                doc_type="doc",
                limit=4,
            )
        )
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=f"source-repo services {parsed.service_name or 'repository modify'}",
                doc_type="doc",
                limit=2,
            )
        )
        evidence.append(
            _safe_rag_search(
                "search_api",
                query=query,
                doc_type="api",
                services=service_filter,
                limit=2,
            )
        )

    elif parsed.intent == "checkout":
        evidence.append(
            _safe_rag_search(
                "search_runbooks",
                query=query,
                doc_type="runbook",
                services=service_filter,
                limit=3,
            )
        )
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query="checkout flow architecture",
                doc_type="doc",
                limit=2,
            )
        )

    elif parsed.intent == "explain":
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=f"sock shop microservices architecture {query}",
                doc_type="doc",
                limit=4,
            )
        )
        if not parsed.service_name:
            evidence.append(
                _safe_rag_search(
                    "search_docs",
                    query="programming languages polyglot Java Go Node.js Spring Boot",
                    doc_type="doc",
                    limit=2,
                )
            )

    elif parsed.intent == "ownership":
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=f"team owns {parsed.service_name or query}",
                doc_type="doc",
                limit=2,
            )
        )

    elif parsed.intent in ("general", "service_lookup", "database", "dependencies", "dependents", "impact"):
        evidence.append(
            _safe_rag_search(
                "search_docs",
                query=query,
                doc_type="doc",
                services=service_filter,
                limit=3,
            )
        )

    return evidence
